"""Document field extraction via a vision model, with strict PII scrubbing.

Flow:
 1. Image bytes are sent to the configured vision model (API key from env).
 2. The model is instructed to return ONLY the allow-listed fields as JSON.
 3. The raw model output is scrubbed in code regardless of what the model
    returned: any field not on the allow-list is dropped, and any value
    that looks like a 12-digit number (Aadhaar), PAN pattern, or other
    banned identifier is rejected/redacted.
 4. The image bytes are discarded immediately after extraction; they are
    NEVER written to disk or stored in the database.
"""
from __future__ import annotations

import os
import re
from typing import Any

from app.pii import find_identifier

ALLOWED_FIELDS = {
    "name",
    "date_of_birth",
    "age",
    "gender",
    "state",
    "district",
    "occupation",
    "income_band",
    "income_amount",
    "caste_category",
    "marital_status",
    "family_size",
    "land_holding",
    "disability_status",
    "document_type",
}

# Patterns for identifiers we must never return or store.
AADHAAR_RE = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")
TWELVE_DIGIT_RE = re.compile(r"\b\d{12}\b")
PAN_RE = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b", re.IGNORECASE)
VOTER_ID_RE = re.compile(r"\b[A-Z]{3}\d{7}\b", re.IGNORECASE)
PASSPORT_RE = re.compile(r"\b[A-PR-WY][1-9]\d\s?\d{4}[1-9]\b", re.IGNORECASE)
BANK_ACCOUNT_RE = re.compile(r"\b\d{9,18}\b")
PHONE_RE = re.compile(r"\b\d{10}\b")
VID_RE = re.compile(r"\b\d{16}\b")

BANNED_PATTERNS = [AADHAAR_RE, TWELVE_DIGIT_RE, PAN_RE, VOTER_ID_RE, PASSPORT_RE, VID_RE]

SYSTEM_PROMPT = (
    "You are extracting ONLY the following fields from a government document "
    "image, for the purpose of helping someone find welfare schemes: name, "
    "date_of_birth (or age), gender, state, district, occupation, "
    "income_band or income_amount, caste_category, marital_status, "
    "family_size, land_holding, disability_status, document_type. "
    "You must NEVER return an Aadhaar number, PAN, voter ID, passport "
    "number, bank account number, phone number, QR code content, barcode "
    "content, or VID, under any circumstances, even if visible in the "
    "image. Respond ONLY with a flat JSON object using exactly these field "
    "names; omit any field you cannot read confidently."
)


class ExtractionError(Exception):
    pass


def contains_banned_identifier(value: Any) -> bool:
    if value is None:
        return False
    s = str(value)
    if any(p.search(s) for p in BANNED_PATTERNS):
        return True
    return find_identifier(s) is not None      # the same rule used for everything typed by a person


def scrub_extracted_fields(raw: dict) -> dict:
    """Allow-list filter + banned-pattern rejection. Never trusts the model.

    Any key not in ALLOWED_FIELDS is dropped. Any value matching a banned
    identifier pattern anywhere in the dict causes that field to be dropped
    entirely (fail safe: drop rather than partially redact).
    """
    if not isinstance(raw, dict):
        return {}

    clean: dict = {}
    for key, value in raw.items():
        if key not in ALLOWED_FIELDS:
            continue
        if contains_banned_identifier(value):
            continue
        if isinstance(value, str) and not value.strip():
            continue
        clean[key] = value
    return clean


def call_vision_model(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    """Call the configured vision model. Returns raw (unscrubbed) dict.

    Uses VISION_API_KEY and VISION_API_URL from environment. If no key is
    configured (e.g. local/dev/test), raises ExtractionError so callers can
    handle gracefully rather than silently fabricating data.
    """
    api_key = os.environ.get("VISION_API_KEY")
    if not api_key:
        raise ExtractionError(
            "VISION_API_KEY is not configured; document extraction is unavailable."
        )

    # NOTE: Real HTTP call to the vision provider would go here using
    # httpx, with SYSTEM_PROMPT and image_bytes as a base64 payload. The
    # exact provider wire format depends on which vision API key the
    # deployer configures, so this is intentionally left as the single
    # integration point. The image bytes must never be persisted.
    import httpx

    api_url = os.environ.get(
        "VISION_API_URL", "https://api.openai.com/v1/chat/completions"
    )
    model = os.environ.get("VISION_MODEL", "gpt-4o-mini")
    import base64

    b64 = base64.b64encode(image_bytes).decode("ascii")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract the allowed fields from this document image."},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
                ],
            },
        ],
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        resp = httpx.post(api_url, json=payload, headers=headers, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        import json as _json

        return _json.loads(content)
    except Exception as e:  # noqa: BLE001
        raise ExtractionError(f"Vision model call failed: {e}") from e
    finally:
        # Image bytes go out of scope here; nothing is written to disk.
        del image_bytes


def extract_and_scrub(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    """Full pipeline: call model, scrub output, discard image.

    Returns the scrubbed field dict. Never raises on scrub (scrub always
    succeeds), but may raise ExtractionError if the model call itself
    fails (e.g. no API key configured).
    """
    raw = call_vision_model(image_bytes, mime_type=mime_type)
    return scrub_extracted_fields(raw)

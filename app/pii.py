"""Keep confidential identifiers OUT of the database, whatever the user (or a document) sends.

Every profile value that is saved goes through `clean_profile_value`. It enforces:
- only allow-listed profile fields can be stored (no "aadhaar_number", "password", ...);
- identifier-shaped values (Aadhaar, PAN, voter id, passport, bank account, phone, VID,
  IFSC, email, UPI id) are refused, even inside a field like "name";
- values are length-limited and have control characters removed.
This is the same rule the document scrubber follows, applied to everything typed or spoken too.
"""
from __future__ import annotations

import re

PROFILE_FIELDS = {
    "name", "date_of_birth", "age", "gender", "state", "district", "occupation", "income_band",
    "income_amount", "caste_category", "marital_status", "family_size", "land_holding",
    "disability_status", "document_type", "documents_have",
}
MAX_LEN = 120

_AADHAAR = re.compile(r"(?<!\d)\d{4}[\s\-]?\d{4}[\s\-]?\d{4}(?!\d)")
_LONG_DIGITS = re.compile(r"(?<!\d)\d{9,18}(?!\d)")                 # bank account / VID / long ids
_PHONE = re.compile(r"(?<!\d)(?:\+?91[\s\-]?)?[6-9]\d{9}(?!\d)")
_SPACED_DIGITS = re.compile(r"(?<!\d)(?:\d[\s\-.]?){10,18}(?!\d)")   # digits split by spaces or dashes
_PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b", re.I)
_VOTER = re.compile(r"\b[A-Z]{3}\d{7}\b", re.I)
_PASSPORT = re.compile(r"\b[A-PR-WY]\d{7}\b", re.I)
_IFSC = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b", re.I)
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_UPI = re.compile(r"\b[\w.\-]{2,}@[a-z]{2,}\b", re.I)
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

_PATTERNS = [("an Aadhaar number", _AADHAAR), ("a long account or ID number", _LONG_DIGITS), ("a phone number", _PHONE),
             ("a PAN", _PAN), ("a voter ID", _VOTER), ("a passport number", _PASSPORT), ("an IFSC code", _IFSC),
             ("an email address", _EMAIL), ("a UPI ID", _UPI)]


class PiiError(ValueError):
    """Raised for a value we refuse to store. The message never repeats the value."""


def find_identifier(text: str):
    """The kind of identifier found in `text` (e.g. 'an Aadhaar number'), or None."""
    for label, rx in _PATTERNS:
        if rx.search(text):
            return label
    # Same number written with spaces/dashes ("98765 43210", "+91 98765 43210", "1234 5678 9012").
    for m in _SPACED_DIGITS.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if len(digits) >= 10:
            if len(digits) == 12 and not digits.startswith("91"):
                return "an Aadhaar number"
            return "a phone or ID number"
    return None


def clean_profile_value(field: str, value):
    """Return a safe value to store, or raise PiiError. Numbers are checked after coercion."""
    if field not in PROFILE_FIELDS:
        raise PiiError(f"'{field}' is not something we store.")
    if isinstance(value, bool) or value is None:
        raise PiiError("That value is not valid.")
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, list):
        return [clean_profile_value(field, v) for v in value[:20]]
    text = _CTRL.sub("", str(value)).strip()
    if not text:
        raise PiiError("That value is empty.")
    if len(text) > MAX_LEN:
        raise PiiError("That value is too long.")
    kind = find_identifier(text)
    if kind:
        raise PiiError(f"For your safety we do not accept {kind}. Please remove it.")
    return text

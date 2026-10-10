"""Draft a scheme + rule from official source text.

The LLM never decides eligibility and never supplies dates:
- it only PROPOSES conditions; draft_clean.clean_conditions() drops anything without a
  quote that exists word-for-word in the source, and forces vague terms to "ambiguous";
- the last date to apply comes from deadlines.py (regex + exact quote), and is only
  suggested when the source names exactly one date;
- a draft ALWAYS lands as status "draft", verified=false, for an admin to approve.
With no API key a conservative placeholder is made, so nothing is ever invented.
"""
from __future__ import annotations

import datetime as dt
import json
import os

import httpx

from app.deadlines import extract_deadline_candidates, pick_deadline
from app.draft_clean import ALLOWED_FIELDS, clean_conditions, source_ref

SYSTEM_PROMPT = (
    "You read official Indian government scheme text and propose eligibility conditions. "
    "Return ONLY JSON: {\"name\": str, \"benefit\": str, \"category\": str, \"tags\": [str], "
    "\"conditions\": [{\"field\": str, \"op\": str, \"value\": any, \"type\": \"hard\"|\"ambiguous\", "
    "\"exact_quote\": str}]}. field must be one of: " + ", ".join(sorted(ALLOWED_FIELDS)) + ". "
    "op must be one of: = != < <= > >= in. exact_quote must be copied WORD FOR WORD from the text. "
    "Do not invent conditions, numbers or dates. If a condition is vague or depends on a local list, "
    "set type to ambiguous. Use gender values female/male, and age as a number. Omit anything you are not sure of."
)


def _wrap(scheme_id: str, url: str, top_quote: str, conditions: list) -> dict:
    today = dt.date.today()
    return {
        "scheme_id": scheme_id, "state": "ALL", "version": 1, "status": "draft", "verified": False,
        "effective_from": today.isoformat(), "review_by": (today + dt.timedelta(days=180)).isoformat(),
        "source": source_ref(url, top_quote), "conditions": conditions,
    }


def _placeholder(scheme_id: str, url: str, text: str) -> dict:
    first = next((l.strip() for l in text.splitlines() if l.strip()), text[:120])
    return _wrap(scheme_id, url, first, [{
        "field": "needs_manual_review", "op": "=", "value": True, "type": "ambiguous",
        "note": "Auto-drafted placeholder; an admin must author real conditions from the source text.",
        "source": source_ref(url, first)}])


def call_llm(source_text: str) -> dict:
    """One call to the configured chat-completions API; returns the parsed JSON object."""
    url = os.environ.get("RULE_DRAFTING_LLM_URL", "https://api.openai.com/v1/chat/completions")
    payload = {"model": os.environ.get("RULE_DRAFTING_LLM_MODEL", "gpt-4o-mini"), "temperature": 0,
               "response_format": {"type": "json_object"},
               "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": source_text[:24000]}]}
    key = os.environ["RULE_DRAFTING_LLM_API_KEY"]
    r = httpx.post(url, json=payload, headers={"Authorization": f"Bearer {key}"}, timeout=60.0)
    r.raise_for_status()
    return json.loads(r.json()["choices"][0]["message"]["content"])


def draft_scheme(scheme_id: str, source_url: str, source_text: str, llm=None) -> dict:
    """{rule, meta, deadline_candidates, deadline_suggestion, problems}.
    `llm` can be injected for tests; it takes the source text and returns a dict."""
    problems: list = []
    meta = {"name": None, "benefit": None, "category": None, "tags": []}
    conditions: list = []
    use = llm or (call_llm if os.environ.get("RULE_DRAFTING_LLM_API_KEY") else None)
    if use:
        try:
            out = use(source_text)
            meta = {"name": out.get("name"), "benefit": out.get("benefit"), "category": out.get("category"),
                    "tags": [t for t in (out.get("tags") or []) if isinstance(t, str)][:6]}
            conditions, problems = clean_conditions(out.get("conditions"), source_text, source_url)
        except Exception:  # noqa: BLE001 - a bad model reply must never stop the admin flow
            problems.append("The drafting service failed, so a safe placeholder was made instead.")
    rule = (_wrap(scheme_id, source_url, conditions[0]["source"]["exact_quote"], conditions)
            if conditions else _placeholder(scheme_id, source_url, source_text))
    cands = extract_deadline_candidates(source_text)
    return {"rule": rule, "meta": meta, "deadline_candidates": cands,
            "deadline_suggestion": pick_deadline(cands), "problems": problems}


def draft_rule_from_text(scheme_id: str, source_url: str, source_text: str) -> dict:
    """Backward-compatible helper: just the rule JSON."""
    return draft_scheme(scheme_id, source_url, source_text)["rule"]

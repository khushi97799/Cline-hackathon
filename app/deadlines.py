"""Application deadlines.

Dates are found and checked by CODE, never by an LLM. A deadline is only ever
shown if it comes with an exact quote from the official source, and the date in
that quote must match the stored date. If the source has no last date we say so
instead of guessing.
"""
from __future__ import annotations

import datetime as dt
import re

from app.textutil import contains_normalized, sentence_around

CLOSING_SOON_DAYS = 30

MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3, "april": 4, "apr": 4,
    "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7, "august": 8, "aug": 8,
    "september": 9, "sept": 9, "sep": 9, "october": 10, "oct": 10, "november": 11, "nov": 11,
    "december": 12, "dec": 12,
    "जनवरी": 1, "फरवरी": 2, "फ़रवरी": 2, "मार्च": 3, "अप्रैल": 4, "मई": 5, "जून": 6, "जुलाई": 7,
    "अगस्त": 8, "सितंबर": 9, "सितम्बर": 9, "अक्टूबर": 10, "नवंबर": 11, "नवम्बर": 11, "दिसंबर": 12, "दिसम्बर": 12,
}
_M = "|".join(re.escape(m) for m in sorted(MONTHS, key=len, reverse=True))
_DMY_TEXT = re.compile(rf"(\d{{1,2}})(?:st|nd|rd|th)?[\s\-]*(?:of\s+)?({_M})\.?,?[\s\-]*(\d{{4}})", re.I)
_MDY_TEXT = re.compile(rf"({_M})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})", re.I)
_NUM = re.compile(r"(?<!\d)(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})(?!\d)")   # day first (Indian style)
_ISO = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")

# Only wording that clearly means "last date to APPLY". Plain "valid till" is not a deadline.
_CUE = re.compile(
    r"last\s+(?:date|day)|closing\s+date|closes?\s+on|apply\s+(?:before|by|till|until)|"
    r"applications?\s+(?:can\s+be\s+|may\s+be\s+|must\s+be\s+|should\s+be\s+)?(?:submitted|received)\s+"
    r"(?:by|before|till|until|on\s+or\s+before)|deadline|due\s+date|"
    r"अंतिम\s+(?:तिथि|तारीख)|आखिरी\s+(?:तिथि|तारीख)",
    re.I,
)


def find_dates(text: str) -> list:
    """All real calendar dates in `text` as (date, start, end), in order, no overlaps."""
    found = []

    def add(m, y, mo, d):
        if 2000 <= y <= 2100:
            try:
                found.append((dt.date(y, mo, d), m.start(), m.end()))
            except ValueError:
                pass

    for m in _DMY_TEXT.finditer(text):
        add(m, int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1)))
    for m in _MDY_TEXT.finditer(text):
        add(m, int(m.group(3)), MONTHS[m.group(1).lower()], int(m.group(2)))
    for m in _NUM.finditer(text):
        add(m, int(m.group(3)), int(m.group(2)), int(m.group(1)))
    for m in _ISO.finditer(text):
        add(m, int(m.group(1)), int(m.group(2)), int(m.group(3)))
    found.sort(key=lambda x: x[1])
    out, last_end = [], -1
    for item in found:
        if item[1] >= last_end:
            out.append(item)
            last_end = item[2]
    return out


def parse_date(text: str):
    dates = find_dates(text)
    return dates[0][0] if dates else None


def extract_deadline_candidates(text: str) -> list:
    """Dates that sit in a sentence about the last date to apply, each with its exact quote."""
    cands, seen = [], set()
    for d, s, e in find_dates(text):
        quote = sentence_around(text, s, e)
        if not _CUE.search(quote):
            continue
        key = (d.isoformat(), quote)
        if key not in seen:
            seen.add(key)
            cands.append({"date": d.isoformat(), "quote": quote})
    return cands


def pick_deadline(cands: list):
    """Auto-suggest only when the source names exactly one date; otherwise a human decides."""
    if len({c["date"] for c in cands}) == 1:
        return cands[0]
    return None


def validate_deadline(deadline: dict, source_text: str) -> list:
    """Problems that stop a deadline being published (empty list = fine)."""
    problems = []
    try:
        d = dt.date.fromisoformat(str(deadline.get("date", "")))
    except ValueError:
        return ["The date is not a valid date (use YYYY-MM-DD)."]
    quote = (deadline.get("quote") or "").strip()
    if not quote:
        return ["A last date needs an exact quote from the official source."]
    if not contains_normalized(source_text or "", quote):
        problems.append("The quote for the last date is not found word-for-word in the source text.")
    if d not in {x[0] for x in find_dates(quote)}:
        problems.append("The date does not match any date written in the quote.")
    return problems


def deadline_status(deadline, today=None) -> dict:
    """open_ended | open | closing_soon | closed. The last date itself still counts as open."""
    today = today or dt.date.today()
    if not deadline or not deadline.get("date"):
        return {"state": "open_ended", "date": None, "days_left": None}
    try:
        d = dt.date.fromisoformat(deadline["date"])
    except ValueError:
        return {"state": "open_ended", "date": None, "days_left": None}
    days = (d - today).days
    state = "closed" if days < 0 else "closing_soon" if days <= CLOSING_SOON_DAYS else "open"
    return {"state": state, "date": d.isoformat(), "days_left": days}

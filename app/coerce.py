"""Normalise profile values coming from forms/documents so the rules
engine can compare them (e.g. "62" -> 62, "Female" -> "female")."""
from __future__ import annotations

import datetime as dt
import re

NUMERIC_FIELDS = {"age", "family_size", "land_holding", "income_amount"}
LOWER_FIELDS = {"gender", "occupation", "caste_category", "marital_status", "disability_status"}
UPPER_FIELDS = {"income_band"}
GENDER_MAP = {"f": "female", "female": "female", "woman": "female", "m": "male", "male": "male", "man": "male"}


def coerce_value(field: str, value):
    if field in NUMERIC_FIELDS:
        try:
            num = float(str(value).strip().replace(",", ""))
        except ValueError as e:
            raise ValueError(f"{field} must be a number") from e
        return int(num) if num.is_integer() else num
    if isinstance(value, str):
        v = value.strip()
        if field == "gender":
            return GENDER_MAP.get(v.lower(), v.lower())
        if field in LOWER_FIELDS:
            return v.lower()
        if field in UPPER_FIELDS:
            return v.upper()
        return v
    return value


def coerce_dict(values: dict) -> dict:
    out = {}
    for k, v in (values or {}).items():
        try:
            out[k] = coerce_value(k, v)
        except ValueError:
            continue  # drop unusable numeric values rather than store junk
    return out


def derive_age(dob: str, today: dt.date | None = None):
    """Compute age from DD-MM-YYYY, DD/MM/YYYY or YYYY-MM-DD. None if unparseable."""
    today = today or dt.date.today()
    s = str(dob).strip()
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", s)
    if m:
        y, mo, d = (int(x) for x in m.groups())
    else:
        m = re.match(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$", s)
        if not m:
            return None
        d, mo, y = (int(x) for x in m.groups())
    try:
        born = dt.date(y, mo, d)
    except ValueError:
        return None
    age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    return age if 0 <= age < 130 else None

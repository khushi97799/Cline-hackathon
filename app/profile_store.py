"""The single place where profile values are written. Everything goes through pii.clean_profile_value."""
from __future__ import annotations

from fastapi import HTTPException

from app.coerce import coerce_dict, coerce_value, derive_age
from app.pii import PROFILE_FIELDS, PiiError, clean_profile_value


def safe_value(field: str, value):
    """Coerce, then refuse anything confidential. Raises HTTP 400 with a kind message."""
    if field not in PROFILE_FIELDS:
        raise HTTPException(status_code=400, detail=f"'{field}' is not something we store.")
    try:
        if isinstance(value, str):
            clean_profile_value(field, value)          # check the raw text first (e.g. an Aadhaar typed as a number)
        return clean_profile_value(field, coerce_value(field, value))
    except PiiError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


def safe_dict(values: dict) -> dict:
    out = {}
    for k, v in (values or {}).items():
        if v is None or (isinstance(v, str) and not v.strip()):
            continue
        out[k] = safe_value(k, v)
    return out


def merge(person, verified: dict, user_stated: dict) -> None:
    """Save values on a person. Verified = confirmed from a document; user_stated = typed or spoken."""
    verified, user_stated = safe_dict(verified), safe_dict(user_stated)
    if "age" not in verified and verified.get("date_of_birth"):
        derived = derive_age(verified["date_of_birth"])
        if derived is not None:
            verified["age"] = derived
    profile, sources = dict(person.profile_json or {}), dict(person.field_sources or {})
    for f, v in verified.items():
        profile[f], sources[f] = v, "verified"
    for f, v in user_stated.items():
        profile[f], sources[f] = v, "user_stated"
    person.profile_json, person.field_sources = profile, sources

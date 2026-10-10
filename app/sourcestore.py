"""Where official source text lives on disk (data/raw/<scheme_id>.txt).

Admin approval checks every quote against this file, so whatever we fetch must be
saved here exactly as it was read.
"""
from __future__ import annotations

import re
from pathlib import Path

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
_SAFE = re.compile(r"^[a-z0-9][a-z0-9\-]{0,79}$")


def raw_path(scheme_id: str) -> Path:
    if not _SAFE.match(scheme_id or ""):
        raise ValueError("Scheme id may only contain lowercase letters, numbers and dashes.")
    return RAW_DIR / f"{scheme_id}.txt"


def save_source_text(scheme_id: str, text: str) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_path(scheme_id).write_text(text, encoding="utf-8")


def load_source_text(scheme_id: str):
    try:
        p = raw_path(scheme_id)
    except ValueError:
        return None
    return p.read_text(encoding="utf-8") if p.exists() else None

"""Small text helpers shared by the validator, deadline finder and drafting code."""
from __future__ import annotations

import hashlib
import re

_WS = re.compile(r"\s+")
MAX_QUOTE = 400


def normalize_ws(s: str) -> str:
    return _WS.sub(" ", s or "").strip()


def contains_normalized(text: str, quote: str) -> bool:
    """True if `quote` occurs in `text` ignoring differences in whitespace/line wrapping."""
    q = normalize_ws(quote)
    return bool(q) and q in normalize_ws(text)


def sha256_text(text: str) -> str:
    return hashlib.sha256(normalize_ws(text).encode("utf-8")).hexdigest()


def _ends_sentence(text: str, i: int) -> bool:
    ch = text[i]
    if ch in ".!?।":
        return i + 1 >= len(text) or text[i + 1] in " \n\t"
    if ch == "\n":
        j = i - 1
        while j >= 0 and text[j] in " \t\r":
            j -= 1
        if j < 0 or text[j] in ".!?।:;\n":
            return True
        nxt = text[i + 1:i + 3].lstrip(" \t")
        return nxt[:1] in ("", "\n", "-", "•", "*")
    return False


def sentence_around(text: str, start: int, end: int) -> str:
    """The sentence containing text[start:end], as an exact substring of `text`.

    Line breaks inside a wrapped sentence do not end it. Very long sentences are
    clipped around the match so a quote never exceeds MAX_QUOTE characters.
    """
    left = 0
    for i in range(start - 1, -1, -1):
        if _ends_sentence(text, i):
            left = i + 1
            break
    right = len(text)
    for j in range(end, len(text)):
        if _ends_sentence(text, j):
            right = j + 1 if text[j] != "\n" else j
            break
    if right - left > MAX_QUOTE:
        left = max(left, start - MAX_QUOTE // 2)
        right = min(right, end + MAX_QUOTE // 2)
    return text[left:right].strip()

"""Word matching that forgives typing mistakes. Pure functions, no database, no network."""
from __future__ import annotations

import re
import unicodedata

# \w does not count Indian vowel signs and the virama as letters (so "kisan" in Hindi would fall apart),
# so every Indic script block is listed explicitly: letters, vowel signs, virama, nukta, digits.
_WORD = re.compile(r"[A-Za-z0-9\u00c0-\u024f\u0900-\u0dff\u200c\u200d]+")


def norm(s: str) -> str:
    """Lower-case and remove accents, but keep Devanagari vowel signs (they change the word)."""
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c) or "\u0900" <= c <= "\u097f")
    return unicodedata.normalize("NFC", s)


def words(s: str) -> list:
    return [w.replace("\u200c", "").replace("\u200d", "") for w in _WORD.findall(norm(s))]


def edit_distance(a: str, b: str, limit: int) -> int:
    """Levenshtein distance; gives up early (returning limit + 1) once it must exceed `limit`."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if min(cur) > limit:
            return limit + 1
        prev = cur
    return prev[-1]


def typo_limit(n: int) -> int:
    """Short words must be exact, longer words may have 1-2 mistakes."""
    return 0 if n <= 3 else 1 if n <= 6 else 2


def word_score(q: str, candidates: list) -> float:
    """How well ONE typed word matches a list of words. 0 means no match.
    exact 10 > prefix (a single letter is enough) ~8 > inside a word 5 > typo ~3-4."""
    best = 0.0
    for w in candidates:
        if w == q:
            return 10.0
        if w.startswith(q):
            best = max(best, 8.0 - min(len(w) - len(q), 6) * 0.1)      # a closer length is a better prefix match
        elif len(q) >= 3 and q in w:
            best = max(best, 5.0)
        elif len(q) >= 4:
            lim = typo_limit(len(q))
            d = min(edit_distance(q, w, lim), edit_distance(q, w[: len(q)], lim))   # typo in the whole word or its start
            if d <= lim:
                best = max(best, 4.0 - 0.5 * d)
    return best

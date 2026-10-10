"""Scheme search that feels instant and forgives mistakes.

Each typed word must match something in the scheme (so "women pension" narrows down). A single letter
already gives suggestions (prefix match), typos are tolerated ("kisaan" finds kisan), and everyday words
in English, Hinglish and Hindi ("kheti", "bujurg", "महिला") point to the right "who is it for" tag.
Names count more than descriptions. Search only FINDS schemes; it never decides eligibility.
"""
from __future__ import annotations

from app.fuzzy import edit_distance, norm, typo_limit, word_score, words

# Words people actually type (English, Hinglish, Hindi) -> our tag ids.
SYNONYMS = {
    "farmer": ["farmer", "farmers", "kisan", "kisaan", "kheti", "krishi", "agriculture", "farming", "किसान", "खेती", "कृषि"],
    "women": ["woman", "women", "mahila", "mahilaon", "female", "ladies", "girl", "lady", "महिला", "महिलाएं", "औरत"],
    "senior": ["senior", "old", "elderly", "oldage", "vridh", "buzurg", "bujurg", "budhapa", "वृद्ध", "बुजुर्ग", "बुढ़ापा"],
    "student": ["student", "students", "scholarship", "padhai", "vidyarthi", "education", "school", "college", "छात्र", "विद्यार्थी", "पढ़ाई", "छात्रवृत्ति"],
    "health": ["health", "hospital", "ilaj", "ilaaj", "medical", "insurance", "swasthya", "स्वास्थ्य", "इलाज", "अस्पताल"],
    "housing": ["house", "housing", "ghar", "awas", "awaas", "makan", "आवास", "घर", "मकान"],
    "pension": ["pension", "pansion", "paisa", "monthly", "पेंशन"],
    "disability": ["disability", "disabled", "divyang", "handicap", "viklang", "दिव्यांग", "विकलांग"],
    "employment": ["job", "jobs", "employment", "rozgar", "naukri", "kaam", "रोज़गार", "रोजगार", "नौकरी"],
    "business": ["business", "loan", "vyapar", "udyog", "mudra", "व्यापार", "कारोबार", "ऋण", "लोन"],
    "child": ["child", "children", "bachche", "baccha", "kids", "बच्चे", "बच्चा"],
    "food": ["food", "ration", "anaj", "khana", "bhojan", "राशन", "अनाज", "भोजन"],
    "energy": ["gas", "lpg", "cooking", "cylinder", "chulha", "bijli", "electricity", "ujjwala", "गैस", "सिलेंडर", "बिजली", "उज्ज्वला"],
}
_SYN_NORM = {tag: [norm(s) for s in syns] for tag, syns in SYNONYMS.items()}


def synonym_tags(q: str) -> set:
    """Tag ids a typed word points to (exact, prefix of 2+ letters, or a small typo)."""
    found = set()
    for tag, syns in _SYN_NORM.items():
        for s in syns:
            if s == q or (len(q) >= 2 and s.startswith(q)) or (len(q) >= 4 and edit_distance(q, s, typo_limit(len(q))) <= typo_limit(len(q))):
                found.add(tag)
                break
    return found


def build_index(card: dict, tag_labels: dict) -> dict:
    tags = card.get("tags") or []
    labels = [lbl for t in tags for lbl in tag_labels.get(t, [])]
    return {"name": words(card["name"]), "tags": words(" ".join(tags + labels)),
            "meta": words(" ".join([card.get("category") or "", card.get("level") or "", card.get("state") or ""])),
            "body": words(card["benefit"]), "tagset": set(tags)}


def score_card(query_words: list, idx: dict):
    """Total score for the query, or None if any typed word matches nothing."""
    total = 0.0
    for q in query_words:
        s = max(word_score(q, idx["name"]) * 1.6, word_score(q, idx["tags"]) * 1.2,
                word_score(q, idx["meta"]), word_score(q, idx["body"]) * 0.7)
        if synonym_tags(q) & idx["tagset"]:
            s = max(s, 7.0)
        if s <= 0:
            return None
        total += s
    return total


def search(cards: list, query: str, tag_labels: dict | None = None) -> list:
    """Cards matching `query`, best first. An empty query returns the cards unchanged."""
    qw = words(query)
    if not qw:
        return cards
    scored = []
    for c in cards:
        s = score_card(qw, build_index(c, tag_labels or {}))
        if s is not None:
            scored.append((s, c))
    scored.sort(key=lambda x: (-x[0], x[1]["name"].lower()))
    return [c for _, c in scored]


def suggest(cards: list, query: str, tag_labels: dict | None = None, limit: int = 6) -> list:
    """The short list for the search-box dropdown, with why each one matched."""
    qw = words(query)
    out = []
    for c in search(cards, query, tag_labels)[:limit]:
        idx = build_index(c, tag_labels or {})
        if any(word_score(q, idx["name"]) for q in qw):
            why = "name"
        elif any((synonym_tags(q) & idx["tagset"]) or word_score(q, idx["tags"]) for q in qw):
            why = "tag"
        else:
            why = "text"
        out.append({"scheme_id": c["scheme_id"], "name": c["name"], "benefit": c["benefit"], "match": why, "tags": c.get("tags") or []})
    return out

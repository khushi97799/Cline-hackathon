"""Public scheme catalogue: tags, filtering, sorting, and the deadline shown to users.

Filters are plain data lookups. Eligibility is NOT decided here; that is only ever
done by the rules engine reading approved rules.
"""
from __future__ import annotations

import datetime as dt

from app.deadlines import deadline_status

# Fixed vocabulary so filters stay consistent. Labels live in i18n as "tag_<id>".
TAGS = ["farmer", "women", "senior", "student", "health", "housing", "pension", "disability",
        "employment", "business", "child", "food", "energy"]
LEVELS = ["central", "state"]

SORTS = {"relevance", "deadline", "recent", "name"}


def scheme_card(s, rule_verified: bool, today=None) -> dict:
    status = deadline_status(s.deadline_json, today)
    return {
        "scheme_id": s.scheme_id, "name": s.name, "benefit": s.benefit, "category": s.category,
        "level": s.level, "state": s.state, "tags": s.tags or [],
        "status": s.status, "verified": rule_verified,
        "last_verified": s.last_verified.isoformat() if s.last_verified else None,
        "official_link": (s.data_json or {}).get("source", {}).get("url"),
        "deadline": {**status, "quote": (s.deadline_json or {}).get("quote")},
        "added": s.created_at.date().isoformat() if s.created_at else None,
    }


def matches(card: dict, q=None, category=None, level=None, state=None, tag=None, verified=None,
            deadline=None) -> bool:
    if category and (card.get("category") or "") != category:
        return False
    if level and card.get("level") != level:
        return False
    if state and card.get("state") not in (state, "ALL", None):
        return False
    if tag and tag not in card["tags"]:
        return False
    if verified is not None and card["verified"] != verified:
        return False
    st = card["deadline"]["state"]
    if deadline == "open" and st == "closed":
        return False
    if deadline == "closing_soon" and st != "closing_soon":
        return False
    if deadline == "closed" and st != "closed":
        return False
    if deadline == "no_deadline" and st != "open_ended":
        return False
    return True


def sort_cards(cards: list, sort: str = "relevance") -> list:
    far = dt.date.max.isoformat()
    if sort == "deadline":      # soonest open deadline first, then no-deadline, closed last
        def key(c):
            st = c["deadline"]["state"]
            order = {"closing_soon": 0, "open": 0, "open_ended": 1, "closed": 2}[st]
            return (order, c["deadline"]["date"] or far, c["name"].lower())
        return sorted(cards, key=key)
    if sort == "recent":
        return sorted(cards, key=lambda c: c["added"] or "", reverse=True)
    if sort == "name":
        return sorted(cards, key=lambda c: c["name"].lower())
    # relevance: verified first, then closing soon, then the rest; closed always last
    def rel(c):
        st = c["deadline"]["state"]
        return (st == "closed", not c["verified"], st != "closing_soon", c["name"].lower())
    return sorted(cards, key=rel)

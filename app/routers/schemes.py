"""Scheme detail router: documents checklist, offices, printable packet.

Documents/offices/steps come ONLY from scheme data files (data/schemes/*.json
and data/offices.json) loaded into Scheme.data_json; this router never adds
offices, addresses, or steps of its own.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deadlines import deadline_status
from app.search import search, suggest
from app.tag_labels import TAG_LABELS
from app.deps import get_current_phone, get_optional_phone, owned_person
from app.models import Person, PhoneNumber, RuleVersion, Scheme

router = APIRouter(prefix="/api/schemes", tags=["schemes"])

ROOT = Path(__file__).resolve().parent.parent.parent
OFFICES_PATH = ROOT / "data" / "offices.json"


def _load_offices() -> dict:
    if not OFFICES_PATH.exists():
        return {}
    with open(OFFICES_PATH, "r", encoding="utf-8") as f:
        offices = json.load(f)
    return {o["office_id"]: o for o in offices}


@router.get("")
def list_schemes(
    q: str | None = None, category: str | None = None, level: str | None = None, state: str | None = None,
    tag: str | None = None, verified: bool | None = None, deadline: str | None = None,
    sort: str = "relevance", db: Session = Depends(get_db),
):
    """Public catalogue with filters. Draft schemes are never shown; a scheme whose
    source changed (needs_update) stays visible but is never marked verified."""
    from app.catalogue import LEVELS, TAGS, matches, scheme_card, sort_cards

    rows = db.query(Scheme).filter(Scheme.status.in_(("approved", "needs_update"))).all()
    approved = {r.scheme_id: r for r in db.query(RuleVersion).filter(RuleVersion.status == "approved").all()}
    cards = []
    for s in rows:
        rv = approved.get(s.scheme_id)
        ok = bool(rv and rv.verified and s.status == "approved")
        cards.append(scheme_card(s, ok))
    shown = [c for c in cards if matches(c, None, category, level, state, tag, verified, deadline)]
    if (q or "").strip():
        # Fuzzy search ranks by how well each word matches; keep that order unless a sort was asked for.
        found = search(shown, q, TAG_LABELS)
        shown = found if sort == "relevance" else sort_cards(found, sort)
    else:
        shown = sort_cards(shown, sort)
    return {
        "schemes": shown,
        "total": len(cards),
        "categories": sorted({c["category"] for c in cards if c["category"]}),
        "tags": [t for t in TAGS if any(t in c["tags"] for c in cards)],
        "states": sorted({c["state"] for c in cards if c["state"] and c["state"] != "ALL"}),
        "levels": LEVELS,
    }


@router.get("/suggest")
def suggest_schemes(q: str = "", db: Session = Depends(get_db)):
    """Live suggestions while typing: works from the first letter, tolerates typos."""
    from app.catalogue import scheme_card

    rows = db.query(Scheme).filter(Scheme.status.in_(("approved", "needs_update"))).all()
    cards = [scheme_card(s, False) for s in rows]
    return {"suggestions": suggest(cards, q[:60], TAG_LABELS)}


@router.get("/{scheme_id}/rule")
def get_scheme_rule(scheme_id: str, db: Session = Depends(get_db)):
    """Transparency: the approved conditions and the exact source quotes."""
    rv = (db.query(RuleVersion)
          .filter(RuleVersion.scheme_id == scheme_id, RuleVersion.status == "approved")
          .order_by(RuleVersion.version.desc()).first())
    if not rv:
        raise HTTPException(status_code=404, detail="No approved rule for this scheme")
    rule = rv.rule_json
    return {
        "scheme_id": scheme_id, "version": rv.version, "verified": rv.verified,
        "review_by": rule.get("review_by"), "source": rule.get("source"),
        "conditions": [
            {"field": c["field"], "op": c["op"], "value": c["value"], "type": c["type"],
             "note": c.get("note"), "quote": c.get("source", {}).get("exact_quote")}
            for c in rule.get("conditions", [])
        ],
    }


@router.get("/{scheme_id}")
def get_scheme_detail(
    scheme_id: str, person_id: str | None = None, db: Session = Depends(get_db),
    phone: PhoneNumber | None = Depends(get_optional_phone),
):
    scheme = db.query(Scheme).filter(Scheme.scheme_id == scheme_id).first()
    if not scheme:
        raise HTTPException(status_code=404, detail="Scheme not found")

    data = scheme.data_json or {}
    documents = data.get("documents", [])
    offices = _load_offices()

    profile = {}
    if person_id and phone is not None:
        person = db.query(Person).filter(Person.id == person_id).first()
        if person and (person.phone_number_id == phone.id or person.created_by_operator_id == phone.id):
            profile = person.profile_json or {}

    have_docs = set(profile.get("documents_have", []) or [])

    checklist = []
    for doc in documents:
        has_it = doc["doc_id"] in have_docs
        office = offices.get(doc.get("issuing_office_id"))
        checklist.append(
            {
                "doc_id": doc["doc_id"],
                "name": doc["name"],
                "have": has_it,
                "office": office,
                "what_to_carry": doc.get("what_to_carry", []),
                "form": doc.get("form"),
                "official_link": doc.get("official_link"),
                "steps": doc.get("steps", []),
                "confirm_before_you_go": True,
            }
        )

    return {
        "scheme_id": scheme.scheme_id,
        "name": scheme.name,
        "benefit": scheme.benefit,
        "status": scheme.status,
        "category": scheme.category,
        "level": scheme.level,
        "state": scheme.state,
        "tags": scheme.tags or [],
        "deadline": {**deadline_status(scheme.deadline_json), "quote": (scheme.deadline_json or {}).get("quote")},
        "official_link": data.get("source", {}).get("url"),
        "last_verified": scheme.last_verified.isoformat() if scheme.last_verified else None,
        "documents": checklist,
    }


@router.get("/{scheme_id}/packet")
def get_printable_packet(
    scheme_id: str, person=Depends(owned_person), db: Session = Depends(get_db),
    phone: PhoneNumber = Depends(get_current_phone),
):
    scheme = db.query(Scheme).filter(Scheme.scheme_id == scheme_id).first()
    if not scheme:
        raise HTTPException(status_code=404, detail="Scheme not found")

    detail = get_scheme_detail(scheme_id, person.id, db, phone)
    return {
        "scheme_name": scheme.name,
        "confirmed_values": person.profile_json or {},
        "documents_checklist": detail["documents"],
        "official_links": [d["official_link"] for d in detail["documents"] if d.get("official_link")],
    }

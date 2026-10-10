"""Results router: runs the deterministic rules engine for every scheme.

Never says "You qualify". Unverified schemes always downgrade
likely_qualifies to maybe_confirm_at_office (handled inside rules_engine).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deadlines import deadline_status
from app.deps import owned_person
from app.models import RuleVersion, Scheme
from app.rules_engine import evaluate
from app.schemas import SchemeResultCard

router = APIRouter(prefix="/api/results", tags=["results"])


@router.get("/{person_id}")
def get_results(person=Depends(owned_person), db: Session = Depends(get_db)):
    profile = person.profile_json or {}
    approved_rules = db.query(RuleVersion).filter(RuleVersion.status == "approved").all()  # one per scheme in practice

    cards = []
    for rv in approved_rules:
        scheme = db.query(Scheme).filter(Scheme.scheme_id == rv.scheme_id).first()
        if not scheme:
            continue
        # If the official source changed (needs_update) the rule is no longer trusted:
        # treat it as unverified so a confident result is never shown.
        rule = dict(rv.rule_json)
        trusted = bool(rv.verified) and scheme.status == "approved"
        if not trusted:
            rule["verified"] = False
        result = evaluate(rule, profile)
        status = deadline_status(scheme.deadline_json)
        cards.append(
            SchemeResultCard(
                scheme_id=scheme.scheme_id,
                name=scheme.name,
                benefit=scheme.benefit,
                outcome=result.outcome,
                verified_badge=trusted,
                last_verified=scheme.last_verified.isoformat() if scheme.last_verified else None,
                almost_eligible=result.almost_eligible,
                reasons=result.reasons,
                deadline={**status, "quote": (scheme.deadline_json or {}).get("quote")},
                needs_update=scheme.status == "needs_update",
            )
        )
    return {"results": [c.model_dump() for c in cards]}

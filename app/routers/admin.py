"""Admin dashboard, rule review, ingest-source router.

Approve requires: valid schema, every quote exists in the source text,
tests pass (schema+quote check enforced here; full pytest run is a CI/
daily-job concern, not re-run per click).
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_role
from app.models import AuditLog, ChangeTicket, RuleVersion, Scheme
from app.deadlines import validate_deadline
from app.schemas import RuleApprovalRequest
from app.sourcestore import load_source_text
from app.validator import quotes_exist_in_source, RuleValidationError, validate_schema

router = APIRouter(prefix="/api/admin", tags=["admin"])

ROOT = Path(__file__).resolve().parent.parent.parent
RAW_DIR = ROOT / "data" / "raw"


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    schemes = db.query(Scheme).all()
    return {
        "schemes": [
            {
                "scheme_id": s.scheme_id,
                "name": s.name,
                "status": s.status,
                "last_verified": s.last_verified.isoformat() if s.last_verified else None,
            }
            for s in schemes
        ]
    }


@router.get("/stats")
def stats(db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    from app.models import Person, Submission
    schemes = db.query(Scheme).all()
    by_status: dict = {}
    for s in schemes:
        by_status[s.status] = by_status.get(s.status, 0) + 1
    return {
        "schemes": len(schemes), "by_status": by_status,
        "open_tickets": db.query(ChangeTicket).filter(ChangeTicket.status == "open").count(),
        "drafts_waiting": db.query(RuleVersion).filter(RuleVersion.status == "draft").count(),
        "people": db.query(Person).count(),
        "submissions": db.query(Submission).count(),
    }


@router.get("/source/{scheme_id}")
def source_text(scheme_id: str, _=Depends(require_role("admin"))):
    text = load_source_text(scheme_id)
    if text is None:
        raise HTTPException(status_code=404, detail="No source text file for this scheme")
    return {"scheme_id": scheme_id, "text": text}


@router.post("/run-refresh")
def run_refresh(db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    from app.daily_refresh import run_daily_refresh
    return {"ok": True, "summary": run_daily_refresh(db)}


@router.get("/audit")
def audit(db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    rows = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(50).all()
    return {"entries": [{"action": r.action, "target": r.target, "actor_role": r.actor_role,
                         "at": r.created_at.isoformat()} for r in rows]}


@router.get("/rules/{scheme_id}")
def list_rule_versions(scheme_id: str, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    rows = db.query(RuleVersion).filter(RuleVersion.scheme_id == scheme_id).order_by(RuleVersion.version.desc()).all()
    return {"rule_versions": [
        {
            "id": r.id, "version": r.version, "status": r.status, "verified": r.verified,
            "review_by": r.review_by.isoformat() if r.review_by else None,
            "rule_json": r.rule_json,
        } for r in rows
    ]}


@router.post("/rules/review")
def review_rule(req: RuleApprovalRequest, db: Session = Depends(get_db), admin=Depends(require_role("admin"))):
    rv = db.query(RuleVersion).filter(RuleVersion.id == req.rule_version_id).first()
    if not rv:
        raise HTTPException(status_code=404, detail="Rule version not found")

    rule_json = req.edited_rule_json or rv.rule_json

    if not req.approve:
        rv.status = "rejected"
        db.add(rv)
        db.add(AuditLog(actor_role="admin", actor_id=admin.id, action="reject_rule", target=rv.id))
        db.commit()
        return {"ok": True, "status": "rejected"}

    try:
        validate_schema(rule_json)
    except RuleValidationError as e:
        raise HTTPException(status_code=400, detail=f"Schema invalid: {e}") from e

    if rule_json.get("scheme_id") != rv.scheme_id:
        raise HTTPException(status_code=400, detail="The rule's scheme_id does not match this scheme.")
    from app.draft_clean import ALLOWED_FIELDS

    bad = [c["field"] for c in rule_json["conditions"] if c["field"] not in ALLOWED_FIELDS]
    if bad:
        raise HTTPException(status_code=400, detail=f"Replace the placeholder condition(s) with real ones before approving: {sorted(set(bad))}")

    source_text = load_source_text(rv.scheme_id)
    missing = quotes_exist_in_source(rule_json, source_text=source_text)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Quotes not found verbatim in source: {missing}",
        )

    scheme = db.query(Scheme).filter(Scheme.scheme_id == rv.scheme_id).first()
    if scheme is None:
        raise HTTPException(status_code=404, detail="Scheme not found")
    if scheme.deadline_json:
        problems = validate_deadline(scheme.deadline_json, source_text or "")
        if problems:
            raise HTTPException(status_code=400, detail="Last date problem: " + " ".join(problems) + " Fix or clear the last date first.")

    # Only one approved version per scheme: retire the older ones.
    db.query(RuleVersion).filter(
        RuleVersion.scheme_id == rv.scheme_id, RuleVersion.status == "approved", RuleVersion.id != rv.id
    ).update({"status": "superseded"})

    rv.rule_json = rule_json
    rv.status = "approved"
    rv.verified = True
    rv.approved_by = admin.id
    rv.effective_from = dt.date.fromisoformat(rule_json["effective_from"])
    rv.review_by = dt.date.fromisoformat(rule_json["review_by"])
    db.add(rv)

    scheme.status = "approved"
    scheme.last_verified = dt.date.today()
    db.add(scheme)
    db.query(ChangeTicket).filter(ChangeTicket.draft_rule_version_id == rv.id).update({"status": "resolved"})

    db.add(AuditLog(actor_role="admin", actor_id=admin.id, action="approve_rule", target=rv.id))
    db.commit()
    return {"ok": True, "status": "approved"}


@router.get("/change-tickets")
def list_change_tickets(db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    rows = db.query(ChangeTicket).order_by(ChangeTicket.created_at.desc()).all()
    return {"change_tickets": [
        {
            "id": t.id, "scheme_id": t.scheme_id, "source_url": t.source_url,
            "status": t.status, "created_at": t.created_at.isoformat(),
        } for t in rows
    ]}

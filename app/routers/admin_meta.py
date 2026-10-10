"""Admin: filters (level, state, tags) and the last date to apply for a scheme.

A last date is only accepted together with an exact quote from the official source,
and the date must match a date written in that quote (checked by code)."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.catalogue import LEVELS, TAGS
from app.database import get_db
from app.deadlines import extract_deadline_candidates, validate_deadline
from app.deps import require_role
from app.models import AuditLog, Scheme
from app.sourcestore import load_source_text

router = APIRouter(prefix="/api/admin", tags=["admin"])


class MetaRequest(BaseModel):
    level: Optional[str] = None
    state: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    category: Optional[str] = None
    deadline_date: Optional[str] = None     # YYYY-MM-DD, or empty to clear
    deadline_quote: Optional[str] = None


@router.get("/options")
def options(_=Depends(require_role("admin"))):
    return {"tags": TAGS, "levels": LEVELS}


@router.get("/schemes/{scheme_id}/meta")
def get_meta(scheme_id: str, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    s = db.query(Scheme).filter(Scheme.scheme_id == scheme_id).first()
    if s is None:
        raise HTTPException(status_code=404, detail="Scheme not found")
    text = load_source_text(scheme_id) or ""
    return {"scheme_id": s.scheme_id, "name": s.name, "level": s.level, "state": s.state, "tags": s.tags or [],
            "category": s.category, "deadline": s.deadline_json,
            "deadline_candidates": extract_deadline_candidates(text), "has_source": bool(text)}


@router.put("/schemes/{scheme_id}/meta")
def set_meta(scheme_id: str, req: MetaRequest, db: Session = Depends(get_db), admin=Depends(require_role("admin"))):
    s = db.query(Scheme).filter(Scheme.scheme_id == scheme_id).first()
    if s is None:
        raise HTTPException(status_code=404, detail="Scheme not found")
    if req.level and req.level not in LEVELS:
        raise HTTPException(status_code=400, detail="Level must be central or state.")
    bad = [t for t in req.tags if t not in TAGS]
    if bad:
        raise HTTPException(status_code=400, detail=f"Unknown tag(s): {bad}")
    deadline = None
    if (req.deadline_date or "").strip():
        deadline = {"date": req.deadline_date.strip(), "quote": (req.deadline_quote or "").strip()}
        problems = validate_deadline(deadline, load_source_text(scheme_id) or "")
        if problems:
            raise HTTPException(status_code=400, detail=" ".join(problems))
    s.level, s.state = req.level or None, (req.state or "").strip() or None
    s.tags, s.deadline_json = req.tags, deadline
    if req.category is not None:
        s.category = req.category.strip() or None
    db.add(AuditLog(actor_role="admin", actor_id=admin.id, action="set_scheme_meta", target=scheme_id))
    db.commit()
    return {"ok": True}

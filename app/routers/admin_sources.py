"""Admin: add a new scheme from an official URL or pasted text, and manage the pages we
watch every day. Everything lands as a DRAFT; nothing is published without Approve."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_role
from app.discovery import create_draft_scheme, run_discovery
from app.models import AuditLog, RuleVersion, Scheme, SchemeSource
from app.rule_drafting import draft_scheme
from app.source_fetch import SourceFetchError, fetch_source, validate_source_url
from app.sourcestore import save_source_text

router = APIRouter(prefix="/api/admin", tags=["admin"])


class IngestRequest(BaseModel):
    scheme_id: Optional[str] = None      # existing scheme: add a new rule version; empty = new scheme
    title: Optional[str] = None
    url: Optional[str] = None
    text: Optional[str] = None


class SourceRequest(BaseModel):
    url: str
    scheme_id: Optional[str] = None      # empty = a discovery page/feed that lists schemes
    kind: str = "page"


@router.post("/ingest")
def ingest(req: IngestRequest, db: Session = Depends(get_db), admin=Depends(require_role("admin"))):
    text, url, title = (req.text or "").strip(), (req.url or "").strip(), (req.title or "").strip()
    if not text and not url:
        raise HTTPException(status_code=400, detail="Give an official web address or paste the official text.")
    sha = None
    if url and not text:
        try:
            res = fetch_source(url)
        except SourceFetchError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        text, url, sha = res.text, res.url, res.sha256
        title = title or res.title
    if len(text) < 80:
        raise HTTPException(status_code=400, detail="That text is too short to read a scheme from.")

    if req.scheme_id:
        scheme = db.query(Scheme).filter(Scheme.scheme_id == req.scheme_id).first()
        if scheme is None:
            raise HTTPException(status_code=404, detail="Scheme not found")
        d = draft_scheme(scheme.scheme_id, url or "pasted-text", text)
        latest = (db.query(RuleVersion).filter(RuleVersion.scheme_id == scheme.scheme_id)
                  .order_by(RuleVersion.version.desc()).first())
        version = (latest.version + 1) if latest else 1
        d["rule"]["version"] = version
        db.add(RuleVersion(scheme_id=scheme.scheme_id, version=version, status="draft", verified=False, rule_json=d["rule"]))
        save_source_text(scheme.scheme_id, text)
    else:
        scheme = create_draft_scheme(db, title or "New scheme", url or "pasted-text", text, kind="admin")
        d = draft_scheme(scheme.scheme_id, url or "pasted-text", text)
    if url and not db.query(SchemeSource).filter(SchemeSource.url == url).first():
        db.add(SchemeSource(scheme_id=scheme.scheme_id, url=url, kind="page", last_hash=sha))
    db.add(AuditLog(actor_role="admin", actor_id=admin.id, action="ingest_source", target=scheme.scheme_id))
    db.commit()
    return {"ok": True, "scheme_id": scheme.scheme_id, "problems": d["problems"],
            "deadline_candidates": d["deadline_candidates"], "deadline_suggestion": d["deadline_suggestion"]}


@router.get("/sources")
def list_sources(db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    rows = db.query(SchemeSource).order_by(SchemeSource.created_at.desc()).all()
    return {"sources": [{"id": r.id, "url": r.url, "scheme_id": r.scheme_id, "kind": r.kind, "active": r.active,
                         "last_checked": r.last_checked.isoformat() if r.last_checked else None,
                         "last_error": r.last_error} for r in rows]}


@router.post("/sources")
def add_source(req: SourceRequest, db: Session = Depends(get_db), admin=Depends(require_role("admin"))):
    try:
        url = validate_source_url(req.url)
    except SourceFetchError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if req.scheme_id and db.query(Scheme).filter(Scheme.scheme_id == req.scheme_id).first() is None:
        raise HTTPException(status_code=404, detail="Scheme not found")
    if db.query(SchemeSource).filter(SchemeSource.url == url).first():
        raise HTTPException(status_code=409, detail="We already watch this address.")
    db.add(SchemeSource(url=url, scheme_id=req.scheme_id or None, kind="feed" if req.kind == "feed" else "page"))
    db.add(AuditLog(actor_role="admin", actor_id=admin.id, action="add_source", target=req.scheme_id or "discovery"))
    db.commit()
    return {"ok": True}


@router.delete("/sources/{source_id}")
def remove_source(source_id: str, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    row = db.query(SchemeSource).filter(SchemeSource.id == source_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Source not found")
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.post("/discover")
def discover(db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    return run_discovery(db)

"""Daily job: re-read every scheme's official page, detect changes, find new schemes.

For each watched source:
  fetch -> plain text -> hash -> compare with the last hash.
  Unchanged:    only the "last checked" time moves.
  Changed:      save a snapshot, open a change ticket, mark the scheme needs_update (its
                results are downgraded to "confirm at the office"), draft an updated rule
                for the admin queue, and note if the last date to apply moved.
  Fetch failed: record the error and leave the scheme exactly as it was. A website being
                down must never change what citizens see.
Nothing here publishes anything: only an admin's Approve makes a draft live.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from app.deadlines import extract_deadline_candidates
from app.discovery import run_discovery
from app.models import ChangeTicket, RuleVersion, Scheme, SchemeSource
from app.rule_drafting import draft_scheme
from app.source_fetch import SourceFetchError, fetch_source
from app.sourcestore import save_source_text


def _deadline_note(scheme: Scheme, new_text: str) -> str:
    old = (scheme.deadline_json or {}).get("date")
    new = sorted({c["date"] for c in extract_deadline_candidates(new_text)})
    if not new and old:
        return f"The last date ({old}) is no longer found on the source page."
    if new and old and old not in new:
        return f"Last date on the page now reads {', '.join(new)} (we show {old}). Please check."
    if new and not old:
        return f"The page now mentions a last date: {', '.join(new)}."
    return ""


def _mark_changed(db: Session, scheme: Scheme, src: SchemeSource, res, llm=None) -> dict:
    latest = (db.query(RuleVersion).filter(RuleVersion.scheme_id == scheme.scheme_id)
              .order_by(RuleVersion.version.desc()).first())
    d = draft_scheme(scheme.scheme_id, src.url, res.text, llm=llm)
    version = (latest.version + 1) if latest else 1
    d["rule"]["version"] = version
    rv = RuleVersion(scheme_id=scheme.scheme_id, version=version, status="draft", verified=False, rule_json=d["rule"])
    db.add(rv)
    db.flush()
    note = "The official page changed. Review the updated draft."
    extra = _deadline_note(scheme, res.text)
    if extra:
        note += " " + extra
    if d["problems"]:
        note += " Auto-checks: " + " ".join(d["problems"])
    ticket = ChangeTicket(scheme_id=scheme.scheme_id, source_url=src.url, old_hash=src.last_hash, new_hash=res.sha256,
                          snapshot_text=res.text[:20000], status="open", draft_rule_version_id=rv.id, note=note)
    db.add(ticket)
    if scheme.status == "approved":
        scheme.status = "needs_update"
    db.add(scheme)
    # Keep the new text so the admin can check quotes against exactly what the page says now.
    save_source_text(scheme.scheme_id, res.text)
    return {"scheme_id": scheme.scheme_id, "changed": True, "ticket_id": ticket.id}


def run_daily_refresh(db: Session, fetcher=fetch_source, llm=None, discover: bool = True) -> list:
    """Returns one summary dict per watched scheme source (plus discovery results)."""
    summary: list = []
    now = dt.datetime.utcnow()
    watched = db.query(SchemeSource).filter(SchemeSource.active.is_(True), SchemeSource.scheme_id.isnot(None)).all()
    for src in watched:
        scheme = db.query(Scheme).filter(Scheme.scheme_id == src.scheme_id).first()
        if scheme is None:
            continue
        try:
            res = fetcher(src.url)
        except SourceFetchError as e:
            src.last_error, src.last_checked = str(e), now
            summary.append({"scheme_id": scheme.scheme_id, "changed": False, "error": str(e)})
            continue
        src.last_error, src.last_checked = None, now
        if src.last_hash is None:                      # first time we see this page: remember it
            src.last_hash = res.sha256
            summary.append({"scheme_id": scheme.scheme_id, "changed": False, "baseline": True})
            continue
        if res.sha256 == src.last_hash:
            summary.append({"scheme_id": scheme.scheme_id, "changed": False})
            continue
        summary.append(_mark_changed(db, scheme, src, res, llm=llm))
        src.last_hash = res.sha256
    db.commit()
    if discover:
        found = run_discovery(db, fetcher=fetcher, llm=llm)
        for sid in found["created"]:
            summary.append({"scheme_id": sid, "changed": True, "new": True})
        for err in found["errors"]:
            summary.append({"scheme_id": None, "changed": False, "error": err["error"], "url": err["url"]})
    return summary

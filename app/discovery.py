"""Find NEW schemes from official feeds/pages and put them in the admin queue.

Nothing found here is ever shown to citizens until an admin approves it. Discovery only
creates a *draft* scheme + a draft rule, with the source text saved so the admin can
check every quote against it.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from urllib.parse import urljoin

from sqlalchemy.orm import Session

from app.models import AuditLog, ChangeTicket, RuleVersion, Scheme, SchemeSource
from app.rule_drafting import draft_scheme
from app.source_fetch import SourceFetchError, fetch_source, host_allowed, validate_source_url
from app.sourcestore import save_source_text

_LINK = re.compile(r"""<a\s[^>]*href=["']([^"'#]+)["'][^>]*>(.*?)</a>""", re.I | re.S)
_TAGS = re.compile(r"<[^>]+>")
SCHEME_WORDS = re.compile(r"(yojana|yojna|scheme|abhiyan|mission|pension|scholarship|सम्मान|योजना|अभियान)", re.I)
MAX_NEW_PER_RUN = 10


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:60] or "scheme"


def parse_feed(xml_text: str) -> list:
    """[(title, link)] from an RSS or Atom feed."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    out = []
    for item in root.iter():
        tag = item.tag.split("}")[-1]
        if tag not in ("item", "entry"):
            continue
        title = link = ""
        for ch in item:
            t = ch.tag.split("}")[-1]
            if t == "title":
                title = (ch.text or "").strip()
            elif t == "link":
                link = (ch.attrib.get("href") or ch.text or "").strip()
        if title and link:
            out.append((title, link))
    return out


def parse_listing(html: str, base_url: str) -> list:
    """[(title, absolute_link)] for links that look like schemes, on allowed hosts only."""
    from urllib.parse import urlparse

    out, seen = [], set()
    for href, inner in _LINK.findall(html):
        title = " ".join(_TAGS.sub(" ", inner).split())
        link = urljoin(base_url, href.strip())
        host = urlparse(link).hostname or ""
        if len(title) < 6 or not SCHEME_WORDS.search(title) or not host_allowed(host) or link in seen:
            continue
        seen.add(link)
        out.append((title, link))
    return out


def create_draft_scheme(db: Session, title: str, url: str, text: str, kind: str = "discovered", llm=None) -> Scheme:
    """Create a draft scheme + draft rule + change ticket from fetched official text."""
    base = slugify(title)
    scheme_id, n = base, 2
    while db.query(Scheme).filter(Scheme.scheme_id == scheme_id).first():
        scheme_id, n = f"{base}-{n}", n + 1
    d = draft_scheme(scheme_id, url, text, llm=llm)
    meta = d["meta"]
    scheme = Scheme(
        scheme_id=scheme_id, name=(meta.get("name") or title)[:200], benefit=(meta.get("benefit") or "To be confirmed from the official source")[:500],
        category=meta.get("category"), status="draft", level=None, state=None, tags=meta.get("tags") or [],
        data_json={"scheme_id": scheme_id, "name": title, "documents": [], "source": {"url": url}},
    )
    db.add(scheme)
    db.flush()
    save_source_text(scheme_id, text)
    rv = RuleVersion(scheme_id=scheme_id, version=1, status="draft", verified=False, rule_json=d["rule"])
    db.add(rv)
    db.flush()
    note = "New scheme found from an official source. Check every condition and the last date, then approve."
    if d["problems"]:
        note += " Auto-checks: " + " ".join(d["problems"])
    db.add(ChangeTicket(scheme_id=scheme_id, source_url=url, new_hash=None, snapshot_text=text[:20000],
                        status="open", draft_rule_version_id=rv.id, note=note))
    db.add(AuditLog(actor_role="system", action=f"discover_{kind}", target=scheme_id))
    return scheme


def run_discovery(db: Session, fetcher=fetch_source, llm=None) -> dict:
    """Look at every active feed/page source and draft any scheme link we have not seen."""
    created, errors = [], []
    known = {s.url for s in db.query(SchemeSource).all()}
    for src in db.query(SchemeSource).filter(SchemeSource.active.is_(True), SchemeSource.scheme_id.is_(None)).all():
        try:
            res = fetcher(src.url)
            items = parse_feed(res.text) if res.content_type in ("application/rss+xml", "application/atom+xml", "application/xml", "text/xml") \
                else parse_listing(res.html or res.text, res.url)
            src.last_error = None
        except SourceFetchError as e:
            src.last_error = str(e)
            errors.append({"url": src.url, "error": str(e)})
            continue
        finally:
            import datetime as dt
            src.last_checked = dt.datetime.utcnow()
        for title, link in items:
            if len(created) >= MAX_NEW_PER_RUN:
                break
            try:
                link = validate_source_url(link)
            except SourceFetchError:
                continue
            if link in known:
                continue
            try:
                page = fetcher(link)
            except SourceFetchError as e:
                errors.append({"url": link, "error": str(e)})
                continue
            known.add(link)
            scheme = create_draft_scheme(db, title, page.url, page.text, llm=llm)
            db.add(SchemeSource(scheme_id=scheme.scheme_id, url=page.url, kind="page", last_hash=page.sha256))
            created.append(scheme.scheme_id)
    db.commit()
    return {"created": created, "errors": errors}

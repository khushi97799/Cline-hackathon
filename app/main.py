"""FastAPI application entrypoint."""
from __future__ import annotations

import os
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import get_db, init_db, SessionLocal
from app.daily_refresh import run_daily_refresh
from app.routers import admin, admin_meta, admin_sources, auth, consent, csc, daily_job, documents, my_data, my_data_erase, questions, results, roles, schemes, submission

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"

_scheduler_stop = threading.Event()


def _daily_scheduler_loop():
    """Simple in-process scheduler: runs the daily refresh once per day at
    the configured local time (DAILY_REFRESH_TIME, HH:MM)."""
    target = os.environ.get("DAILY_REFRESH_TIME", "03:00")
    try:
        target_h, target_m = (int(x) for x in target.split(":"))
    except ValueError:
        target_h, target_m = 3, 0

    last_run_date = None
    while not _scheduler_stop.is_set():
        now = datetime.now()
        if now.hour == target_h and now.minute == target_m and last_run_date != now.date():
            db = SessionLocal()
            try:
                run_daily_refresh(db)
            finally:
                db.close()
            last_run_date = now.date()
        _scheduler_stop.wait(30)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    thread = threading.Thread(target=_daily_scheduler_loop, daemon=True)
    thread.start()
    yield
    _scheduler_stop.set()


app = FastAPI(title="Scheme Sniper", lifespan=lifespan)

# The website and API share one origin, so no CORS is needed. Other origins can be allowed
# explicitly with CORS_ORIGINS=https://a.example,https://b.example (never "*" with cookies).
_origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip() and o.strip() != "*"]
if _origins:
    app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_credentials=True,
                       allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Content-Type", "X-Requested-With", "Authorization"])


@app.middleware("http")
async def security_layer(request, call_next):
    from fastapi.responses import JSONResponse

    from app.security import apply_headers, csrf_ok

    if not csrf_ok(request):
        resp = JSONResponse({"detail": "Blocked: missing security header."}, status_code=403)
    else:
        resp = await call_next(request)
    apply_headers(request, resp)
    return resp

app.include_router(auth.router)
app.include_router(consent.router)
app.include_router(documents.router)
app.include_router(questions.router)
app.include_router(results.router)
app.include_router(schemes.router)
app.include_router(admin.router)
app.include_router(roles.router)
app.include_router(my_data.router)
app.include_router(my_data_erase.router)
app.include_router(admin_sources.router)
app.include_router(admin_meta.router)
app.include_router(csc.router)
app.include_router(submission.router)
app.include_router(daily_job.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/languages")
def get_languages():
    import json

    with open(ROOT / "data" / "languages.json", "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/i18n/{lang_code}")
def get_i18n(lang_code: str):
    import json
    import re

    if not re.fullmatch(r"[a-z]{2,3}", lang_code):
        lang_code = "en"
    i18n_dir = ROOT / "app" / "i18n"

    def load(name: str) -> dict:
        p = i18n_dir / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

    # English is the fallback for every missing key; ".ui.json" holds the
    # extra website strings so each file stays small.
    parts = ("", ".ui", ".ui2", ".ui3", ".ui4")
    data: dict = {}
    for suffix in parts:
        data.update(load(f"en{suffix}.json"))
    if lang_code != "en":
        for suffix in parts:
            data.update(load(f"{lang_code}{suffix}.json"))
    return {"strings": data, "preview": lang_code not in ("en", "hi")}


@app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], include_in_schema=False)
async def api_not_found(rest: str):
    """Unknown API paths answer with JSON, never with the HTML 404 page."""
    from fastapi.responses import JSONResponse

    return JSONResponse({"detail": "Not Found"}, status_code=404)


@app.exception_handler(404)
async def not_found(request, exc):
    """Browsers get the friendly 404 page; API callers keep the JSON error."""
    from fastapi.responses import FileResponse, JSONResponse

    if not request.url.path.startswith("/api") and (STATIC_DIR / "404.html").exists():
        return FileResponse(STATIC_DIR / "404.html", status_code=404)
    return JSONResponse({"detail": getattr(exc, "detail", "Not Found")}, status_code=404)


if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


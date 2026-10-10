"""Protected endpoint to trigger the daily refresh job (used by
.github/workflows/daily.yml via a bearer-style shared token, and locally
by the in-process scheduler at DAILY_REFRESH_TIME)."""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.daily_refresh import run_daily_refresh
from app.database import get_db

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("/daily-refresh")
def trigger_daily_refresh(
    x_daily_refresh_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    expected = os.environ.get("DAILY_REFRESH_TOKEN")
    if not expected or x_daily_refresh_token != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing refresh token")
    summary = run_daily_refresh(db)
    return {"ok": True, "summary": summary}

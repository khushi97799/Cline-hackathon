"""Cookie-based login (HttpOnly) and browser security headers.

The login token lives in an HttpOnly cookie, so JavaScript can never read it: a script
injected into a page cannot steal it. The cookie is SameSite=Lax and Secure in production.
CSRF: state-changing requests must also carry the custom X-Requested-With header, which a
cross-site form cannot send. `Authorization: Bearer` is still accepted for API clients/tests.
"""
from __future__ import annotations

import os

from fastapi import Request, Response

from app.otp_providers import is_production

COOKIE = "ss_session"
CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "SchemeSniper"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
MAX_AGE = 60 * 60 * 12


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(COOKIE, token, max_age=MAX_AGE, httponly=True, samesite="lax", secure=is_production(), path="/")


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE, path="/")


def csrf_ok(request: Request) -> bool:
    """Cookie-authenticated writes need the custom header. Bearer-token calls are not
    cookie-authenticated, so they are not subject to CSRF."""
    if request.method in SAFE_METHODS:
        return True
    if request.headers.get("authorization"):
        return True
    if COOKIE not in request.cookies:
        return True                      # nothing to forge: the request is anonymous anyway
    return request.headers.get(CSRF_HEADER) == CSRF_VALUE


CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
       "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")


def apply_headers(request: Request, response: Response) -> None:
    h = response.headers
    h["Content-Security-Policy"] = CSP
    h["X-Content-Type-Options"] = "nosniff"
    h["X-Frame-Options"] = "DENY"
    h["Referrer-Policy"] = "no-referrer"
    h["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=()"
    if is_production():
        h["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    # Personal data must never be cached by the browser or a proxy.
    if request.url.path.startswith("/api/") and not request.url.path.startswith(("/api/schemes", "/api/languages", "/api/i18n")):
        h["Cache-Control"] = "no-store"
        h["Pragma"] = "no-cache"

"""Authentication helpers: OTP generation + hashing, JWT, phone handling.

OTP codes are never stored in plain text; only an HMAC of the code is saved.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import os
import secrets

from jose import jwt

from app.models import Role
from app.otp_providers import OtpProvider, is_production

JWT_ALGO = "HS256"
JWT_EXPIRE_MINUTES = 60 * 12
OTP_TTL_MINUTES = 5
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_SECONDS = 30
OTP_DAILY_LIMIT = 10          # codes per phone per rolling 24h
TEST_OTP_CODE = os.environ.get("TEST_OTP_CODE", "123456")

VALID_ROLES = {r.value for r in Role}
# Only citizens can sign themselves up. Staff roles must be granted by an admin
# (or via ADMIN_PHONES for the very first admin).
SELF_SERVICE_ROLES = {"citizen"}


def _secret() -> str:
    secret = os.environ.get("JWT_SECRET", "")
    if not secret:
        if is_production():
            raise RuntimeError("JWT_SECRET must be set when APP_ENV=production")
        secret = "dev-insecure-secret-change-me"
    return secret


def generate_otp_code(provider: OtpProvider) -> str:
    if provider.is_test_mode:
        return TEST_OTP_CODE
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp(phone: str, code: str) -> str:
    return hmac.new(_secret().encode(), f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()


def check_otp(phone: str, code: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_otp(phone, code), stored_hash)


def otp_expiry() -> dt.datetime:
    return dt.datetime.utcnow() + dt.timedelta(minutes=OTP_TTL_MINUTES)


def create_access_token(phone_id: str, role: str) -> str:
    expire = dt.datetime.utcnow() + dt.timedelta(minutes=JWT_EXPIRE_MINUTES)
    return jwt.encode({"sub": phone_id, "role": role, "exp": expire}, _secret(), algorithm=JWT_ALGO)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, _secret(), algorithms=[JWT_ALGO])


def normalize_phone(phone: str) -> str:
    digits = "".join(c for c in phone if c.isdigit())
    return digits[-10:] if len(digits) >= 10 else digits


def admin_phones() -> set:
    raw = os.environ.get("ADMIN_PHONES", "")
    return {normalize_phone(p) for p in raw.split(",") if p.strip()}

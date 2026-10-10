"""Phone + OTP login. Citizens self-register; staff roles must be pre-approved."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.auth import (
    OTP_DAILY_LIMIT, OTP_MAX_ATTEMPTS, OTP_RESEND_SECONDS, VALID_ROLES,
    admin_phones, check_otp, create_access_token, generate_otp_code, hash_otp, normalize_phone, otp_expiry,
)
from app.database import get_db
from app.deps import get_current_phone
from app.security import clear_session_cookie, set_session_cookie
from app.models import OtpCode, PhoneNumber, Role
from app.otp_providers import OtpDeliveryError, get_otp_provider
from app.schemas import SendOtpRequest, TokenResponse, VerifyOtpRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _utcnow() -> dt.datetime:
    return dt.datetime.utcnow()


def _resolve_phone_row(db: Session, phone: str, role: str) -> PhoneNumber:
    """Find or create the phone row and enforce who may use which role."""
    row = db.query(PhoneNumber).filter(PhoneNumber.phone == phone).first()
    if row is None:
        if role == "citizen":
            row = PhoneNumber(phone=phone, role=Role.citizen)
        elif role == "admin" and phone in admin_phones():
            row = PhoneNumber(phone=phone, role=Role.admin)
        else:
            raise HTTPException(status_code=403, detail="This number is not approved for that role. Ask an admin to add it.")
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    if role != row.role.value:
        if role == "admin" and phone in admin_phones():
            row.role = Role.admin          # bootstrap admin allow-list
            db.commit()
        else:
            raise HTTPException(status_code=403, detail=f"This number is registered as {row.role.value}. Choose that tab.")
    return row


@router.post("/send-otp")
def send_otp(req: SendOtpRequest, db: Session = Depends(get_db)):
    if req.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")
    phone = normalize_phone(req.phone)
    if len(phone) != 10 or phone[0] not in "6789":
        raise HTTPException(status_code=400, detail="Enter a valid 10-digit Indian mobile number")

    try:
        provider = get_otp_provider()
    except OtpDeliveryError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    row = _resolve_phone_row(db, phone, req.role)
    now = _utcnow()
    last = db.query(OtpCode).filter(OtpCode.phone_number_id == row.id).order_by(OtpCode.created_at.desc()).first()
    if last and (now - last.created_at).total_seconds() < OTP_RESEND_SECONDS:
        wait = int(OTP_RESEND_SECONDS - (now - last.created_at).total_seconds()) + 1
        raise HTTPException(status_code=429, detail=f"Please wait {wait} seconds before asking for a new code.")
    since = now - dt.timedelta(days=1)
    if db.query(OtpCode).filter(OtpCode.phone_number_id == row.id, OtpCode.created_at > since).count() >= OTP_DAILY_LIMIT:
        raise HTTPException(status_code=429, detail="Too many codes requested today. Try again tomorrow.")

    code = generate_otp_code(provider)
    # A new code invalidates any earlier unused ones.
    db.query(OtpCode).filter(OtpCode.phone_number_id == row.id, OtpCode.consumed.is_(False)).update({"consumed": True})
    db.add(OtpCode(phone_number_id=row.id, code=hash_otp(phone, code), purpose="login", expires_at=otp_expiry()))
    db.commit()

    try:
        provider.send(phone, code)
    except OtpDeliveryError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    out = {"ok": True, "test_mode": provider.is_test_mode, "resend_in": OTP_RESEND_SECONDS, "message": "Code sent by SMS."}
    if provider.is_test_mode:
        out["message"] = f"TEST MODE: your code is {code}"
    return out


@router.post("/verify-otp", response_model=TokenResponse)
def verify_otp(req: VerifyOtpRequest, response: Response, db: Session = Depends(get_db)):
    phone = normalize_phone(req.phone)
    row = db.query(PhoneNumber).filter(PhoneNumber.phone == phone).first()
    if not row:
        raise HTTPException(status_code=400, detail="Request a code first.")
    otp = (db.query(OtpCode).filter(OtpCode.phone_number_id == row.id, OtpCode.consumed.is_(False))
           .order_by(OtpCode.created_at.desc()).first())
    if not otp:
        raise HTTPException(status_code=400, detail="No active code. Request a new one.")
    if otp.expires_at < _utcnow():
        otp.consumed = True
        db.commit()
        raise HTTPException(status_code=400, detail="This code has expired. Request a new one.")
    if not check_otp(phone, req.code.strip(), otp.code):
        otp.attempts = (otp.attempts or 0) + 1
        left = OTP_MAX_ATTEMPTS - otp.attempts
        if left <= 0:
            otp.consumed = True
        db.commit()
        if left <= 0:
            raise HTTPException(status_code=429, detail="Too many wrong attempts. Request a new code.")
        raise HTTPException(status_code=400, detail=f"Incorrect code. {left} tries left.")
    if req.role != row.role.value:
        raise HTTPException(status_code=403, detail=f"This number is registered as {row.role.value}.")

    otp.consumed = True
    db.commit()
    token = create_access_token(row.id, row.role.value)
    set_session_cookie(response, token)        # HttpOnly: page scripts can never read it
    return TokenResponse(access_token=token, role=row.role.value, test_mode=get_otp_provider().is_test_mode)


@router.post("/logout")
def logout(response: Response):
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/me")
def me(phone: PhoneNumber = Depends(get_current_phone)):
    """Who is logged in. The phone number is masked and never returned in full."""
    return {"role": phone.role.value, "phone_hint": phone.phone[:2] + "******" + phone.phone[-2:]}

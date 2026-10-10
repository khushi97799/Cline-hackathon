"""SIMULATED online submission router. See app/submission.py for the
honesty notice: this never calls a real government API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_phone, owned_person
from app.models import Person, PhoneNumber, Submission
from app.schemas import SubmitApplicationRequest
from app.submission import advance_status, SubmissionError, submit_application

router = APIRouter(prefix="/api/submissions", tags=["submissions"])


def _own_person(db: Session, phone: PhoneNumber, person_id: str) -> Person:
    """The caller must own the person: the citizen themself, or the CSC operator who created them."""
    person = db.query(Person).filter(Person.id == person_id).first()
    owns = person is not None and (person.phone_number_id == phone.id or person.created_by_operator_id == phone.id)
    if not owns:
        # 404 for both "missing" and "not yours" so ids cannot be probed.
        raise HTTPException(status_code=404, detail="Person not found")
    return person


@router.post("/request-code")
def request_submit_code(
    phone: PhoneNumber = Depends(get_current_phone), db: Session = Depends(get_db),
):
    """Send a fresh confirmation code to the logged-in user's own phone."""
    import datetime as dt

    from app.auth import OTP_RESEND_SECONDS, generate_otp_code, hash_otp, otp_expiry
    from app.models import OtpCode
    from app.otp_providers import OtpDeliveryError, get_otp_provider

    try:
        provider = get_otp_provider()
    except OtpDeliveryError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    last = (db.query(OtpCode).filter(OtpCode.phone_number_id == phone.id, OtpCode.purpose == "submit")
            .order_by(OtpCode.created_at.desc()).first())
    if last and (dt.datetime.utcnow() - last.created_at).total_seconds() < OTP_RESEND_SECONDS:
        raise HTTPException(status_code=429, detail="Please wait a few seconds before asking for a new code.")
    code = generate_otp_code(provider)
    db.query(OtpCode).filter(OtpCode.phone_number_id == phone.id, OtpCode.purpose == "submit",
                             OtpCode.consumed.is_(False)).update({"consumed": True})
    db.add(OtpCode(phone_number_id=phone.id, code=hash_otp(phone.phone, code), purpose="submit", expires_at=otp_expiry()))
    db.commit()
    try:
        provider.send(phone.phone, code)
    except OtpDeliveryError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    msg = f"TEST MODE: your code is {code}" if provider.is_test_mode else "Code sent by SMS."
    return {"ok": True, "test_mode": provider.is_test_mode, "message": msg}


def _consume_submit_code(db: Session, phone: PhoneNumber, code: str) -> None:
    import datetime as dt

    from app.auth import OTP_MAX_ATTEMPTS, check_otp
    from app.models import OtpCode

    otp = (db.query(OtpCode).filter(OtpCode.phone_number_id == phone.id, OtpCode.purpose == "submit",
                                    OtpCode.consumed.is_(False)).order_by(OtpCode.created_at.desc()).first())
    if not otp or otp.expires_at < dt.datetime.utcnow():
        raise HTTPException(status_code=400, detail="Ask for a confirmation code first (it may have expired).")
    if not check_otp(phone.phone, (code or "").strip(), otp.code):
        otp.attempts = (otp.attempts or 0) + 1
        if otp.attempts >= OTP_MAX_ATTEMPTS:
            otp.consumed = True
        db.commit()
        raise HTTPException(status_code=400, detail="Incorrect code.")
    otp.consumed = True
    db.commit()


@router.post("")
def submit(
    req: SubmitApplicationRequest,
    phone: PhoneNumber = Depends(get_current_phone),
    db: Session = Depends(get_db),
):
    person = _own_person(db, phone, req.person_id)
    _consume_submit_code(db, phone, req.otp_code)

    try:
        receipt = submit_application(
            person_id=person.id,
            scheme_id=req.scheme_id,
            profile=person.profile_json or {},
            submitted_by_role=phone.role.value,
        )
    except SubmissionError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    row = Submission(
        person_id=person.id,
        scheme_id=req.scheme_id,
        arn=receipt["arn"],
        status=receipt["status"],
        submitted_by_role=phone.role.value,
    )
    db.add(row)
    db.commit()
    return receipt


@router.get("/track/{arn}")
def track(arn: str, db: Session = Depends(get_db)):
    """Public status lookup by reference number (no personal data returned)."""
    row = db.query(Submission).filter(Submission.arn == arn).first()
    if not row:
        raise HTTPException(status_code=404, detail="Reference number not found")
    return {
        "arn": row.arn, "scheme_id": row.scheme_id, "status": row.status, "simulated": True,
        "submitted_at": row.created_at.isoformat() + "Z",
        "updated_at": row.updated_at.isoformat() + "Z",
        "steps": ["SUBMITTED", "UNDER_SCRUTINY", "APPROVED"],
    }


@router.get("/person/{person_id}")
def person_submissions(person=Depends(owned_person), db: Session = Depends(get_db)):
    rows = db.query(Submission).filter(Submission.person_id == person.id).all()
    return {"submissions": [{"arn": r.arn, "scheme_id": r.scheme_id, "status": r.status} for r in rows]}


@router.get("/queue")
def operator_queue(
    phone: PhoneNumber = Depends(get_current_phone), db: Session = Depends(get_db)
):
    """CSC operator's view of submitted applications they handled, with
    simulated live tracking statuses."""
    if phone.role.value not in ("csc_operator", "admin"):
        raise HTTPException(status_code=403, detail="Insufficient role")

    people_ids = [p.id for p in db.query(Person).filter(Person.created_by_operator_id == phone.id).all()]
    rows = db.query(Submission).filter(Submission.person_id.in_(people_ids)).all() if people_ids else []
    return {
        "submissions": [
            {"id": r.id, "person_id": r.person_id, "scheme_id": r.scheme_id, "arn": r.arn, "status": r.status}
            for r in rows
        ]
    }


@router.post("/{submission_id}/advance")
def advance(submission_id: str, phone: PhoneNumber = Depends(get_current_phone), db: Session = Depends(get_db)):
    """Advance a simulated submission's status (SUBMITTED -> UNDER_SCRUTINY
    -> APPROVED). Demo-only state machine."""
    if phone.role.value not in ("csc_operator", "admin"):
        raise HTTPException(status_code=403, detail="Insufficient role")
    row = db.query(Submission).filter(Submission.id == submission_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Submission not found")
    if phone.role.value == "csc_operator":
        mine = db.query(Person).filter(Person.id == row.person_id, Person.created_by_operator_id == phone.id).first()
        if not mine:
            raise HTTPException(status_code=404, detail="Submission not found")
    row.status = advance_status(row.status)
    db.add(row)
    db.commit()
    return {"ok": True, "status": row.status}

"""Download or erase my data: export, delete one person, delete my whole account."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_phone, owned_person
from app.models import AuditLog, Consent, OtpCode, Person, PhoneNumber, Submission
from app.routers.my_data import people_of, view
from app.security import clear_session_cookie

router = APIRouter(prefix="/api/me", tags=["my-data"])


def erase_person(db: Session, person: Person) -> None:
    db.query(Consent).filter(Consent.person_id == person.id).delete()
    db.query(Submission).filter(Submission.person_id == person.id).delete()
    db.delete(person)


@router.get("/export")
def export_my_data(response: Response, phone: PhoneNumber = Depends(get_current_phone), db: Session = Depends(get_db)):
    """A downloadable copy of everything stored about the caller. The phone number is masked."""
    people = []
    for p in people_of(db, phone):
        subs = db.query(Submission).filter(Submission.person_id == p.id).all()
        people.append({**view(db, p), "applications": [{"reference": s.arn, "scheme": s.scheme_id, "status": s.status} for s in subs]})
    response.headers["Content-Disposition"] = 'attachment; filename="my-scheme-sniper-data.json"'
    return {"exported_at": dt.datetime.utcnow().isoformat() + "Z", "role": phone.role.value,
            "phone_hint": phone.phone[:2] + "******" + phone.phone[-2:], "people": people,
            "note": "We never store document images, Aadhaar numbers or audio."}


@router.delete("/people/{person_id}")
def delete_person(person=Depends(owned_person), db: Session = Depends(get_db)):
    erase_person(db, person)
    db.commit()
    return {"ok": True}


@router.delete("/account")
def delete_account(response: Response, phone: PhoneNumber = Depends(get_current_phone), db: Session = Depends(get_db)):
    """Erase the caller completely: every person they own, their login codes and their phone number.
    Staff accounts are removed by an admin instead, so admin actions stay accountable."""
    if phone.role.value != "citizen":
        raise HTTPException(status_code=403, detail="Staff accounts are removed by an admin.")
    for p in people_of(db, phone):
        erase_person(db, p)
    db.query(OtpCode).filter(OtpCode.phone_number_id == phone.id).delete()
    db.add(AuditLog(actor_role="citizen", actor_id=None, action="delete_account", target="self"))
    db.delete(phone)
    db.commit()
    clear_session_cookie(response)
    return {"ok": True}

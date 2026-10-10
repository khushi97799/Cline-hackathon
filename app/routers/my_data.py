"""See and change what is stored about me: values, name, consents.

Citizens see their own profile; CSC operators see the people they created. Ownership is checked
on every call, and a missing record and "not yours" look the same (404).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_phone, owned_person
from app.models import Consent, Person, PhoneNumber
from app.pii import PROFILE_FIELDS
from app.profile_store import merge, safe_value

router = APIRouter(prefix="/api/me", tags=["my-data"])


class FieldEdit(BaseModel):
    value: str | int | float


class NameEdit(BaseModel):
    name: str


class ConsentEdit(BaseModel):
    save_profile: bool
    notifications: bool = False


def people_of(db: Session, phone: PhoneNumber) -> list:
    q = db.query(Person)
    if phone.role.value == "csc_operator":
        return q.filter(Person.created_by_operator_id == phone.id).all()
    return q.filter(Person.phone_number_id == phone.id).all()


def latest_consent(db: Session, person_id: str):
    return db.query(Consent).filter(Consent.person_id == person_id).order_by(Consent.recorded_at.desc()).first()


def view(db: Session, p: Person) -> dict:
    c = latest_consent(db, p.id)
    return {"id": p.id, "display_name": p.display_name, "language": p.language, "profile": p.profile_json or {},
            "field_sources": p.field_sources or {}, "saved": bool(p.saved),
            "consent": {"save_profile": bool(c and c.save_profile), "notifications": bool(c and c.notifications)},
            "created_at": p.created_at.isoformat() if p.created_at else None}


@router.get("/people")
def my_people(phone: PhoneNumber = Depends(get_current_phone), db: Session = Depends(get_db)):
    return {"people": [view(db, p) for p in people_of(db, phone)], "role": phone.role.value}


@router.get("/people/{person_id}")
def my_person(person=Depends(owned_person), db: Session = Depends(get_db)):
    return view(db, person)


@router.put("/people/{person_id}/fields/{field}")
def edit_field(field: str, body: FieldEdit, person=Depends(owned_person), db: Session = Depends(get_db)):
    """Change one value. An edited value is 'user_stated' because it no longer comes from a document."""
    if field not in PROFILE_FIELDS:
        raise HTTPException(status_code=404, detail="Unknown field")
    merge(person, {}, {field: body.value})
    db.add(person)
    db.commit()
    return view(db, person)


@router.delete("/people/{person_id}/fields/{field}")
def delete_field(field: str, person=Depends(owned_person), db: Session = Depends(get_db)):
    if field not in PROFILE_FIELDS:
        raise HTTPException(status_code=404, detail="Unknown field")
    profile, sources = dict(person.profile_json or {}), dict(person.field_sources or {})
    profile.pop(field, None)
    sources.pop(field, None)
    if field == "date_of_birth" and sources.get("age") == "verified":     # that age was derived from this value
        profile.pop("age", None)
        sources.pop("age", None)
    person.profile_json, person.field_sources = profile, sources
    db.add(person)
    db.commit()
    return view(db, person)


@router.put("/people/{person_id}/name")
def rename(body: NameEdit, person=Depends(owned_person), db: Session = Depends(get_db)):
    person.display_name = safe_value("name", body.name) if body.name.strip() else None
    db.add(person)
    db.commit()
    return view(db, person)


@router.put("/people/{person_id}/consent")
def change_consent(body: ConsentEdit, person=Depends(owned_person), db: Session = Depends(get_db)):
    """Give or withdraw the optional consents at any time (each change is recorded)."""
    prev = latest_consent(db, person.id)
    db.add(Consent(person_id=person.id, find_schemes=bool(prev.find_schemes) if prev else True,
                   save_profile=body.save_profile, notifications=body.notifications))
    person.saved = body.save_profile
    db.add(person)
    db.commit()
    return view(db, person)

"""Consent + person creation router.

Finding schemes is required; saving profile and notifications are
separate optional opt-ins. Each person (including ones created by a CSC
operator) needs their own recorded consent.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_phone, owned_person
from app.models import Consent, Person, PhoneNumber
from app.profile_store import safe_value

LANGS = {"en", "hi", "as", "bn", "brx", "doi", "gu", "kn", "ks", "kok", "mai", "ml", "mni", "mr", "ne", "or", "pa", "sa", "sat", "sd", "ta", "te", "ur"}
from app.schemas import ConsentRequest, CreatePersonRequest

router = APIRouter(prefix="/api/persons", tags=["persons"])


@router.post("")
def create_person(
    req: CreatePersonRequest,
    phone: PhoneNumber = Depends(get_current_phone),
    db: Session = Depends(get_db),
):
    """Create a person profile.

    If the caller is a citizen, the person is linked to their own phone.
    If the caller is a csc_operator, the person is linked to the operator
    as creator, so the operator can later see only people they created.
    """
    name = safe_value("name", req.display_name) if (req.display_name or "").strip() else None
    person = Person(language=req.language if req.language in LANGS else "en", display_name=name)
    if phone.role.value == "citizen":
        person.phone_number_id = phone.id
    elif phone.role.value == "csc_operator":
        person.created_by_operator_id = phone.id
    else:
        raise HTTPException(status_code=403, detail="Admins do not create citizen profiles")

    db.add(person)
    db.commit()
    db.refresh(person)
    return {"person_id": person.id}


@router.post("/consent")
def record_consent(
    req: ConsentRequest, phone: PhoneNumber = Depends(get_current_phone), db: Session = Depends(get_db),
):
    if not req.find_schemes:
        raise HTTPException(
            status_code=400, detail="Consent to find schemes is required to continue"
        )
    person = db.query(Person).filter(Person.id == req.person_id).first()
    if person is None or not (person.phone_number_id == phone.id or person.created_by_operator_id == phone.id):
        raise HTTPException(status_code=404, detail="Person not found")

    consent = Consent(
        person_id=person.id,
        find_schemes=req.find_schemes,
        save_profile=req.save_profile,
        notifications=req.notifications,
    )
    person.saved = req.save_profile
    db.add(consent)
    db.commit()
    return {"ok": True}


@router.get("/{person_id}")
def get_person(person=Depends(owned_person)):
    return {
        "id": person.id, "display_name": person.display_name, "language": person.language,
        "profile": person.profile_json or {}, "field_sources": person.field_sources or {},
    }


@router.post("/{person_id}/remove-field")
def remove_field(field: str, person=Depends(owned_person), db: Session = Depends(get_db)):
    profile = dict(person.profile_json or {})
    sources = dict(person.field_sources or {})
    profile.pop(field, None)
    sources.pop(field, None)
    person.profile_json, person.field_sources = profile, sources
    db.add(person)
    db.commit()
    return {"ok": True}


@router.delete("/{person_id}")
def delete_my_data(person=Depends(owned_person), db: Session = Depends(get_db)):
    """Delete-my-data button: removes the person profile, consents and submissions."""
    from app.models import Submission

    db.query(Consent).filter(Consent.person_id == person.id).delete()
    db.query(Submission).filter(Submission.person_id == person.id).delete()
    db.delete(person)
    db.commit()
    return {"ok": True}

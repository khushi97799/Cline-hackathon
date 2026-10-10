"""CSC operator router: operator can only see people they created."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_role
from app.models import Person

router = APIRouter(prefix="/api/csc", tags=["csc"])


@router.get("/people")
def list_my_people(db: Session = Depends(get_db), operator=Depends(require_role("csc_operator"))):
    rows = db.query(Person).filter(Person.created_by_operator_id == operator.id).all()
    return {
        "people": [
            {"id": p.id, "display_name": p.display_name, "language": p.language, "saved": p.saved}
            for p in rows
        ]
    }


@router.get("/people/{person_id}")
def get_my_person(person_id: str, db: Session = Depends(get_db), operator=Depends(require_role("csc_operator"))):
    person = (
        db.query(Person)
        .filter(Person.id == person_id, Person.created_by_operator_id == operator.id)
        .first()
    )
    if not person:
        raise HTTPException(status_code=404, detail="Person not found or not created by you")
    return {
        "id": person.id,
        "display_name": person.display_name,
        "language": person.language,
        "profile": person.profile_json,
        "field_sources": person.field_sources,
    }

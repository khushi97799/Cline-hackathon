"""Next-question + answer router. Question selection is deterministic code,
never the LLM."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.profile_store import merge
from app.database import get_db
from app.deps import get_current_phone, owned_person
from app.models import Person, PhoneNumber, RuleVersion
from app.questions import select_next_question
from app.schemas import AnswerQuestionRequest, NextQuestionResponse

router = APIRouter(prefix="/api/questions", tags=["questions"])


def _approved_rules(db: Session) -> list:
    rows = db.query(RuleVersion).filter(RuleVersion.status == "approved").all()
    return [r.rule_json for r in rows]


@router.get("/next/{person_id}", response_model=NextQuestionResponse)
def next_question(person=Depends(owned_person), db: Session = Depends(get_db)):
    rules = _approved_rules(db)
    spec = select_next_question(rules, person.profile_json or {})
    if spec is None:
        return NextQuestionResponse(done=True, question=None)
    return NextQuestionResponse(done=False, question=spec)


@router.post("/answer")
def answer_question(
    req: AnswerQuestionRequest, phone: PhoneNumber = Depends(get_current_phone), db: Session = Depends(get_db),
):
    person = db.query(Person).filter(Person.id == req.person_id).first()
    if person is None or not (person.phone_number_id == phone.id or person.created_by_operator_id == phone.id):
        raise HTTPException(status_code=404, detail="Person not found")

    merge(person, {}, {req.field: req.value})
    db.add(person)
    db.commit()
    profile = person.profile_json
    return {"ok": True, "profile": profile}

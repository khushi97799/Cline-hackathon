"""Shared FastAPI dependencies: current user/role extraction, role guards."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Header, Request, status
from sqlalchemy.orm import Session

from app.auth import decode_access_token
from app.database import get_db
from app.models import PhoneNumber
from app.security import COOKIE


def _token_from(request: Request, authorization):
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1]
    return request.cookies.get(COOKIE)


def get_current_phone(
    request: Request, authorization: str | None = Header(default=None), db: Session = Depends(get_db)
) -> PhoneNumber:
    token = _token_from(request, authorization)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_access_token(token)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from e

    phone = db.query(PhoneNumber).filter(PhoneNumber.id == payload.get("sub")).first()
    if not phone:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown user")
    return phone


def get_optional_phone(
    request: Request, authorization: str | None = Header(default=None), db: Session = Depends(get_db)
) -> PhoneNumber | None:
    """Like get_current_phone but returns None for anonymous visitors."""
    try:
        return get_current_phone(request, authorization, db)
    except HTTPException:
        return None


def owned_person(
    person_id: str,
    phone: PhoneNumber = Depends(get_current_phone),
    db: Session = Depends(get_db),
):
    """Return the Person only if the caller owns it: the citizen themself,
    or the CSC operator who created them. Everyone else gets 404 (so ids
    cannot be probed)."""
    from app.models import Person

    person = db.query(Person).filter(Person.id == person_id).first()
    if person is None or not (person.phone_number_id == phone.id or person.created_by_operator_id == phone.id):
        raise HTTPException(status_code=404, detail="Person not found")
    return person


def require_role(*roles: str):
    def checker(phone: PhoneNumber = Depends(get_current_phone)) -> PhoneNumber:
        if phone.role.value not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return phone

    return checker

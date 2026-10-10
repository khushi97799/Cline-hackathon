"""Admin-only role management: approve CSC operators and extra admins."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import normalize_phone
from app.database import get_db
from app.deps import require_role
from app.models import AuditLog, PhoneNumber, Role

router = APIRouter(prefix="/api/admin/roles", tags=["admin"])


class GrantRoleRequest(BaseModel):
    phone: str
    role: str


def _mask(phone: str) -> str:
    return phone[:2] + "******" + phone[-2:]


@router.get("")
def list_staff(db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    rows = db.query(PhoneNumber).filter(PhoneNumber.role != Role.citizen).all()
    return {"staff": [{"id": r.id, "phone": _mask(r.phone), "role": r.role.value} for r in rows]}


@router.post("")
def grant_role(req: GrantRoleRequest, db: Session = Depends(get_db), admin=Depends(require_role("admin"))):
    if req.role not in ("csc_operator", "admin"):
        raise HTTPException(status_code=400, detail="Role must be csc_operator or admin")
    phone = normalize_phone(req.phone)
    if len(phone) != 10 or phone[0] not in "6789":
        raise HTTPException(status_code=400, detail="Enter a valid 10-digit Indian mobile number")
    row = db.query(PhoneNumber).filter(PhoneNumber.phone == phone).first()
    if row is None:
        db.add(PhoneNumber(phone=phone, role=Role(req.role)))
    else:
        row.role = Role(req.role)
    db.add(AuditLog(actor_role="admin", actor_id=admin.id, action=f"grant_{req.role}", target=_mask(phone)))
    db.commit()
    return {"ok": True}

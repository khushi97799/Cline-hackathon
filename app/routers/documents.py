"""Document upload + extraction + confirm router.

The image is sent to the vision model, fields are scrubbed in code, and
the image bytes are discarded immediately after extraction -- never
written to disk or the database.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.profile_store import merge
from app.database import get_db
from app.deps import get_current_phone
from app.models import Person, PhoneNumber
from app.schemas import ConfirmFieldsRequest, ExtractResponse
from app.vision_extract import ExtractionError, extract_and_scrub

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/extract", response_model=ExtractResponse)
async def extract_document(file: UploadFile = File(...), phone: PhoneNumber = Depends(get_current_phone)):
    # Login is required so the paid vision API cannot be used anonymously.
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload an image file.")
    image_bytes = await file.read()
    if len(image_bytes) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image is too large (limit 8 MB).")
    try:
        fields = extract_and_scrub(image_bytes, mime_type=file.content_type or "image/jpeg")
    except ExtractionError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    finally:
        # Ensure no reference to the image bytes is retained.
        del image_bytes
    return ExtractResponse(fields=fields, rejected_fields=[])


@router.post("/confirm")
def confirm_fields(
    req: ConfirmFieldsRequest, phone: PhoneNumber = Depends(get_current_phone), db: Session = Depends(get_db),
):
    """Store confirmed (verified) and user-stated field values on the person.

    Confirmed document values are "verified"; typed or spoken values are
    "user_stated". This endpoint merges both into the person's profile.
    """
    person = db.query(Person).filter(Person.id == req.person_id).first()
    if person is None or not (person.phone_number_id == phone.id or person.created_by_operator_id == phone.id):
        raise HTTPException(status_code=404, detail="Person not found")

    merge(person, req.verified_fields, req.user_stated_fields)
    db.add(person)
    db.commit()
    profile, sources = person.profile_json, person.field_sources
    return {"ok": True, "profile": profile, "field_sources": sources}

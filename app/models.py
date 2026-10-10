"""SQLAlchemy models.

Hard rule: phone numbers live in their own table (PhoneNumber), separate
from any profile data. Profile data (Person) never stores the phone
number directly; it links via phone_number_id only when the user has
explicitly opted in to save (see Person.saved).

No Aadhaar numbers, document images, or raw audio are ever stored here.
"""
import datetime as dt
import enum
import uuid

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum, ForeignKey, Integer, JSON, String, Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> dt.datetime:
    return dt.datetime.utcnow()


class Role(str, enum.Enum):
    citizen = "citizen"
    csc_operator = "csc_operator"
    admin = "admin"


class PhoneNumber(Base):
    """Phone numbers are kept strictly separate from profile data."""
    __tablename__ = "phone_numbers"

    id = Column(String, primary_key=True, default=_uuid)
    phone = Column(String, unique=True, nullable=False, index=True)
    role = Column(Enum(Role), nullable=False, default=Role.citizen)
    created_at = Column(DateTime, default=_now)

    otp_codes = relationship("OtpCode", back_populates="phone_number", cascade="all,delete-orphan")


class OtpCode(Base):
    __tablename__ = "otp_codes"

    id = Column(String, primary_key=True, default=_uuid)
    phone_number_id = Column(String, ForeignKey("phone_numbers.id"), nullable=False)
    code = Column(String, nullable=False)
    purpose = Column(String, nullable=False, default="login")
    expires_at = Column(DateTime, nullable=False)
    consumed = Column(Boolean, default=False)
    attempts = Column(Integer, default=0)  # wrong guesses; locks the code at the limit
    created_at = Column(DateTime, default=_now)

    phone_number = relationship("PhoneNumber", back_populates="otp_codes")


class Person(Base):
    """Profile data. Never contains phone number or raw identity numbers.

    created_by_operator_id is set when a CSC operator created this person
    on behalf of a citizen; operators can only see persons they created.
    """
    __tablename__ = "persons"

    id = Column(String, primary_key=True, default=_uuid)
    phone_number_id = Column(String, ForeignKey("phone_numbers.id"), nullable=True)
    created_by_operator_id = Column(String, ForeignKey("phone_numbers.id"), nullable=True)
    display_name = Column(String, nullable=True)
    saved = Column(Boolean, default=False)  # opted in to persist beyond session
    language = Column(String, default="en")
    profile_json = Column(JSON, default=dict)  # confirmed/user_stated field values
    field_sources = Column(JSON, default=dict)  # field -> "verified" | "user_stated"
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class Consent(Base):
    __tablename__ = "consents"

    id = Column(String, primary_key=True, default=_uuid)
    person_id = Column(String, ForeignKey("persons.id"), nullable=False)
    find_schemes = Column(Boolean, nullable=False, default=False)  # required
    save_profile = Column(Boolean, nullable=False, default=False)  # optional
    notifications = Column(Boolean, nullable=False, default=False)  # optional
    recorded_at = Column(DateTime, default=_now)


class Scheme(Base):
    __tablename__ = "schemes"

    scheme_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    benefit = Column(String, nullable=False)
    category = Column(String, nullable=True)
    status = Column(String, nullable=False, default="draft")
    data_json = Column(JSON, nullable=False, default=dict)  # full scheme data incl. documents
    last_verified = Column(Date, nullable=True)
    # Level of government + who it is for. Filled by an admin when approving.
    level = Column(String, nullable=True)            # central | state
    state = Column(String, nullable=True)            # ALL or a state name
    tags = Column(JSON, nullable=True)               # e.g. ["farmer", "women", "senior"]
    # Last date to apply, only ever stored with an exact quote from the source:
    # {"date": "YYYY-MM-DD", "quote": "..."}. Empty = the source gives no last date.
    deadline_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)


class SchemeSource(Base):
    """An official web page we watch for a scheme (or a discovery feed)."""
    __tablename__ = "scheme_sources"

    id = Column(String, primary_key=True, default=_uuid)
    scheme_id = Column(String, ForeignKey("schemes.scheme_id"), nullable=True)
    url = Column(String, nullable=False, unique=True)
    kind = Column(String, nullable=False, default="page")   # page | feed
    last_hash = Column(String, nullable=True)
    last_checked = Column(DateTime, nullable=True)
    last_error = Column(String, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=_now)


class RuleVersion(Base):
    __tablename__ = "rule_versions"

    id = Column(String, primary_key=True, default=_uuid)
    scheme_id = Column(String, ForeignKey("schemes.scheme_id"), nullable=False)
    version = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="draft")
    verified = Column(Boolean, nullable=False, default=False)
    rule_json = Column(JSON, nullable=False)
    effective_from = Column(Date, nullable=True)
    review_by = Column(Date, nullable=True)
    approved_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=_now)


class ChangeTicket(Base):
    __tablename__ = "change_tickets"

    id = Column(String, primary_key=True, default=_uuid)
    scheme_id = Column(String, ForeignKey("schemes.scheme_id"), nullable=False)
    source_url = Column(String, nullable=False)
    old_hash = Column(String, nullable=True)
    new_hash = Column(String, nullable=True)
    snapshot_text = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="open")
    draft_rule_version_id = Column(String, ForeignKey("rule_versions.id"), nullable=True)
    # What changed, in plain words, so the admin can review it quickly.
    note = Column(String, nullable=True)
    created_at = Column(DateTime, default=_now)


class AuditLog(Base):
    """Audit log for admin/system actions only. Never logs personal data."""
    __tablename__ = "audit_log"

    id = Column(String, primary_key=True, default=_uuid)
    actor_role = Column(String, nullable=False)
    actor_id = Column(String, nullable=True)
    action = Column(String, nullable=False)
    target = Column(String, nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=_now)


class Submission(Base):
    """SIMULATED government submission record. This is a demo/simulation
    only -- it does NOT call any real government API. See app/submission.py.
    """
    __tablename__ = "submissions"

    id = Column(String, primary_key=True, default=_uuid)
    person_id = Column(String, ForeignKey("persons.id"), nullable=False)
    scheme_id = Column(String, ForeignKey("schemes.scheme_id"), nullable=False)
    arn = Column(String, nullable=False, unique=True)
    status = Column(String, nullable=False, default="SUBMITTED")
    submitted_by_role = Column(String, nullable=False)  # citizen | csc_operator
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

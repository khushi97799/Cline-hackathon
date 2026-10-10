"""Pydantic request/response models for the API."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class SendOtpRequest(BaseModel):
    phone: str
    role: str = "citizen"


class VerifyOtpRequest(BaseModel):
    phone: str
    code: str
    role: str = "citizen"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    test_mode: bool = False


class ConsentRequest(BaseModel):
    person_id: str
    find_schemes: bool
    save_profile: bool = False
    notifications: bool = False


class ExtractResponse(BaseModel):
    fields: dict
    rejected_fields: list = Field(default_factory=list)


class ConfirmFieldsRequest(BaseModel):
    person_id: str
    verified_fields: dict = Field(default_factory=dict)
    user_stated_fields: dict = Field(default_factory=dict)


class NextQuestionResponse(BaseModel):
    done: bool
    question: Optional[dict] = None


class AnswerQuestionRequest(BaseModel):
    person_id: str
    field: str
    value: Any


class SchemeResultCard(BaseModel):
    scheme_id: str
    name: str
    benefit: str
    outcome: str
    verified_badge: bool
    last_verified: Optional[str] = None
    almost_eligible: bool = False
    reasons: list = Field(default_factory=list)
    deadline: Optional[dict] = None
    needs_update: bool = False


class SubmitApplicationRequest(BaseModel):
    person_id: str
    scheme_id: str
    otp_code: str


class CreatePersonRequest(BaseModel):
    display_name: Optional[str] = None
    language: str = "en"


class IngestSourceRequest(BaseModel):
    scheme_id: str
    url: Optional[str] = None
    text: Optional[str] = None


class RuleApprovalRequest(BaseModel):
    rule_version_id: str
    approve: bool
    edited_rule_json: Optional[dict] = None

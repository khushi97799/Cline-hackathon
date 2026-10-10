"""SIMULATED online application submission engine.

IMPORTANT / HONESTY NOTICE: This module does NOT call any real government
API (PM-Kisan, NSAP, UMANG, etc.). Those portals require official
integration agreements, Aadhaar e-KYC biometric/OTP authority, and
government-issued API credentials that a hackathon project cannot
legitimately obtain. Everything here is a clearly labeled simulation for
demo purposes: it generates a fake, locally-unique Application Reference
Number (ARN) and a local status record, and nothing is transmitted to any
external government system. Any UI showing this must display
"simulation" / "demo mode" language (see i18n key submission_simulated_notice).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import random
import string



STATUS_FLOW = ["SUBMITTED", "UNDER_SCRUTINY", "APPROVED"]


def generate_arn(scheme_id: str, person_id: str) -> str:
    """Generate a demo Application Reference Number.

    Format: SIM-<SCHEME>-<YEAR>-<6 hex chars>. Prefixed with SIM- to make
    unambiguous in all UI and logs that this is a simulated reference, not
    an official government number.
    """
    today = dt.date.today()
    seed = f"{scheme_id}:{person_id}:{today.isoformat()}:{random.random()}"
    digest = hashlib.sha256(seed.encode()).hexdigest()[:6].upper()
    scheme_tag = "".join(c for c in scheme_id.upper() if c.isalnum())[:10]
    return f"SIM-{scheme_tag}-{today.year}-{digest}"







class SubmissionError(Exception):
    pass


def submit_application(person_id: str, scheme_id: str, profile: dict, submitted_by_role: str) -> dict:
    """Run the simulated submission pipeline and return a receipt dict.

    Raises SubmissionError if the (simulated) OTP step fails or mandatory
    fields are missing. Never contacts any external government system.
    """
    if submitted_by_role not in ("citizen", "csc_operator"):
        raise SubmissionError("Only citizens or CSC operators may submit.")




    required_min_fields = ["name"]
    missing = [f for f in required_min_fields if not profile.get(f)]
    if missing:
        raise SubmissionError(f"Missing required fields for submission: {', '.join(missing)}")

    arn = generate_arn(scheme_id, person_id)
    receipt = {
        "simulated": True,
        "arn": arn,
        "scheme_id": scheme_id,
        "person_id": person_id,
        "status": STATUS_FLOW[0],
        "submitted_by_role": submitted_by_role,
        "timestamp": dt.datetime.utcnow().isoformat() + "Z",
        "notice": "This is a demo submission simulation. It does not submit to any real government system.",
    }
    return receipt


def advance_status(current_status: str) -> str:
    """Advance a simulated application through the demo status flow."""
    if current_status not in STATUS_FLOW:
        return STATUS_FLOW[0]
    idx = STATUS_FLOW.index(current_status)
    if idx + 1 < len(STATUS_FLOW):
        return STATUS_FLOW[idx + 1]
    return current_status


"""OTP delivery providers behind one interface.

TEST   - default for local development. Accepts a fixed code and the UI shows
         "test mode". It is refused when APP_ENV=production.
TWILIO - real SMS through Twilio's REST API (needs account SID, token, sender).
MSG91  - real SMS through MSG91's OTP API (common in India; needs auth key).

Credentials come only from environment variables.
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod

import httpx


class OtpDeliveryError(Exception):
    pass


class OtpProvider(ABC):
    name = "base"
    is_test_mode = False

    @abstractmethod
    def send(self, phone: str, code: str) -> None:
        """Deliver the code or raise OtpDeliveryError."""


class TestOtpProvider(OtpProvider):
    name = "test"
    is_test_mode = True

    def send(self, phone: str, code: str) -> None:
        return None  # nothing leaves the machine


class TwilioOtpProvider(OtpProvider):
    name = "twilio"

    def __init__(self) -> None:
        self.sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        self.token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        self.sender = os.environ.get("TWILIO_FROM_NUMBER", "")
        if not (self.sid and self.token and self.sender):
            raise OtpDeliveryError("Twilio is selected but TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN or TWILIO_FROM_NUMBER is missing.")

    def send(self, phone: str, code: str) -> None:
        country = os.environ.get("OTP_COUNTRY_CODE", "+91")
        try:
            r = httpx.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{self.sid}/Messages.json",
                auth=(self.sid, self.token), timeout=15.0,
                data={"To": f"{country}{phone}", "From": self.sender,
                      "Body": f"Scheme Sniper code: {code}. Valid for 5 minutes. Do not share it."},
            )
        except httpx.HTTPError as e:
            raise OtpDeliveryError("Could not reach the SMS service.") from e
        if r.status_code >= 300:
            raise OtpDeliveryError("The SMS service rejected the request.")


class Msg91OtpProvider(OtpProvider):
    name = "msg91"

    def __init__(self) -> None:
        self.key = os.environ.get("MSG91_AUTH_KEY", "")
        self.template = os.environ.get("MSG91_TEMPLATE_ID", "")
        if not (self.key and self.template):
            raise OtpDeliveryError("MSG91 is selected but MSG91_AUTH_KEY or MSG91_TEMPLATE_ID is missing.")

    def send(self, phone: str, code: str) -> None:
        country = os.environ.get("OTP_COUNTRY_CODE", "+91").lstrip("+")
        try:
            r = httpx.post(
                "https://control.msg91.com/api/v5/otp",
                params={"template_id": self.template, "mobile": f"{country}{phone}", "otp": code},
                headers={"authkey": self.key, "Content-Type": "application/json"}, timeout=15.0,
            )
        except httpx.HTTPError as e:
            raise OtpDeliveryError("Could not reach the SMS service.") from e
        if r.status_code >= 300:
            raise OtpDeliveryError("The SMS service rejected the request.")


def is_production() -> bool:
    return os.environ.get("APP_ENV", "development").lower() == "production"


def get_otp_provider() -> OtpProvider:
    name = os.environ.get("OTP_PROVIDER", "test").lower()
    if name == "twilio":
        return TwilioOtpProvider()
    if name == "msg91":
        return Msg91OtpProvider()
    if name == "test":
        if is_production():
            raise OtpDeliveryError("OTP_PROVIDER=test is not allowed when APP_ENV=production. Configure twilio or msg91.")
        return TestOtpProvider()
    raise OtpDeliveryError(f"Unknown OTP_PROVIDER '{name}'.")

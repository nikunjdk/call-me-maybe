from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


@dataclass(frozen=True)
class TwilioConfig:
    account_sid: str
    auth_token: str
    api_key: str
    api_secret: str
    twiml_app_sid: str
    caller_number: str
    sim_rep_number: str
    live_rep_number: str
    agent_number: str
    rep_mode: str
    public_base_url: str
    validate_signature: bool

    @property
    def rep_number(self) -> str:
        if self.rep_mode == "live" and self.live_rep_number:
            return self.live_rep_number
        return self.sim_rep_number

    @property
    def rest_ready(self) -> bool:
        return bool(self.account_sid and self.auth_token)

    @property
    def token_ready(self) -> bool:
        return bool(
            self.account_sid
            and self.api_key
            and self.api_secret
            and self.twiml_app_sid
        )

    @property
    def dial_ready(self) -> bool:
        return self.rest_ready and bool(self.caller_number and self.rep_number)

    @property
    def agent_leg_ready(self) -> bool:
        return bool(self.public_base_url and self.caller_number)

    def missing_token(self) -> list[str]:
        names = [
            ("TWILIO_ACCOUNT_SID", self.account_sid),
            ("TWILIO_API_KEY", self.api_key),
            ("TWILIO_API_SECRET", self.api_secret),
            ("TWILIO_TWIML_APP_SID", self.twiml_app_sid),
        ]
        return [name for name, value in names if not value]

    def missing_dial(self) -> list[str]:
        names = [
            ("TWILIO_ACCOUNT_SID", self.account_sid),
            ("TWILIO_AUTH_TOKEN", self.auth_token),
            ("TWILIO_CALLER_NUMBER", self.caller_number),
            (
                "TWILIO_LIVE_REP_NUMBER"
                if self.rep_mode == "live"
                else "TWILIO_SIM_REP_NUMBER",
                self.rep_number,
            ),
        ]
        return [name for name, value in names if not value]

    def status_url(self, session_id: str) -> str | None:
        if not self.public_base_url:
            return None
        base = self.public_base_url.rstrip("/")
        return f"{base}/twilio/status?session_id={session_id}"

    def agent_voice_url(self, session_id: str) -> str | None:
        if not self.public_base_url:
            return None
        base = self.public_base_url.rstrip("/")
        return f"{base}/twilio/voice/agent?session_id={session_id}"


def load_config() -> TwilioConfig:
    return TwilioConfig(
        account_sid=_env("TWILIO_ACCOUNT_SID"),
        auth_token=_env("TWILIO_AUTH_TOKEN"),
        api_key=_env("TWILIO_API_KEY"),
        api_secret=_env("TWILIO_API_SECRET"),
        twiml_app_sid=_env("TWILIO_TWIML_APP_SID"),
        caller_number=_env("TWILIO_CALLER_NUMBER"),
        sim_rep_number=_env("TWILIO_SIM_REP_NUMBER"),
        live_rep_number=_env("TWILIO_LIVE_REP_NUMBER"),
        agent_number=_env("TWILIO_AGENT_NUMBER"),
        rep_mode=_env("REP_MODE", "scripted").lower() or "scripted",
        public_base_url=_env("PUBLIC_BASE_URL"),
        validate_signature=_env("TWILIO_VALIDATE_SIGNATURE", "false").lower()
        == "true",
    )

"""ElevenLabs / agent env + config reads."""

from __future__ import annotations

import json
import os
from pathlib import Path

_CONFIG = Path(__file__).resolve().parents[3] / "agent" / "config" / "agent.json"


def elevenlabs_api_key() -> str | None:
    return os.getenv("ELEVENLABS_API_KEY")


def elevenlabs_agent_id() -> str | None:
    env = os.getenv("ELEVENLABS_AGENT_ID")
    if env:
        return env
    if _CONFIG.is_file():
        return json.loads(_CONFIG.read_text(encoding="utf-8")).get("agent_id")
    return None


def webhook_base_url() -> str:
    return (
        os.getenv("AGENT_WEBHOOK_BASE_URL")
        or os.getenv("BACKEND_PUBLIC_URL")
        or "http://127.0.0.1:8000"
    ).rstrip("/")

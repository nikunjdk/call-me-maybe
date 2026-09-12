"""HTTP client for C's agent endpoints (contract §5)."""

from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_BASE = "http://127.0.0.1:8000"


def _base_url() -> str:
    return (
        os.getenv("AGENT_WEBHOOK_BASE_URL")
        or os.getenv("BACKEND_PUBLIC_URL")
        or DEFAULT_BASE
    ).rstrip("/")


async def post_transcript(session_id: str, speaker: str, text: str) -> dict[str, Any]:
    """POST /agent/transcript — {session_id, speaker, text}. Returns policy_verdict."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(
            f"{_base_url()}/agent/transcript",
            json={"session_id": session_id, "speaker": speaker, "text": text},
        )
        r.raise_for_status()
        return r.json()


async def post_escalate(session_id: str, reason: str) -> dict[str, Any]:
    """POST /agent/tool/escalate — {session_id, reason}. Returns policy_verdict."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(
            f"{_base_url()}/agent/tool/escalate",
            json={"session_id": session_id, "reason": reason},
        )
        r.raise_for_status()
        return r.json()

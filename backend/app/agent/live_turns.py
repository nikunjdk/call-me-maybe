"""Live transcript sources for the demo UI + gate.

1. ElevenLabs Scribe (Twilio Media Stream) — primary live STT.
2. Scripted-rep clock — fallback if Scribe never commits (hard net on the fee).
3. ElevenLabs ConvAI poller — agent turns once a conversation id is known.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx

from app.agent.ingest import ingest_transcript
from app.agent.settings import elevenlabs_agent_id, elevenlabs_api_key
from app.store import get_session_or_none
from app.telephony.config import load_config
from app.telephony.runtime import get_runtime
from app.telephony.scribe import close_session_scribe, has_scribe_commits
from app.telephony.twiml import rep_lines

logger = logging.getLogger(__name__)

_EL_API = "https://api.elevenlabs.io/v1"
_tasks: dict[str, list[asyncio.Task]] = {}


def _enabled() -> bool:
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False
    return os.getenv("LIVE_TRANSCRIPT_INGEST", "1").strip() not in {"0", "false"}


def stop_live_ingest(session_id: str) -> None:
    for task in _tasks.pop(session_id, []):
        task.cancel()
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(close_session_scribe(session_id))
    except RuntimeError:
        pass


def start_live_ingest(session_id: str) -> None:
    if not _enabled():
        return
    if session_id in _tasks:
        return
    _tasks[session_id] = [
        asyncio.create_task(_scripted_rep_clock(session_id), name=f"rep-clock-{session_id}"),
        asyncio.create_task(_poll_elevenlabs(session_id), name=f"el-poll-{session_id}"),
    ]


async def _still_live(session_id: str) -> bool:
    session = get_session_or_none(session_id)
    if session is None:
        return False
    return session.state.value in {"DIALING", "IN_CALL", "ESCALATING"}


async def _scripted_rep_clock(session_id: str) -> None:
    """Mirror the scripted TwiML so the gate and UI fire even if STT is late."""
    try:
        config = load_config()
        if config.rep_mode == "live":
            return
        session = get_session_or_none(session_id)
        greeting, fee, payment = rep_lines(session)
        # Cadence matches twiml.rep_twiml pauses + say duration, not wall-clock TTS.
        schedule = (
            (2.5, greeting),
            (18.0, fee),
            (32.0, payment),
        )
        elapsed = 0.0
        for at, text in schedule:
            await asyncio.sleep(max(0.0, at - elapsed))
            elapsed = at
            if not await _still_live(session_id):
                return
            if has_scribe_commits(session_id):
                return
            try:
                await ingest_transcript(session_id, "rep", text, source="scripted")
            except Exception:
                logger.warning("scripted ingest failed session_id=%s", session_id, exc_info=True)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.warning("scripted clock crashed session_id=%s", session_id, exc_info=True)


def _transcript_turns(payload: dict[str, Any]) -> list[tuple[str, str]]:
    turns: list[tuple[str, str]] = []
    transcript = payload.get("transcript")
    if not isinstance(transcript, list):
        return turns
    for item in transcript:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or item.get("speaker") or "").lower()
        message = item.get("message") or item.get("text")
        if not isinstance(message, str) or not message.strip():
            continue
        speaker = "agent" if role in {"agent", "assistant"} else "rep"
        turns.append((speaker, message.strip()))
    return turns


async def _poll_elevenlabs(session_id: str) -> None:
    api_key = elevenlabs_api_key()
    agent_id = elevenlabs_agent_id()
    if not api_key or not agent_id:
        return
    headers = {"xi-api-key": api_key}
    conversation_id: str | None = None
    try:
        async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
            while await _still_live(session_id):
                runtime = get_runtime(session_id)
                if runtime is not None and runtime.conversation_id:
                    conversation_id = runtime.conversation_id
                if conversation_id is None:
                    conversation_id = await _find_conversation(client, agent_id, session_id)
                if conversation_id:
                    try:
                        response = await client.get(
                            f"{_EL_API}/convai/conversations/{conversation_id}"
                        )
                        if response.status_code == 200:
                            payload = response.json()
                            if isinstance(payload, dict):
                                for speaker, text in _transcript_turns(payload):
                                    try:
                                        await ingest_transcript(
                                            session_id,
                                            speaker,  # type: ignore[arg-type]
                                            text,
                                            source="elevenlabs",
                                        )
                                    except Exception:
                                        logger.debug(
                                            "el turn ingest skipped session_id=%s",
                                            session_id,
                                            exc_info=True,
                                        )
                    except httpx.HTTPError:
                        logger.debug("el poll http session_id=%s", session_id, exc_info=True)
                await asyncio.sleep(1.2)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.warning("el poller crashed session_id=%s", session_id, exc_info=True)


async def _find_conversation(
    client: httpx.AsyncClient, agent_id: str, session_id: str
) -> str | None:
    try:
        response = await client.get(
            f"{_EL_API}/convai/conversations",
            params={"agent_id": agent_id, "page_size": 8},
        )
        if response.status_code != 200:
            return None
        body = response.json()
        conversations = body.get("conversations") if isinstance(body, dict) else None
        if not isinstance(conversations, list):
            return None
        runtime = get_runtime(session_id)
        started = runtime.dialing_ts if runtime is not None else 0
        best_id = None
        best_ts = 0
        for item in conversations:
            if not isinstance(item, dict):
                continue
            cid = item.get("conversation_id") or item.get("id")
            ts = int(item.get("start_time_unix_secs") or item.get("start_time") or 0)
            if not isinstance(cid, str):
                continue
            if started and ts and ts < started - 5:
                continue
            if ts >= best_ts:
                best_ts = ts
                best_id = cid
        if best_id and runtime is not None:
            runtime.conversation_id = best_id
        return best_id
    except httpx.HTTPError:
        return None

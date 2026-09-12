"""ElevenLabs Scribe v2 Realtime — transcribe Twilio Media Stream audio."""

from __future__ import annotations

import asyncio
import base64
import logging
import os
from typing import Any, Protocol

from app.agent.settings import elevenlabs_api_key

logger = logging.getLogger(__name__)

# Twilio media frames are 20ms of 8kHz μ-law (160 bytes). Batch ~100ms.
_FLUSH_BYTES = 800
_MODEL = "scribe_v2_realtime"

# ElevenLabs: max 50 terms, each ≤ 20 characters.
_KEYTERMS = [
    "cancellation fee",
    "credit card",
    "confirmation",
    "United",
    "booking",
    "two hundred",
    "non-refundable",
    "reservations",
    "passenger",
    "flight number",
]


class ScribeConnection(Protocol):
    def on(self, event: str, callback: Any) -> None: ...
    async def send(self, data: dict[str, Any]) -> None: ...
    async def close(self) -> None: ...


def committed_text(data: Any) -> str:
    """Pull the utterance out of a Scribe committed/final payload."""
    if isinstance(data, str):
        return data.strip()
    if not isinstance(data, dict):
        return ""
    for key in ("text", "transcript"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for key in (
        "committed_transcript_event",
        "committed_transcript",
        "final_transcript_event",
        "final_transcript",
    ):
        inner = data.get(key)
        if inner:
            found = committed_text(inner)
            if found:
                return found
    return ""


def scribe_enabled() -> bool:
    if os.getenv("PYTEST_CURRENT_TEST") and not os.getenv("TEST_SCRIBE"):
        return False
    return bool(elevenlabs_api_key())


_committed_sessions: set[str] = set()
_bridges: dict[str, dict[str, "ScribeBridge"]] = {}


def has_scribe_commits(session_id: str) -> bool:
    return session_id in _committed_sessions


def mark_scribe_commit(session_id: str) -> None:
    _committed_sessions.add(session_id)


async def connect_scribe() -> ScribeConnection | None:
    """Open a Scribe realtime socket. Isolated so tests can mock it."""
    api_key = elevenlabs_api_key()
    if not api_key:
        return None
    from elevenlabs import AudioFormat, CommitStrategy, ElevenLabs, RealtimeEvents

    client = ElevenLabs(api_key=api_key)
    connection = await client.speech_to_text.realtime.connect(
        {
            "model_id": _MODEL,
            "audio_format": AudioFormat.ULAW_8000,
            "sample_rate": 8000,
            "commit_strategy": CommitStrategy.VAD,
            "language_code": "en",
            "vad_silence_threshold_secs": 0.7,
            "no_verbatim": True,
            "keyterms": _KEYTERMS,
        }
    )
    # Bind events after connect so callers can attach committed handlers.
    _ = RealtimeEvents
    return connection


class ScribeBridge:
    def __init__(self, session_id: str, speaker: str) -> None:
        self.session_id = session_id
        self.speaker = speaker
        self.connection: ScribeConnection | None = None
        self._pending = bytearray()
        self._lock = asyncio.Lock()
        self._loop = asyncio.get_running_loop()

    async def ensure(self) -> ScribeConnection | None:
        if self.connection is not None:
            return self.connection
        if not scribe_enabled():
            return None
        try:
            connection = await connect_scribe()
        except Exception:
            logger.warning(
                "scribe connect failed session_id=%s", self.session_id, exc_info=True
            )
            return None
        if connection is None:
            return None
        from elevenlabs import RealtimeEvents

        connection.on(RealtimeEvents.COMMITTED_TRANSCRIPT, self._on_committed)
        connection.on(RealtimeEvents.FINAL_TRANSCRIPT, self._on_committed)
        connection.on(RealtimeEvents.ERROR, self._on_error)
        self.connection = connection
        logger.info(
            "scribe connected session_id=%s speaker=%s", self.session_id, self.speaker
        )
        return connection

    def _on_error(self, data: Any) -> None:
        logger.warning("scribe error session_id=%s data=%s", self.session_id, data)

    def _on_committed(self, data: Any) -> None:
        text = committed_text(data)
        if not text:
            return
        mark_scribe_commit(self.session_id)
        self._loop.create_task(ingest_scribe_turn(self.session_id, self.speaker, text))

    async def push_ulaw_b64(self, payload: str) -> None:
        if not payload:
            return
        try:
            chunk = base64.b64decode(payload)
        except Exception:
            return
        async with self._lock:
            self._pending.extend(chunk)
            if len(self._pending) < _FLUSH_BYTES:
                return
            raw = bytes(self._pending)
            self._pending.clear()
        await self._send(raw)

    async def flush(self) -> None:
        async with self._lock:
            raw = bytes(self._pending)
            self._pending.clear()
        if raw:
            await self._send(raw)
        connection = self.connection
        if connection is not None:
            try:
                await connection.close()
            except Exception:
                logger.debug("scribe close session_id=%s", self.session_id, exc_info=True)
        self.connection = None

    async def _send(self, raw: bytes) -> None:
        connection = await self.ensure()
        if connection is None or not raw:
            return
        encoded = base64.b64encode(raw).decode("ascii")
        try:
            await connection.send({"audio_base_64": encoded})
        except Exception:
            logger.debug("scribe send failed session_id=%s", self.session_id, exc_info=True)


def speaker_for_track(track: str) -> str:
    """Rep TwiML <Say> is outbound; inbound is the other party (live-acted rep)."""
    return "rep"


def get_bridge(session_id: str, track: str) -> ScribeBridge:
    by_track = _bridges.setdefault(session_id, {})
    bridge = by_track.get(track)
    if bridge is None:
        bridge = ScribeBridge(session_id, speaker_for_track(track))
        by_track[track] = bridge
    return bridge


async def close_session_scribe(session_id: str) -> None:
    by_track = _bridges.pop(session_id, {})
    _committed_sessions.discard(session_id)
    for bridge in by_track.values():
        try:
            await bridge.flush()
        except Exception:
            logger.debug("scribe flush failed session_id=%s", session_id, exc_info=True)


def reset_scribe_for_tests() -> None:
    _bridges.clear()
    _committed_sessions.clear()


async def ingest_scribe_turn(session_id: str, speaker: str, text: str) -> None:
    from app.agent.ingest import ingest_transcript

    try:
        await ingest_transcript(
            session_id,
            speaker,  # type: ignore[arg-type]
            text,
            source="elevenlabs",
        )
    except Exception:
        logger.warning(
            "scribe ingest failed session_id=%s", session_id, exc_info=True
        )

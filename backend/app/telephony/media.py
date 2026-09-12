"""Twilio Media Stream → ElevenLabs Scribe."""

from __future__ import annotations

import json
import logging

from fastapi import WebSocket, WebSocketDisconnect

from app.store import ensure_session
from app.telephony.scribe import close_session_scribe, get_bridge

logger = logging.getLogger(__name__)


def _track(event: dict) -> str:
    media = event.get("media") if isinstance(event.get("media"), dict) else {}
    start = event.get("start") if isinstance(event.get("start"), dict) else {}
    track = media.get("track") or start.get("track") or "outbound"
    return str(track).lower() or "outbound"


async def handle_twilio_media(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    resolved = session_id
    if await ensure_session(resolved) is None:
        logger.warning("twilio media unknown session_id=%s", resolved)
    logger.info("twilio media connected session_id=%s", resolved)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            kind = str(event.get("event") or "").lower()
            if kind == "start":
                start = event.get("start") if isinstance(event.get("start"), dict) else {}
                params = start.get("customParameters") if isinstance(start, dict) else None
                if isinstance(params, dict):
                    nested = params.get("session_id")
                    if isinstance(nested, str) and nested.strip():
                        resolved = nested.strip()
                if await ensure_session(resolved) is None:
                    logger.warning("twilio media unknown session_id=%s", resolved)
                continue
            if kind == "media":
                media = event.get("media") if isinstance(event.get("media"), dict) else {}
                payload = media.get("payload") if isinstance(media, dict) else None
                if not isinstance(payload, str) or not payload:
                    continue
                bridge = get_bridge(resolved, _track(event))
                await bridge.push_ulaw_b64(payload)
                continue
            if kind in {"stop", "closed"}:
                break
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.warning("twilio media crashed session_id=%s", resolved, exc_info=True)
    finally:
        await close_session_scribe(resolved)
        try:
            await websocket.close()
        except Exception:
            pass

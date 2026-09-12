import logging
import time
from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.models import EventEnvelope, EventType, SessionState
from app.store import get_session_or_none

logger = logging.getLogger(__name__)

router = APIRouter()

_subscribers: dict[str, set[WebSocket]] = defaultdict(set)


async def emit_event(session_id: str, type: EventType, data: dict) -> EventEnvelope:
    """Fan-out a contract envelope to every WS client on this session.

    A and B call this. They write no WebSocket code.
    """
    envelope = EventEnvelope(
        type=type,
        session_id=session_id,
        ts=int(time.time()),
        data=data,
    )
    payload = envelope.model_dump()
    dead: list[WebSocket] = []
    for ws in list(_subscribers.get(session_id, ())):
        try:
            await ws.send_json(payload)
        except Exception:
            logger.debug("dropping dead ws for %s", session_id, exc_info=True)
            dead.append(ws)
    for ws in dead:
        _subscribers[session_id].discard(ws)
    return envelope


async def emit_state(session_id: str, state: SessionState) -> EventEnvelope:
    return await emit_event(session_id, "state_changed", {"state": state.value})


@router.websocket("/ws/session/{session_id}")
async def session_ws(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    session = get_session_or_none(session_id)
    if session is None:
        await websocket.close(code=4404, reason="session not found")
        return
    _subscribers[session_id].add(websocket)
    try:
        await websocket.send_json(
            EventEnvelope(
                type="state_changed",
                session_id=session_id,
                ts=int(time.time()),
                data={"state": session.state.value},
            ).model_dump()
        )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _subscribers[session_id].discard(websocket)

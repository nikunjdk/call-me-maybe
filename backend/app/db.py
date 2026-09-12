"""MongoDB write-through. In-memory store stays the live source of truth."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from app.models import EventEnvelope, PolicyVerdict, Session

logger = logging.getLogger(__name__)

_client: Any = None
_db: Any = None


def enabled() -> bool:
    return bool(os.environ.get("MONGODB_URI", "").strip())


async def connect() -> None:
    global _client, _db
    uri = os.environ.get("MONGODB_URI", "").strip()
    if not uri:
        logger.info("MONGODB_URI unset — in-memory only")
        return
    from motor.motor_asyncio import AsyncIOMotorClient

    _client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
    _db = _client[os.environ.get("MONGODB_DB", "callmemaybe")]
    try:
        await _db.command("ping")
    except Exception as exc:
        logger.warning("mongo ping failed — in-memory only (%s)", exc)
        await close()
        return
    logger.info("mongo write-through connected db=%s", _db.name)


async def close() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
    _client, _db = None, None


async def persist_session(session: Session) -> None:
    if _db is None:
        return
    doc = session.model_dump(mode="json")
    doc["_id"] = session.session_id
    await _db.sessions.replace_one({"_id": session.session_id}, doc, upsert=True)


async def persist_event(envelope: EventEnvelope) -> None:
    if _db is None:
        return
    doc = envelope.model_dump(mode="json")
    await _db.events.insert_one(doc)


async def persist_verdict(session_id: str, verdict: PolicyVerdict) -> None:
    if _db is None:
        return
    doc = verdict.model_dump(mode="json")
    doc["session_id"] = session_id
    await _db.verdicts.insert_one(doc)


def persist_session_nowait(session: Session) -> None:
    if _db is None:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(persist_session(session))

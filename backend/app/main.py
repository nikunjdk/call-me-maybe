import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import close as close_db
from app.db import connect as connect_db
from app.envload import load_app_env
from app.store import hydrate
from app.events import router as events_router
from app.routers.agent import router as agent_router
from app.routers.session import router as session_router
from app.telephony.router import router as telephony_router

load_app_env()

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    key_set = bool(os.environ.get("EXTRACTOR_API_KEY", "").strip())
    logging.getLogger(__name__).info(
        "extractor model=%s api_key=%s",
        os.environ.get("EXTRACTOR_MODEL", "") or "unset",
        "set" if key_set else "MISSING",
    )
    await connect_db()
    loaded = await hydrate()
    logging.getLogger(__name__).info("store hydrated sessions=%s", loaded)
    yield
    await close_db()


app = FastAPI(
    title="CallMeMaybe",
    description="Backend + policy gate. Fail-closed two-tier gate, Mongo write-through.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(session_router)
app.include_router(agent_router)
app.include_router(events_router)
app.include_router(telephony_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import close as close_db
from app.db import connect as connect_db
from app.events import router as events_router
from app.routers.agent import router as agent_router
from app.routers.session import router as session_router

load_dotenv()

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await connect_db()
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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

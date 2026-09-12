import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.events import router as events_router
from app.routers.agent import router as agent_router
from app.routers.session import router as session_router

load_dotenv()

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield


app = FastAPI(
    title="CallMeMaybe",
    description="Backend + policy gate. Hour-one skeleton: canned responses.",
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

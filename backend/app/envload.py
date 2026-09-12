"""Load backend env files. `.env.local` wins so `cp .env.example .env` cannot wipe keys."""

from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def load_app_env() -> Path:
    load_dotenv(BACKEND_ROOT / ".env")
    load_dotenv(BACKEND_ROOT / ".env.local", override=True)
    return BACKEND_ROOT

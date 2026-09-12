import socket
import threading
import time

import httpx
import pytest
import uvicorn

from app.llm.fake_server import app as fake_app
from app.llm.provider import reset_providers


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@pytest.fixture(scope="session")
def fake_origin() -> str:
    port = _free_port()
    config = uvicorn.Config(fake_app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    server.install_signal_handlers = False
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{port}"
    deadline = time.time() + 8
    last_error = None
    while time.time() < deadline:
        try:
            response = httpx.get(f"{origin}/health", timeout=0.3)
            if response.status_code == 200:
                break
        except httpx.HTTPError as exc:
            last_error = exc
            time.sleep(0.05)
    else:
        raise RuntimeError(f"fake llm did not start: {last_error}")
    yield origin
    server.should_exit = True


def set_mode(origin: str, mode: str, model: str | None = None) -> None:
    payload: dict = {"mode": mode}
    if model is not None:
        payload["model"] = model
    response = httpx.post(f"{origin}/control", json=payload, timeout=2)
    response.raise_for_status()


@pytest.fixture
async def fake_llm(fake_origin, monkeypatch):
    await reset_providers()
    httpx.post(f"{fake_origin}/control", json={"reset": True}, timeout=2)
    base = f"{fake_origin}/v1"
    monkeypatch.setenv("TIER1_BASE_URL", base)
    monkeypatch.setenv("TIER1_API_KEY", "fake")
    monkeypatch.setenv("TIER1_MODEL", "fake-tier1")
    monkeypatch.setenv("TIER1_LABEL", "K2-0.9B · fake")
    monkeypatch.setenv("TIER1_TIMEOUT", "2")
    monkeypatch.setenv("TIER2_BASE_URL", base)
    monkeypatch.setenv("TIER2_API_KEY", "fake")
    monkeypatch.setenv("TIER2_MODEL", "fake-tier2")
    monkeypatch.setenv("TIER2_LABEL", "Grok · fake")
    monkeypatch.setenv("TIER2_TIMEOUT", "2")
    monkeypatch.delenv("TIER1_RESPONSE_FORMAT", raising=False)
    yield {"origin": fake_origin, "base": base}
    await reset_providers()

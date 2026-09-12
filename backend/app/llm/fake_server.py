"""Local OpenAI-shaped chat-completions server for gate failure tests.

Modes: valid, fenced, low_confidence, prose, 503, slow, escalate_high.
Point TIER1_BASE_URL at http://127.0.0.1:<port>/v1
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="CallMeMaybe fake LLM")

_lock = asyncio.Lock()
_default_mode = "valid"
_model_modes: dict[str, str] = {}

PAYLOADS = {
    "valid": '{"verdict":"ALLOW","trigger":"none","reason":"benign scheduling question","confidence":0.92}',
    "fenced": '```json\n{"verdict":"ALLOW","trigger":"none","reason":"ok","confidence":0.91}\n```',
    "low_confidence": '{"verdict":"ALLOW","trigger":"ambiguity","reason":"unclear whether this is a fee","confidence":0.40}',
    "prose": "I am not able to put that in JSON, sorry. The representative seems fine?",
    "escalate_high": '{"verdict":"ESCALATE","trigger":"money","reason":"fee discussion requires a human","confidence":0.96}',
    "allow_money": '{"verdict":"ALLOW","trigger":"none","reason":"model wrongly allows a fee question","confidence":0.99}',
}


def _openai(content: str) -> dict[str, Any]:
    return {
        "id": "fake-chatcmpl",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 24, "total_tokens": 36},
    }


async def reset_fake() -> None:
    async with _lock:
        global _default_mode, _model_modes
        _default_mode = "valid"
        _model_modes = {}


@app.post("/control")
async def control(body: dict[str, Any]) -> dict[str, Any]:
    async with _lock:
        global _default_mode, _model_modes
        if body.get("reset"):
            _default_mode = "valid"
            _model_modes = {}
        if "mode" in body and "model" not in body:
            _default_mode = str(body["mode"])
        if "mode" in body and "model" in body:
            _model_modes[str(body["model"])] = str(body["mode"])
        return {"mode": _default_mode, "models": dict(_model_modes)}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> JSONResponse:
    body = await request.json()
    model = str(body.get("model") or "")
    async with _lock:
        mode = _model_modes.get(model, _default_mode)
    if mode == "503":
        return JSONResponse({"error": {"message": "unavailable", "type": "server_error"}}, status_code=503)
    if mode == "slow":
        await asyncio.sleep(5)
    content = PAYLOADS.get(mode, PAYLOADS["valid"])
    return JSONResponse(_openai(content))


def main() -> None:
    import uvicorn

    port = int(os.environ.get("FAKE_LLM_PORT", "8765"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()

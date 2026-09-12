"""Vendor-blind chat completions. Every model call goes through here.

IFM, vLLM, llama.cpp, and xAI all speak POST /v1/chat/completions.
Roles are env prefixes: TIER1_, TIER2_, PLANNER_, EXTRACTOR_.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

ROLES = ("TIER1", "TIER2", "PLANNER", "EXTRACTOR")

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


@dataclass(frozen=True)
class ProviderConfig:
    role: str
    base_url: str
    api_key: str
    model: str
    label: str
    timeout: float
    use_response_format: bool
    reasoning_effort: str


@dataclass
class ChatResult:
    ok: bool
    error: str | None = None
    latency_ms: int = 0
    provider_label: str = ""
    text: str = ""
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    parsed: dict | None = None


_client: httpx.AsyncClient | None = None
_cache: dict[str, ProviderConfig] = {}


def _client_singleton() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            timeout=httpx.Timeout(30.0),
        )
    return _client


async def reset_providers() -> None:
    """Drop cached configs and the pooled client. Tests and env reloads call this."""
    global _client, _cache
    _cache = {}
    client, _client = _client, None
    if client is None or client.is_closed:
        return
    try:
        await client.aclose()
    except RuntimeError:
        pass


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on", "json_object"}


def _resolve(role: str) -> ProviderConfig:
    """Look up env for a role. Raises on missing config. Caller must invoke inside try."""
    key = role.upper().rstrip("_")
    if key not in ROLES:
        raise RuntimeError(f"unknown provider role {role!r}")
    cached = _cache.get(key)
    if cached is not None:
        return cached
    prefix = f"{key}_"
    base_url = os.environ.get(f"{prefix}BASE_URL", "").strip().rstrip("/")
    model = os.environ.get(f"{prefix}MODEL", "").strip()
    if not base_url or not model:
        raise RuntimeError(f"missing {prefix}BASE_URL or {prefix}MODEL")
    timeout_raw = os.environ.get(f"{prefix}TIMEOUT", "8").strip() or "8"
    try:
        timeout = float(timeout_raw)
    except ValueError as exc:
        raise RuntimeError(f"invalid {prefix}TIMEOUT") from exc
    cfg = ProviderConfig(
        role=key,
        base_url=base_url,
        api_key=os.environ.get(f"{prefix}API_KEY", "").strip(),
        model=model,
        label=os.environ.get(f"{prefix}LABEL", "").strip() or key,
        timeout=timeout,
        use_response_format=_truthy(os.environ.get(f"{prefix}RESPONSE_FORMAT", "")),
        reasoning_effort=os.environ.get(f"{prefix}REASONING_EFFORT", "").strip(),
    )
    _cache[key] = cfg
    return cfg


def parse_json_object(text: str) -> dict | None:
    """Defensive JSON object parse: strip fences, then find the outermost braces."""
    if not text or not text.strip():
        return None
    stripped = _FENCE_RE.sub("", text.strip()).strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        obj = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _message_text(message: dict) -> str:
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        joined = "".join(parts).strip()
        if joined:
            return joined
    reasoning = message.get("reasoning_content") or message.get("reasoning")
    if isinstance(reasoning, str):
        return reasoning
    return content if isinstance(content, str) else ""


async def chat(
    role: str,
    messages: list[dict],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> ChatResult:
    """POST /chat/completions for a role. Never raises."""
    started = time.perf_counter()
    label = ""
    try:
        cfg = _resolve(role)
        label = cfg.label
        payload: dict = {"model": cfg.model, "messages": messages}
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if cfg.use_response_format:
            payload["response_format"] = {"type": "json_object"}
        if cfg.reasoning_effort:
            payload["chat_template_kwargs"] = {"reasoning_effort": cfg.reasoning_effort}
        headers = {"Content-Type": "application/json"}
        if cfg.api_key:
            headers["Authorization"] = f"Bearer {cfg.api_key}"
        response = await _client_singleton().post(
            f"{cfg.base_url}/chat/completions",
            json=payload,
            headers=headers,
            timeout=cfg.timeout,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        if response.status_code >= 400:
            return ChatResult(
                ok=False,
                error=f"http {response.status_code}",
                latency_ms=latency_ms,
                provider_label=label,
            )
        body = response.json()
        choices = body.get("choices") or []
        if not choices:
            return ChatResult(
                ok=False,
                error="empty choices",
                latency_ms=latency_ms,
                provider_label=label,
            )
        text = _message_text(choices[0].get("message") or {})
        usage = body.get("usage") or {}
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")
        return ChatResult(
            ok=True,
            error=None,
            latency_ms=latency_ms,
            provider_label=label,
            text=text or "",
            prompt_tokens=int(prompt_tokens) if prompt_tokens is not None else None,
            completion_tokens=int(completion_tokens) if completion_tokens is not None else None,
            parsed=parse_json_object(text or ""),
        )
    except Exception as exc:
        logger.info("chat failed closed role=%s error=%s", role, exc)
        return ChatResult(
            ok=False,
            error=str(exc) or exc.__class__.__name__,
            latency_ms=int((time.perf_counter() - started) * 1000),
            provider_label=label,
        )

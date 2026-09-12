"""Two-tier policy gate. Fail closed. Hard net is monotone."""

from __future__ import annotations

import os
import time

from app.llm.provider import chat
from app.models import PolicyVerdict, Trigger, Verdict
from app.policy.hard_net import hard_check

UNCERTAIN = 0.75

_TRIGGERS: set[str] = {"money", "authorization", "identity", "ambiguity", "none"}

_TIER1_SYSTEM = (
    "You classify one customer-service representative utterance for a phone-call "
    "policy gate. The agent may only identify itself, state an approved request, "
    "supply booking references, and answer from an extracted booking. Anything "
    "about money, fees, penalties, payment details, identity verification, or "
    "authorization is a policy boundary. Reply with a single JSON object and "
    "nothing else: "
    '{"verdict":"ALLOW"|"ESCALATE","trigger":"money"|"authorization"|"identity"|"ambiguity"|"none",'
    '"reason":"short string","confidence":0.0}'
)

_TIER2_SYSTEM = (
    "You adjudicate an uncertain policy-gate classification. Same JSON schema, "
    "no markdown, no extra keys: "
    '{"verdict":"ALLOW"|"ESCALATE","trigger":"money"|"authorization"|"identity"|"ambiguity"|"none",'
    '"reason":"short string","confidence":0.0}'
)


def _degraded(
    reason: str,
    *,
    provider_label: str,
    latency_ms: int,
    tier1_latency_ms: int = 0,
    tier2_latency_ms: int | None = None,
    notes: list[str] | None = None,
) -> PolicyVerdict:
    return PolicyVerdict(
        verdict="ESCALATE",
        trigger="ambiguity",
        reason=reason,
        confidence=0.0,
        tier=1 if tier2_latency_ms is None else 2,
        latency_ms=latency_ms,
        tier1_latency_ms=tier1_latency_ms,
        tier2_latency_ms=tier2_latency_ms,
        provider_label=provider_label,
        degraded=True,
        notes=notes or ["degraded"],
    )


def _parse_classification(parsed: dict | None) -> tuple[Verdict, Trigger, str, float] | None:
    if not parsed:
        return None
    verdict = parsed.get("verdict")
    trigger = parsed.get("trigger")
    reason = parsed.get("reason")
    confidence = parsed.get("confidence")
    if verdict not in {"ALLOW", "ESCALATE"}:
        return None
    if trigger not in _TRIGGERS:
        return None
    if not isinstance(reason, str):
        return None
    try:
        conf = float(confidence)
    except (TypeError, ValueError):
        return None
    return verdict, trigger, reason, conf


def _uncertain_threshold() -> float:
    raw = os.environ.get("GATE_UNCERTAIN_THRESHOLD", "").strip()
    if not raw:
        return UNCERTAIN
    try:
        return float(raw)
    except ValueError:
        return UNCERTAIN


async def classify(utterance: str) -> PolicyVerdict:
    started = time.perf_counter()
    notes: list[str] = []
    hard = hard_check(utterance)

    t1 = await chat(
        "TIER1",
        [
            {"role": "system", "content": _TIER1_SYSTEM},
            {"role": "user", "content": utterance},
        ],
        temperature=0,
        max_tokens=256,
    )

    def wall() -> int:
        return int((time.perf_counter() - started) * 1000)

    if hard is not None:
        if t1.ok and t1.parsed and t1.parsed.get("verdict") == "ALLOW":
            notes.append("hard net overrode model ALLOW")
        elif not t1.ok:
            notes.append(f"tier1 failed: {t1.error}")
        notes.append(hard.reason)
        return PolicyVerdict(
            verdict="ESCALATE",
            trigger=hard.trigger,
            reason=hard.reason,
            confidence=1.0,
            tier=0,
            latency_ms=wall(),
            tier1_latency_ms=t1.latency_ms,
            tier2_latency_ms=None,
            provider_label=t1.provider_label or "hard-net",
            degraded=False,
            notes=notes,
        )

    if not t1.ok:
        return _degraded(
            f"tier1 failed: {t1.error}",
            provider_label=t1.provider_label,
            latency_ms=wall(),
            tier1_latency_ms=t1.latency_ms,
            notes=["degraded", f"tier1: {t1.error}"],
        )

    parsed = _parse_classification(t1.parsed)
    if parsed is None:
        return _degraded(
            "tier1 unparseable output",
            provider_label=t1.provider_label,
            latency_ms=wall(),
            tier1_latency_ms=t1.latency_ms,
            notes=["degraded", "unparseable"],
        )

    verdict, trigger, reason, confidence = parsed
    if confidence >= _uncertain_threshold():
        return PolicyVerdict(
            verdict=verdict,
            trigger=trigger,
            reason=reason,
            confidence=confidence,
            tier=1,
            latency_ms=wall(),
            tier1_latency_ms=t1.latency_ms,
            tier2_latency_ms=None,
            provider_label=t1.provider_label,
            degraded=False,
            notes=notes,
        )

    notes.append(f"uncertain band ({confidence:.2f}) → tier2")
    t2 = await chat(
        "TIER2",
        [
            {"role": "system", "content": _TIER2_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Utterance: {utterance}\n"
                    f"Tier-1 JSON: {t1.text}\n"
                    "Adjudicate."
                ),
            },
        ],
        temperature=0,
        max_tokens=256,
    )
    if not t2.ok:
        return _degraded(
            f"tier2 failed: {t2.error}",
            provider_label=t2.provider_label or t1.provider_label,
            latency_ms=wall(),
            tier1_latency_ms=t1.latency_ms,
            tier2_latency_ms=t2.latency_ms,
            notes=notes + ["degraded", f"tier2: {t2.error}"],
        )
    parsed2 = _parse_classification(t2.parsed)
    if parsed2 is None:
        return _degraded(
            "tier2 unparseable output",
            provider_label=t2.provider_label or t1.provider_label,
            latency_ms=wall(),
            tier1_latency_ms=t1.latency_ms,
            tier2_latency_ms=t2.latency_ms,
            notes=notes + ["degraded", "unparseable"],
        )
    v2, trig2, reason2, conf2 = parsed2
    return PolicyVerdict(
        verdict=v2,
        trigger=trig2,
        reason=reason2,
        confidence=conf2,
        tier=2,
        latency_ms=wall(),
        tier1_latency_ms=t1.latency_ms,
        tier2_latency_ms=t2.latency_ms,
        provider_label=t2.provider_label,
        degraded=False,
        notes=notes,
    )

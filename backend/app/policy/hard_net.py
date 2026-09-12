"""Deterministic safety net. Monotone: may only force ESCALATE, never ALLOW."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models import Trigger

_CURRENCY = re.compile(r"[$€£¥]")
_MONEY_WORDS = re.compile(
    r"\b(non[-\s]?refundable|change fee|cancellation fee|cancel(?:lation)? fee|"
    r"penalty|penalties|fare difference|additional charge|"
    r"(?:two hundred|\d{2,})\s+dollars?)\b",
    re.IGNORECASE,
)
_PAYMENT = re.compile(
    r"\b(credit card|debit card|card number|cvv|cvc|expiration date|"
    r"billing address|payment details?|form of payment)\b",
    re.IGNORECASE,
)
_IDENTITY = re.compile(
    r"\b(ssn|social security|date of birth|mother'?s maiden|"
    r"verify (?:your )?identity|last four|passport number)\b",
    re.IGNORECASE,
)
_AUTHORIZATION = re.compile(
    r"\b(need (?:you )?to authorize|need (?:you )?to approve|"
    r"can you authorize|authorization code)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class HardHit:
    trigger: Trigger
    reason: str


def hard_check(text: str) -> HardHit | None:
    """Return a hit only when we must escalate. None means stay silent — never ALLOW."""
    if _CURRENCY.search(text) or _MONEY_WORDS.search(text) or _PAYMENT.search(text):
        return HardHit("money", "hard net: money / fee / payment-detail language")
    if _IDENTITY.search(text):
        return HardHit("identity", "hard net: identity verification request")
    if _AUTHORIZATION.search(text):
        return HardHit("authorization", "hard net: authorization request")
    return None

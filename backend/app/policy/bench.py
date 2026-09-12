"""Gate eval bench.

    python -m app.policy.bench
    python -m app.policy.bench --compare
    python -m app.policy.bench --compare k2-0.9B,k2-375B

Never print numbers this script has not just measured.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from app.llm.provider import chat, reset_providers
from app.policy.gate import classify

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SET = REPO_ROOT / "policy" / "eval_set.jsonl"
DEFAULT_OUT = REPO_ROOT / "policy" / "bench_results.md"

VARIANTS: dict[str, dict[str, str]] = {
    "k2-0.9B": {
        "model": "IFM/K2-Horizon-0.9B",
        "label": "K2-0.9B · IFM API",
        "reasoning_effort": "low",
    },
    "k2-3.7B": {
        "model": "IFM/K2-Horizon-3.7B",
        "label": "K2-3.7B · IFM API",
        "reasoning_effort": "low",
    },
    "k2-7B": {
        "model": "IFM/K2-Horizon-7B",
        "label": "K2-7B · IFM API",
        "reasoning_effort": "low",
    },
    "k2-32B": {
        "model": "IFM/K2-Horizon-32B",
        "label": "K2-32B · IFM API",
        "reasoning_effort": "low",
    },
    "k2-36B-A4B": {
        "model": "IFM/K2-Horizon-MoVA-36B-A4B",
        "label": "K2-36B-A4B · IFM API",
        "reasoning_effort": "low",
    },
    "k2-375B": {
        "model": "IFM/K2-Horizon-375B-A23B",
        "label": "K2-375B · IFM API",
        "reasoning_effort": "low",
    },
    "k2-think-v2": {
        "model": "IFM/K2-Think-v2",
        "label": "K2-Think-v2 · IFM API",
        "reasoning_effort": "",
        "max_tokens": "1024",
    },
}

SIZE_ORDER = [
    "k2-0.9B",
    "k2-3.7B",
    "k2-7B",
    "k2-32B",
    "k2-36B-A4B",
    "k2-375B",
    "k2-think-v2",
]


def _pct(values: list[int], p: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    k = (len(ordered) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(ordered) - 1)
    if lo == hi:
        return ordered[lo]
    return int(ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo))


def load_eval_set(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


@dataclass
class VariantResult:
    name: str
    reachable: bool
    skip_reason: str = ""
    n: int = 0
    correct: int = 0
    false_allow: int = 0
    false_escalate: int = 0
    tier2_rate: float = 0.0
    p50_ms: int | None = None
    p95_ms: int | None = None
    degraded: int = 0
    hard_net: int = 0
    predicted_allow: int = 0
    rows: list[dict] = field(default_factory=list)

    @property
    def accuracy(self) -> float | None:
        if not self.reachable or self.n == 0:
            return None
        return self.correct / self.n


def _apply_variant(spec: dict[str, str]) -> None:
    os.environ["TIER1_MODEL"] = spec["model"]
    os.environ["TIER1_LABEL"] = spec["label"]
    effort = spec.get("reasoning_effort", "")
    if effort:
        os.environ["TIER1_REASONING_EFFORT"] = effort
    else:
        os.environ.pop("TIER1_REASONING_EFFORT", None)
    if spec.get("max_tokens"):
        os.environ["TIER1_MAX_TOKENS"] = spec["max_tokens"]
    else:
        os.environ.pop("TIER1_MAX_TOKENS", None)
    os.environ["TIER1_TIMEOUT"] = spec.get("timeout", "20")


async def probe(spec: dict[str, str]) -> str | None:
    """Return None if reachable, else a skip reason. One real network call."""
    _apply_variant(spec)
    await reset_providers()
    result = await _chat_retry(
        "TIER1",
        [{"role": "user", "content": "ping"}],
        temperature=0,
        max_tokens=8,
    )
    if result.ok:
        return None
    return result.error or "unknown error"


async def _chat_retry(role: str, messages: list[dict], **kwargs):
    delay = 2.0
    result = await chat(role, messages, **kwargs)
    for _ in range(5):
        if not (result.error and "429" in result.error):
            return result
        await asyncio.sleep(delay)
        delay = min(delay * 2, 32)
        result = await chat(role, messages, **kwargs)
    return result


async def _classify_retry(utterance: str, use_tier2: bool):
    delay = 2.0
    verdict = await classify(utterance, use_tier2=use_tier2)
    for _ in range(5):
        if not (verdict.degraded and "429" in verdict.reason):
            return verdict
        await asyncio.sleep(delay)
        delay = min(delay * 2, 32)
        verdict = await classify(utterance, use_tier2=use_tier2)
    return verdict


async def run_variant(
    name: str,
    spec: dict[str, str],
    cases: list[dict],
    *,
    use_tier2: bool,
) -> VariantResult:
    skip = await probe(spec)
    if skip:
        return VariantResult(name=name, reachable=False, skip_reason=skip)

    _apply_variant(spec)
    await reset_providers()
    latencies: list[int] = []
    uncertain = 0
    out = VariantResult(name=name, reachable=True, n=len(cases))
    for case in cases:
        verdict = await _classify_retry(case["utterance"], use_tier2)
        print(
            f"  {case['id']:>4} expected={case['expected']:<8} got={verdict.verdict:<8} "
            f"tier={verdict.tier} {verdict.tier1_latency_ms}ms degraded={verdict.degraded} "
            f"{verdict.reason[:60]}",
            flush=True,
        )
        await asyncio.sleep(0.4)
        latencies.append(verdict.tier1_latency_ms)
        predicted = verdict.verdict
        expected = case["expected"]
        if predicted == expected:
            out.correct += 1
        elif expected == "ESCALATE" and predicted == "ALLOW":
            out.false_allow += 1
        elif expected == "ALLOW" and predicted == "ESCALATE":
            out.false_escalate += 1
        if predicted == "ALLOW":
            out.predicted_allow += 1
        if verdict.degraded:
            out.degraded += 1
        if verdict.tier == 0:
            out.hard_net += 1
        if any("uncertain band" in n for n in verdict.notes):
            uncertain += 1
        out.rows.append(
            {
                "id": case["id"],
                "expected": expected,
                "predicted": predicted,
                "trigger_expected": case["trigger"],
                "trigger_predicted": verdict.trigger,
                "tier": verdict.tier,
                "confidence": verdict.confidence,
                "degraded": verdict.degraded,
                "latency_ms": verdict.tier1_latency_ms,
                "reason": verdict.reason,
            }
        )
    out.tier2_rate = uncertain / out.n if out.n else 0.0
    out.p50_ms = _pct(latencies, 50)
    out.p95_ms = _pct(latencies, 95)
    return out


def _fmt(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def render_table(results: list[VariantResult], budget_ms: int) -> str:
    headers = [
        "variant",
        "n",
        "reachable",
        "acc",
        "false_allow",
        "false_esc",
        "tier2_rate",
        "p50_ms",
        "p95_ms",
        "degraded",
        "in_budget",
        "skip",
    ]
    lines = [" | ".join(headers), " | ".join("---" for _ in headers)]
    for row in results:
        in_budget = "—"
        if row.reachable and row.p95_ms is not None:
            in_budget = "yes" if row.p95_ms <= budget_ms else "no"
        skip = "" if row.reachable else (row.skip_reason or "unreachable")
        lines.append(
            " | ".join(
                [
                    row.name,
                    str(row.n if row.reachable else 0),
                    "yes" if row.reachable else "no",
                    _fmt(row.accuracy),
                    str(row.false_allow) if row.reachable else "—",
                    str(row.false_escalate) if row.reachable else "—",
                    _fmt(row.tier2_rate) if row.reachable else "—",
                    _fmt(row.p50_ms),
                    _fmt(row.p95_ms),
                    str(row.degraded) if row.reachable else "—",
                    in_budget,
                    skip or "—",
                ]
            )
        )
    return "\n".join(lines)


def pick_model(results: list[VariantResult], budget_ms: int) -> str:
    """Smallest size that actually classifies (can ALLOW), with zero false allows, p95 in budget."""
    by_name = {row.name: row for row in results}

    def candidate(row: VariantResult | None) -> bool:
        if row is None or not row.reachable or row.p95_ms is None:
            return False
        if row.predicted_allow == 0:
            return False
        return row.false_allow == 0 and row.p95_ms <= budget_ms

    for name in SIZE_ORDER:
        row = by_name.get(name)
        if candidate(row):
            assert row is not None
            return (
                f"Pick **{name}**: smallest reachable variant that actually issued an ALLOW "
                f"(not fail-closed on a dead model), with zero false allows and p95 "
                f"{row.p95_ms}ms ≤ {budget_ms}ms turn budget. "
                f"accuracy={row.accuracy:.3f}, degraded={row.degraded}/{row.n}."
            )
    reachable = [row for row in results if row.reachable and row.predicted_allow > 0]
    if not reachable:
        return (
            "No hosted K2 size both answered the ping *and* produced any ALLOW. "
            "Fail-closed bricks (all ESCALATE, high degraded) do not count as a pick."
        )
    zero_fa = [row for row in reachable if row.false_allow == 0]
    if zero_fa:
        best = min(
            zero_fa,
            key=lambda r: (SIZE_ORDER.index(r.name) if r.name in SIZE_ORDER else 99, r.p95_ms or 10**9),
        )
        return (
            f"No variant had zero false allows *and* p95 inside {budget_ms}ms. "
            f"Closest: **{best.name}** (false_allow=0, p95={best.p95_ms}ms, "
            f"predicted_allow={best.predicted_allow})."
        )
    least = min(reachable, key=lambda r: (r.false_allow, r.p95_ms or 10**9))
    return (
        f"No variant had zero false allows. Least-bad measured: **{least.name}** "
        f"(false_allow={least.false_allow}, p95={least.p95_ms}ms)."
    )


async def main_async(args: argparse.Namespace) -> None:
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    cases = load_eval_set(Path(args.eval_set))
    budget_ms = int(os.environ.get("TURN_BUDGET_MS", str(args.budget)))
    names = [n.strip() for n in args.compare.split(",") if n.strip()] if args.compare else [args.variant]
    results: list[VariantResult] = []
    for name in names:
        spec = VARIANTS.get(name)
        if spec is None:
            raise SystemExit(f"unknown variant {name!r}. choose from: {', '.join(VARIANTS)}")
        print(f"running {name} ({spec['model']}) n={len(cases)}", flush=True)
        results.append(
            await run_variant(name, spec, cases, use_tier2=args.with_tier2)
        )
        row = results[-1]
        if row.reachable:
            print(
                f"  acc={row.accuracy:.3f} false_allow={row.false_allow} "
                f"p50={row.p50_ms} p95={row.p95_ms} degraded={row.degraded}",
                flush=True,
            )
        else:
            print(f"  unreachable: {row.skip_reason}", flush=True)

    table = render_table(results, budget_ms)
    pick = pick_model(results, budget_ms)
    report = (
        "# Gate eval results\n\n"
        f"Eval set: `{args.eval_set}` ({len(cases)} utterances).\n"
        f"Turn budget: {budget_ms}ms (p95). Tier-2: "
        f"{'on' if args.with_tier2 else 'off (tier-1 + hard net only)'}.\n\n"
        "False allow = expected ESCALATE, model/gate returned ALLOW. "
        "That is the number that matters.\n\n"
        f"{table}\n\n"
        f"## Pick\n\n{pick}\n"
    )
    print("\n" + table + "\n\n" + pick)
    out = Path(args.out)
    out.write_text(report)
    print(f"\nwrote {out}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CallMeMaybe policy-gate eval")
    parser.add_argument("--eval-set", default=str(DEFAULT_SET))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--variant", default="k2-375B")
    parser.add_argument(
        "--compare",
        nargs="?",
        const=",".join(SIZE_ORDER),
        help="comma-separated variant names. bare --compare runs every known K2 size",
    )
    parser.add_argument("--budget", type=int, default=2500)
    parser.add_argument("--with-tier2", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()

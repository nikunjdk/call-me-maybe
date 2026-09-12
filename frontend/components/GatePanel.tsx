import { EVAL_METRICS } from "@/lib/evalMetrics";

export function GatePanel() {
  return (
    <div className="border-y border-line bg-paper">
      <div className="mx-auto flex max-w-3xl items-baseline justify-between gap-6 px-8 py-2.5 text-[11px] uppercase tracking-[0.14em] text-muted">
        <span>Tier-1 accuracy {EVAL_METRICS.tier1Accuracy}</span>
        <span>p95 {EVAL_METRICS.p95LatencyMs}ms</span>
        <span>Tier-2 escalate {EVAL_METRICS.tier2EscalateRate}</span>
      </div>
    </div>
  );
}

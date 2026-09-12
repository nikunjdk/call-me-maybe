import { EVAL_METRICS } from "@/lib/evalMetrics";

export function GatePanel() {
  const items = [
    `Tier-1 ${EVAL_METRICS.tier1Accuracy}`,
    `p95 ${EVAL_METRICS.p95LatencyMs}ms`,
    `Tier-2 ${EVAL_METRICS.tier2EscalateRate}`,
  ];

  return (
    <div className="w-full border-b border-white/50 bg-gradient-to-r from-slate-200/70 via-sky-100/80 to-blue-200/70">
      <div className="flex w-full gap-3 overflow-x-auto px-5 py-3 lg:px-10">
        {items.map((item) => (
          <span key={item} className="chip shrink-0 uppercase tracking-[0.1em]">
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}

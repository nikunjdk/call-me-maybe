import type { PolicyVerdict } from "@/lib/types";

function tierLabel(tier: PolicyVerdict["tier"]): string {
  if (tier === 0) return "net";
  return `t${tier}`;
}

export function VerdictChip({ verdict }: { verdict: PolicyVerdict }) {
  const escalate = verdict.verdict === "ESCALATE";
  const parts: string[] = [verdict.verdict];
  if (verdict.trigger !== "none") parts.push(verdict.trigger);
  parts.push(tierLabel(verdict.tier));
  parts.push(verdict.provider_label);
  parts.push(`${verdict.latency_ms}ms`);

  const tone = verdict.degraded
    ? "border-degraded/30 bg-amber-50 text-degraded"
    : verdict.tier === 0
      ? "border-line bg-white/80 text-ink"
      : escalate
        ? "border-escalate/30 bg-rose-50 text-escalate"
        : "border-allow/30 bg-teal-50 text-allow";

  return (
    <span
      className={`mt-2 inline-flex items-center gap-1.5 rounded-full border px-3 py-1 font-mono text-sm tracking-wide ${tone}`}
    >
      {verdict.degraded ? (
        <span
          aria-label="degraded — fail closed"
          className="inline-block size-1.5 rounded-full bg-degraded"
        />
      ) : null}
      {parts.join(" · ")}
      {verdict.degraded ? " · degraded" : ""}
    </span>
  );
}

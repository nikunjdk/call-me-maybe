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

  const color = verdict.degraded
    ? "text-degraded"
    : verdict.tier === 0
      ? "text-ink"
      : escalate
        ? "text-escalate"
        : "text-allow";

  return (
    <span className={`mt-1 inline-flex items-center gap-1.5 font-mono text-[11px] tracking-wide ${color}`}>
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

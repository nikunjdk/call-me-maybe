import type { PolicyVerdict } from "@/lib/types";

export function VerdictChip({ verdict }: { verdict: PolicyVerdict }) {
  const escalate = verdict.verdict === "ESCALATE";
  const parts: string[] = [verdict.verdict];
  if (verdict.trigger !== "none") parts.push(verdict.trigger);
  parts.push(verdict.provider_label);
  parts.push(`${verdict.latency_ms}ms`);

  return (
    <span
      className={`mt-1 inline-block font-mono text-[11px] tracking-wide ${
        escalate ? "text-escalate" : "text-allow"
      }`}
    >
      {parts.join(" · ")}
      {verdict.degraded ? " · degraded" : ""}
    </span>
  );
}

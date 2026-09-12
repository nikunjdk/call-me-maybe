import type { PolicyVerdict } from "@/lib/types";

export function VerdictChip({ verdict }: { verdict: PolicyVerdict }) {
  const escalate = verdict.verdict === "ESCALATE";
  const parts: string[] = [verdict.verdict];
  if (verdict.trigger !== "none") parts.push(verdict.trigger);
  parts.push(verdict.provider_label);
  parts.push(`${verdict.latency_ms}ms`);

  return (
    <span
      className={`mt-2 inline-flex rounded-full border px-3 py-1 font-mono text-sm tracking-wide ${
        escalate
          ? "border-escalate/30 bg-rose-50 text-escalate"
          : "border-allow/30 bg-teal-50 text-allow"
      }`}
    >
      {parts.join(" · ")}
      {verdict.degraded ? " · degraded" : ""}
    </span>
  );
}

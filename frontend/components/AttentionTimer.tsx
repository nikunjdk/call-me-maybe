import { formatClock } from "@/lib/format";

export function AttentionTimer({
  seconds,
  running,
}: {
  seconds: number;
  running: boolean;
}) {
  return (
    <div className="text-center">
      <p className="text-[11px] uppercase tracking-[0.18em] text-muted">
        Your attention
      </p>
      <p
        className={`mt-1 font-display text-6xl tabular-nums leading-none text-ink ${
          running ? "" : "opacity-90"
        }`}
      >
        {formatClock(seconds)}
      </p>
    </div>
  );
}

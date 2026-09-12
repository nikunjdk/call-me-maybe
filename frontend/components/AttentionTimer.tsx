import { formatClock } from "@/lib/format";

export function AttentionTimer({
  seconds,
  running,
}: {
  seconds: number;
  running: boolean;
}) {
  return (
    <div className="shrink-0 rounded-2xl border border-line bg-gradient-to-br from-white to-sky-100 px-5 py-4 text-center lg:min-w-44">
      <p className="kicker">Your attention</p>
      <p
        className={`mt-1 font-display text-6xl tabular-nums leading-none text-ink ${
          running ? "" : "opacity-80"
        }`}
      >
        {formatClock(seconds)}
      </p>
    </div>
  );
}

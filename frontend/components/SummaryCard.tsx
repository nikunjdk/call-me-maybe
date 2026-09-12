import { closingMetric } from "@/lib/format";
import type { Summary } from "@/lib/types";

export function SummaryCard({
  summary,
  onReset,
}: {
  summary: Summary;
  onReset: () => void;
}) {
  return (
    <div className="space-y-8">
      <div>
        <p className="kicker">Summary</p>
        <h1 className="mt-3 font-display text-5xl leading-[0.95] tracking-tight text-ink lg:text-6xl">
          {summary.outcome}
        </h1>
      </div>

      <div className="card px-6 py-7">
        <p className="kicker">Attention saved</p>
        <p className="mt-3 font-display text-4xl leading-snug text-ink lg:text-5xl">
          {closingMetric(
            summary.total_call_seconds,
            summary.human_attention_seconds,
          )}
        </p>
      </div>

      {summary.actions_taken.length > 0 ? (
        <div className="card px-6 py-6">
          <p className="kicker">Actions taken</p>
          <ul className="mt-3 list-disc space-y-1.5 pl-5 text-lg text-fg">
            {summary.actions_taken.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {summary.open_items.length > 0 ? (
        <div className="card px-6 py-6">
          <p className="kicker">Open items</p>
          <ul className="mt-3 list-disc space-y-1.5 pl-5 text-lg text-fg">
            {summary.open_items.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <button
        type="button"
        onClick={onReset}
        className="btn btn-secondary w-full sm:w-auto"
      >
        Start over
      </button>
    </div>
  );
}

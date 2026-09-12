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
        <p className="text-[11px] uppercase tracking-[0.18em] text-muted">
          Summary
        </p>
        <h1 className="mt-2 font-display text-4xl leading-tight text-ink">
          {summary.outcome}
        </h1>
      </div>

      <p className="font-display text-3xl leading-snug text-ink">
        {closingMetric(
          summary.total_call_seconds,
          summary.human_attention_seconds,
        )}
      </p>

      {summary.actions_taken.length > 0 ? (
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-muted">
            Actions taken
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-fg">
            {summary.actions_taken.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {summary.open_items.length > 0 ? (
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-muted">
            Open items
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-fg">
            {summary.open_items.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <button
        type="button"
        onClick={onReset}
        className="text-sm text-muted underline-offset-4 hover:text-ink hover:underline"
      >
        Start over
      </button>
    </div>
  );
}

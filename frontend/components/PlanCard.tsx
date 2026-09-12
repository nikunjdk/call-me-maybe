"use client";

import { useState } from "react";
import type { Plan } from "@/lib/types";

export function PlanCard({
  plan,
  busy,
  onApprove,
  onEdit,
}: {
  plan: Plan;
  busy: boolean;
  onApprove: () => void;
  onEdit: (goal: string) => Promise<boolean>;
}) {
  const [editing, setEditing] = useState(false);
  const [goal, setGoal] = useState(plan.goal);

  return (
    <div className="space-y-8">
      <div>
        <p className="text-[11px] uppercase tracking-[0.18em] text-muted">
          Call plan
        </p>
        <h1 className="mt-2 font-display text-4xl leading-tight text-ink">
          We will not act until you approve.
        </h1>
      </div>

      <div className="space-y-6 rounded-sm border border-line bg-paper px-6 py-6">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-muted">
            Who we&apos;ll call
          </p>
          <p className="mt-1 text-lg text-fg">{plan.target_name}</p>
          <p className="text-sm text-muted">{plan.target_number}</p>
          <p className="mt-1 text-sm text-muted">
            About {plan.estimated_duration}
          </p>
        </div>

        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-muted">
            Opening script
          </p>
          <p className="mt-2 font-display text-xl leading-snug text-ink">
            {plan.opening_script}
          </p>
        </div>

        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-muted">
            Permitted actions
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-fg">
            {plan.permitted_actions.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>

        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-escalate">
            Escalation triggers
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-fg">
            {plan.escalation_triggers.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      </div>

      {editing ? (
        <form
          className="space-y-3"
          onSubmit={async (event) => {
            event.preventDefault();
            const ok = await onEdit(goal.trim());
            if (ok) setEditing(false);
          }}
        >
          <label className="block text-[11px] uppercase tracking-[0.18em] text-muted">
            Revise the goal
          </label>
          <textarea
            value={goal}
            onChange={(event) => setGoal(event.target.value)}
            rows={3}
            className="w-full rounded-sm border border-line bg-paper px-4 py-3 text-base text-fg outline-none focus:border-ink"
          />
          <div className="flex gap-3">
            <button
              type="submit"
              disabled={busy || !goal.trim()}
              className="rounded-sm bg-ink px-5 py-2.5 text-sm tracking-wide text-paper disabled:opacity-60"
            >
              Update plan
            </button>
            <button
              type="button"
              onClick={() => {
                setGoal(plan.goal);
                setEditing(false);
              }}
              className="rounded-sm border border-line px-5 py-2.5 text-sm tracking-wide text-ink"
            >
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <div className="flex gap-3">
          <button
            type="button"
            onClick={onApprove}
            disabled={busy}
            className="rounded-sm bg-ink px-6 py-2.5 text-sm tracking-wide text-paper disabled:opacity-60"
          >
            Approve
          </button>
          <button
            type="button"
            onClick={() => setEditing(true)}
            disabled={busy}
            className="rounded-sm border border-line px-6 py-2.5 text-sm tracking-wide text-ink disabled:opacity-60"
          >
            Edit
          </button>
        </div>
      )}
    </div>
  );
}

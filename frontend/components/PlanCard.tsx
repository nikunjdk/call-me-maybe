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
        <p className="kicker">Call plan</p>
        <h1 className="mt-3 font-display text-5xl leading-[0.95] tracking-tight text-ink lg:text-6xl">
          We won&apos;t call until you say so.
        </h1>
      </div>

      <div className="card space-y-6 px-7 py-8">
        <div>
          <p className="kicker">Who we&apos;ll call</p>
          <p className="mt-2 text-2xl font-semibold text-fg">{plan.target_name}</p>
          <p className="text-lg text-muted">{plan.target_number}</p>
          <p className="mt-1 text-lg text-muted">
            About {plan.estimated_duration}
          </p>
        </div>

        <div>
          <p className="kicker">Opening script</p>
          <p className="mt-2 font-display text-2xl leading-snug text-ink">
            {plan.opening_script}
          </p>
        </div>

        <div className="grid gap-5 lg:grid-cols-2">
          <div className="rounded-2xl border border-allow/25 bg-gradient-to-br from-sky-50 to-teal-50 px-5 py-5">
            <p className="text-sm font-bold uppercase tracking-[0.16em] text-allow">
              Permitted actions
            </p>
            <ul className="mt-3 list-disc space-y-1 pl-5 text-lg text-fg">
              {plan.permitted_actions.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
          <div className="rounded-2xl border border-escalate/20 bg-gradient-to-br from-rose-50 to-slate-50 px-5 py-5">
            <p className="text-sm font-bold uppercase tracking-[0.16em] text-escalate">
              Escalation triggers
            </p>
            <ul className="mt-3 list-disc space-y-1 pl-5 text-lg text-fg">
              {plan.escalation_triggers.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
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
          <label className="kicker block">Revise the goal</label>
          <textarea
            value={goal}
            onChange={(event) => setGoal(event.target.value)}
            rows={3}
            className="field"
          />
          <div className="flex flex-col gap-2 sm:flex-row">
            <button
              type="submit"
              disabled={busy || !goal.trim()}
              className="btn btn-primary w-full sm:w-auto"
            >
              Update plan
            </button>
            <button
              type="button"
              onClick={() => {
                setGoal(plan.goal);
                setEditing(false);
              }}
              className="btn btn-secondary w-full sm:w-auto"
            >
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <div className="flex flex-col gap-2 sm:flex-row">
          <button
            type="button"
            onClick={onApprove}
            disabled={busy}
            className="btn btn-primary w-full sm:w-auto"
          >
            Approve
          </button>
          <button
            type="button"
            onClick={() => setEditing(true)}
            disabled={busy}
            className="btn btn-secondary w-full sm:w-auto"
          >
            Edit
          </button>
        </div>
      )}
    </div>
  );
}

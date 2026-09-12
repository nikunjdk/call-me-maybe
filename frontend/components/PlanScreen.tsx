"use client";

import { PlanCard } from "@/components/PlanCard";
import { ScreenGate } from "@/components/AppChrome";
import { useSession } from "@/lib/session-context";

export function PlanScreen() {
  const session = useSession();
  const plan = session.demo.plan;
  return (
    <ScreenGate>
      {plan ? (
        <PlanCard
          plan={plan}
          busy={session.busy}
          onApprove={session.approve}
          onEdit={session.editPlan}
        />
      ) : (
        <p className="text-sm text-muted">Loading plan…</p>
      )}
    </ScreenGate>
  );
}

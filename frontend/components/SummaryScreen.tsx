"use client";

import { SummaryCard } from "@/components/SummaryCard";
import { ScreenGate } from "@/components/AppChrome";
import { useSession } from "@/lib/session-context";

export function SummaryScreen() {
  const session = useSession();
  const summary = session.demo.summary;
  return (
    <ScreenGate>
      {summary ? (
        <SummaryCard summary={summary} onReset={session.reset} />
      ) : (
        <p className="text-sm text-muted">Waiting for summary…</p>
      )}
    </ScreenGate>
  );
}

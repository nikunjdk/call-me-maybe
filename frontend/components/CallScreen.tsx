"use client";

import { LiveCall } from "@/components/LiveCall";
import { ScreenGate } from "@/components/AppChrome";
import { useSession } from "@/lib/session-context";

export function CallScreen() {
  const session = useSession();
  return (
    <ScreenGate>
      <LiveCall
        state={session.demo.state}
        turns={session.demo.turns}
        attentionSeconds={session.attentionSeconds}
        attentionRunning={
          Boolean(session.demo.attentionStartedAt) && !session.demo.summary
        }
        escalationReason={session.demo.escalationReason}
        voiceStatus={session.voiceStatus}
        busy={session.busy}
        onTakeover={session.takeover}
      />
    </ScreenGate>
  );
}

import { AttentionTimer } from "@/components/AttentionTimer";
import { TakeoverButton } from "@/components/TakeoverButton";
import { VerdictChip } from "@/components/VerdictChip";
import type { SessionState, Turn, VoiceStatus } from "@/lib/types";

function statusLabel(state: SessionState | null): string {
  switch (state) {
    case "PLAN_APPROVED":
      return "Approved — waiting for dial";
    case "DIALING":
      return "Dialing";
    case "IN_CALL":
      return "Agent on the line";
    case "ESCALATING":
      return "Policy boundary";
    case "HUMAN_CONTROL":
      return "You are on the line";
    case "ENDED":
      return "Call ended";
    default:
      return state ?? "";
  }
}

function speakerLabel(speaker: Turn["speaker"]): string {
  if (speaker === "rep") return "Rep";
  if (speaker === "agent") return "Agent";
  return "You";
}

export function LiveCall({
  state,
  turns,
  attentionSeconds,
  attentionRunning,
  escalationReason,
  voiceStatus,
  busy,
  onTakeover,
}: {
  state: SessionState | null;
  turns: Turn[];
  attentionSeconds: number;
  attentionRunning: boolean;
  escalationReason: string | null;
  voiceStatus: VoiceStatus;
  busy: boolean;
  onTakeover: () => void;
}) {
  const voiceNote =
    voiceStatus === "muted"
      ? "Browser leg muted"
      : voiceStatus === "live"
        ? "Browser leg live"
        : voiceStatus === "unavailable"
          ? "Voice token not available — UI still runs"
          : "Joining call muted";

  return (
    <div className="space-y-8">
      <div className="flex items-start justify-between gap-6">
        <div>
          <p className="text-[11px] uppercase tracking-[0.18em] text-muted">
            Live call
          </p>
          <h1 className="mt-2 font-display text-3xl leading-tight text-ink">
            {statusLabel(state)}
          </h1>
          <p className="mt-2 text-sm text-muted">{voiceNote}</p>
          {escalationReason ? (
            <p className="mt-2 text-sm text-escalate">{escalationReason}</p>
          ) : null}
        </div>
        <AttentionTimer seconds={attentionSeconds} running={attentionRunning} />
      </div>

      <ol className="space-y-4" aria-live="polite">
        {turns.length === 0 ? (
          <li className="text-sm text-muted">Waiting for the first turn…</li>
        ) : (
          turns.map((turn, index) => (
            <li key={`${turn.ts}-${index}`} className="border-t border-line pt-4">
              <p className="text-[11px] uppercase tracking-[0.14em] text-muted">
                {speakerLabel(turn.speaker)}
              </p>
              <p className="mt-1 text-base leading-relaxed text-fg">{turn.text}</p>
              {turn.verdict ? <VerdictChip verdict={turn.verdict} /> : null}
            </li>
          ))
        )}
      </ol>

      <TakeoverButton
        ready={state === "ESCALATING"}
        live={state === "HUMAN_CONTROL"}
        busy={busy}
        onTakeover={onTakeover}
      />
    </div>
  );
}

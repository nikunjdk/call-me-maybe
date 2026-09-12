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
    <div className="space-y-6">
      <div className="card flex flex-col gap-6 px-6 py-6 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <p className="kicker">Live call</p>
          <h1 className="mt-3 font-display text-4xl leading-tight tracking-tight text-ink lg:text-5xl">
            {statusLabel(state)}
          </h1>
          <p className="mt-3 text-lg text-muted">{voiceNote}</p>
          <p className="mt-1 text-sm uppercase tracking-[0.14em] text-muted">
            ElevenLabs Scribe · each rep turn is gated
          </p>
          {escalationReason ? (
            <p className="mt-3 rounded-xl border border-escalate/25 bg-rose-50 px-3 py-2 text-lg text-escalate">
              {escalationReason}
            </p>
          ) : null}
        </div>
        <AttentionTimer seconds={attentionSeconds} running={attentionRunning} />
      </div>

      <ol className="space-y-3" aria-live="polite">
        {turns.length === 0 ? (
          <li className="card px-6 py-8 text-lg text-muted">
            Waiting for the first turn…
          </li>
        ) : (
          turns.map((turn, index) => {
            const you = turn.speaker === "user";
            return (
              <li
                key={`${turn.ts}-${index}`}
                className={`max-w-[92%] rounded-2xl border border-line px-5 py-4 lg:max-w-[85%] ${
                  you
                    ? "ml-auto bg-gradient-to-br from-sky-100 to-blue-50"
                    : turn.speaker === "agent"
                      ? "bg-white/80"
                      : "bg-slate-100/80"
                }`}
              >
                <p className="text-sm font-bold uppercase tracking-[0.14em] text-muted">
                  {speakerLabel(turn.speaker)}
                  {turn.source === "elevenlabs" ? " · ElevenLabs" : ""}
                </p>
                <p className="mt-1 text-lg leading-relaxed text-fg">
                  {turn.text}
                </p>
                {turn.verdict ? <VerdictChip verdict={turn.verdict} /> : null}
              </li>
            );
          })
        )}
      </ol>

      <div className="sticky bottom-4 z-10">
        <TakeoverButton
          ready={state === "ESCALATING"}
          live={state === "HUMAN_CONTROL"}
          busy={busy}
          onTakeover={onTakeover}
        />
      </div>
    </div>
  );
}

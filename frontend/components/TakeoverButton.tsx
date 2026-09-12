export function TakeoverButton({
  ready,
  live,
  busy,
  onTakeover,
}: {
  ready: boolean;
  live: boolean;
  busy: boolean;
  onTakeover: () => void;
}) {
  if (live) {
    return (
      <p className="rounded-sm border border-ink bg-ink px-6 py-4 text-center text-sm tracking-wide text-paper">
        You&apos;re live — the rep is already briefed.
      </p>
    );
  }

  if (!ready) return null;

  return (
    <button
      type="button"
      onClick={onTakeover}
      disabled={busy}
      className="w-full rounded-sm bg-escalate px-6 py-4 text-center text-base font-medium tracking-wide text-paper disabled:opacity-60"
    >
      Take over the call
    </button>
  );
}

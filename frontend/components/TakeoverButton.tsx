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
      <p className="rounded-2xl border border-sky-200 bg-gradient-to-r from-sky-500 to-blue-600 px-6 py-5 text-center text-lg font-bold tracking-wide text-white shadow-lg">
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
      className="btn btn-danger w-full shadow-lg"
    >
      Take over the call
    </button>
  );
}

"use client";

import Image from "next/image";
import { MaybeCanvas } from "@/components/MaybeCanvas";
import { screenFor } from "@/lib/screen";
import { SessionProvider, useSession } from "@/lib/session-context";

const STEPS = ["Ticket", "Plan", "Call", "Done"] as const;

function Header() {
  const { demo, reset } = useSession();
  const hasSession = Boolean(demo.sessionId);
  const step = screenFor(demo.state, demo.summary);

  return (
    <header className="relative z-20 w-full border-b border-white/40 bg-white/25 backdrop-blur-md">
      <div className="mx-auto w-full max-w-7xl px-8 lg:px-10">
        <div className="flex w-full items-center justify-between gap-4 py-5 lg:py-6">
        <button
          type="button"
          onClick={reset}
          className="flex min-h-14 items-center gap-4 text-left"
        >
          <span className="flex size-14 overflow-hidden rounded-2xl border border-line bg-white p-1.5 shadow-sm">
            <Image
              src="/logo.png"
              alt="CallMeMaybe"
              width={56}
              height={56}
              className="size-full object-contain"
              priority
            />
          </span>
          <span className="font-display text-3xl tracking-tight text-ink lg:text-4xl">
            Call me, maybe
          </span>
        </button>
        {hasSession ? (
          <button type="button" onClick={reset} className="chip min-h-11 px-4">
            Start over
          </button>
        ) : null}
        </div>
        {!hasSession ? (
          <div className="max-w-3xl pb-8 lg:pb-10">
            <h1 className="font-display text-4xl leading-[1.05] tracking-tight text-ink lg:text-5xl">
              We won&apos;t waste your time, and we&apos;ll call you when it&apos;s relevant.
            </h1>
            <p className="mt-4 text-lg leading-snug text-fg lg:text-xl">
              Drop the ticket. We&apos;ll take the hold music. You only pick up when
              a human decision is actually required.
            </p>
          </div>
        ) : (
          <ol className="grid w-full grid-cols-4 gap-2 pb-5">
          {STEPS.map((label, index) => {
            const n = index + 1;
            const active = n === step;
            const done = n < step;
            return (
              <li
                key={label}
                className={`rounded-full px-3 py-2 text-center text-sm font-bold tracking-wide ${
                  active
                    ? "bg-gradient-to-r from-violet-400 to-indigo-600 text-white shadow-md"
                    : done
                      ? "bg-violet-100 text-ink"
                      : "bg-white/70 text-muted"
                }`}
              >
                {label}
              </li>
            );
          })}
        </ol>
        )}
      </div>
    </header>
  );
}

function ErrorBanner() {
  const { error } = useSession();
  if (!error) return null;
  return (
    <p className="mb-6 rounded-2xl border border-escalate/30 bg-white/80 px-4 py-3 text-lg text-escalate">
      {error}
    </p>
  );
}

export function AppChrome({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider>
      <div className="pointer-events-none fixed inset-0 z-0">
        <MaybeCanvas />
      </div>
      <div className="relative z-10 min-h-dvh">
        <Header />
        <main className="mx-auto w-full max-w-7xl px-8 py-8 pb-28 lg:px-10 lg:py-10 lg:pb-32">
          <ErrorBanner />
          {children}
        </main>
      </div>
    </SessionProvider>
  );
}

export function ScreenGate({
  children,
  empty,
}: {
  children: React.ReactNode;
  empty?: React.ReactNode;
}) {
  const { routeReady } = useSession();
  if (!routeReady) {
    return empty ?? <p className="text-lg text-muted">Loading…</p>;
  }
  return children;
}

"use client";

import Image from "next/image";
import { GatePanel } from "@/components/GatePanel";
import { SessionProvider, useSession } from "@/lib/session-context";

function Header() {
  const { demo, reset } = useSession();
  const hasSession = Boolean(demo.sessionId);

  return (
    <header className="mx-auto flex max-w-3xl items-center justify-between gap-3 px-8 py-5">
      <button
        type="button"
        onClick={reset}
        className="flex items-center gap-3 text-left"
      >
        <Image
          src="/logo.png"
          alt="CallMeMaybe"
          width={40}
          height={40}
          className="size-10 object-contain"
          priority
        />
        <span className="font-display text-xl tracking-tight text-ink">
          CallMeMaybe
        </span>
      </button>
      {hasSession ? (
        <button
          type="button"
          onClick={reset}
          className="text-sm text-muted underline-offset-4 hover:text-ink hover:underline"
        >
          Start over
        </button>
      ) : null}
    </header>
  );
}

function ErrorBanner() {
  const { error } = useSession();
  if (!error) return null;
  return (
    <p className="mb-6 rounded-sm border border-escalate/30 bg-paper px-4 py-3 text-sm text-escalate">
      {error}
    </p>
  );
}

export function AppChrome({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider>
      <Header />
      <GatePanel />
      <div className="mx-auto max-w-3xl px-8 py-10 pb-24">
        <ErrorBanner />
        {children}
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
    return empty ?? <p className="text-sm text-muted">Loading…</p>;
  }
  return children;
}

"use client";

import { useParams, usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as api from "./api";
import { applyEvent, isLiveCallSignal, turnsFromSession } from "./applyEvent";
import { fakeEventsMode, STORAGE_KEY, wsUrl } from "./env";
import { runFakeReplay } from "./fakeReplay";
import { pathFor, routes } from "./paths";
import { screenFor } from "./screen";
import { connectIfNeeded, destroyVoice, joinMuted, unmuteCall } from "./twilioDevice";
import type {
  EventEnvelope,
  Extracted,
  Plan,
  SessionState,
  Summary,
  Turn,
  VoiceStatus,
} from "./types";

export type DemoState = {
  sessionId: string | null;
  state: SessionState | null;
  extracted: Extracted | null;
  plan: Plan | null;
  summary: Summary | null;
  turns: Turn[];
  escalationReason: string | null;
  attentionStartedAt: number | null;
};

const INITIAL: DemoState = {
  sessionId: null,
  state: null,
  extracted: null,
  plan: null,
  summary: null,
  turns: [],
  escalationReason: null,
  attentionStartedAt: null,
};

const VOICE_STATES: SessionState[] = [
  "PLAN_PENDING",
  "PLAN_APPROVED",
  "DIALING",
  "IN_CALL",
  "ESCALATING",
];

export function useDemoSession() {
  const params = useParams<{ id?: string }>();
  const pathname = usePathname();
  const router = useRouter();

  const [demo, setDemo] = useState<DemoState>(INITIAL);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [voiceStatus, setVoiceStatus] = useState<VoiceStatus>("off");
  const [hydrated, setHydrated] = useState(false);

  const liveCallRef = useRef(false);
  const replayStartedRef = useRef(false);
  const voiceAttemptedRef = useRef(false);
  const takenOverRef = useRef(false);
  const takeoverWaiters = useRef<Array<() => void>>([]);
  const replayAbort = useRef<AbortController | null>(null);
  const fakeSource = useRef(false);
  const sessionIdRef = useRef<string | null>(null);

  const emit = useCallback((event: EventEnvelope, fromFake = false) => {
    if (!fromFake && isLiveCallSignal(event)) {
      liveCallRef.current = true;
    }
    setDemo((current) => applyEvent(current, event));
  }, []);

  const waitForTakeover = useCallback(() => {
    if (takenOverRef.current) return Promise.resolve();
    return new Promise<void>((resolve) => {
      takeoverWaiters.current.push(resolve);
    });
  }, []);

  useEffect(() => {
    const urlId = typeof params.id === "string" ? params.id : undefined;
    const stored = sessionStorage.getItem(STORAGE_KEY);
    const id = urlId ?? stored ?? null;

    if (!id) {
      setHydrated(true);
      return;
    }

    if (sessionIdRef.current === id) {
      setHydrated(true);
      return;
    }

    let cancelled = false;
    api
      .getSession(id)
      .then((session) => {
        if (cancelled) return;
        sessionIdRef.current = session.session_id;
        sessionStorage.setItem(STORAGE_KEY, session.session_id);
        setDemo({
          sessionId: session.session_id,
          state: session.state,
          extracted: session.extracted,
          plan: session.plan,
          summary: session.summary,
          turns: turnsFromSession(session),
          escalationReason: null,
          attentionStartedAt: session.human_unmuted_ts
            ? session.human_unmuted_ts * 1000
            : session.state === "HUMAN_CONTROL" || session.state === "SUMMARIZED"
              ? Date.now()
              : null,
        });
      })
      .catch(() => {
        if (cancelled) return;
        sessionIdRef.current = null;
        sessionStorage.removeItem(STORAGE_KEY);
        setDemo(INITIAL);
      })
      .finally(() => {
        if (!cancelled) setHydrated(true);
      });
    return () => {
      cancelled = true;
    };
  }, [params.id]);

  useEffect(() => {
    if (!demo.sessionId) return;
    let stopped = false;
    let socket: WebSocket | null = null;
    let retry: number | undefined;

    const connect = () => {
      socket = new WebSocket(wsUrl(demo.sessionId!));
      socket.onmessage = (message) => {
        try {
          const event = JSON.parse(message.data as string) as EventEnvelope;
          if (!fakeSource.current && isLiveCallSignal(event)) {
            liveCallRef.current = true;
          }
          setDemo((current) => applyEvent(current, event));
        } catch {
          // ignore malformed frames
        }
      };
      socket.onclose = () => {
        if (stopped) return;
        retry = window.setTimeout(connect, 1000);
      };
    };
    connect();
    return () => {
      stopped = true;
      if (retry !== undefined) window.clearTimeout(retry);
      socket?.close();
    };
  }, [demo.sessionId]);

  useEffect(() => {
    if (!demo.sessionId || demo.state !== "PLAN_APPROVED") return;
    if (replayStartedRef.current) return;
    const mode = fakeEventsMode();
    if (mode === "off") return;

    const delay = mode === "on" ? 0 : 2000;
    const timer = window.setTimeout(() => {
      if (liveCallRef.current || replayStartedRef.current) return;
      replayStartedRef.current = true;
      fakeSource.current = true;
      const controller = new AbortController();
      replayAbort.current = controller;
      void runFakeReplay({
        sessionId: demo.sessionId!,
        emit: (event) => emit(event, true),
        signal: controller.signal,
        waitForTakeover,
      }).finally(() => {
        fakeSource.current = false;
      });
    }, delay);

    return () => {
      window.clearTimeout(timer);
    };
  }, [demo.sessionId, demo.state, emit, waitForTakeover]);

  useEffect(() => {
    if (!demo.sessionId || !demo.state) return;
    if (voiceAttemptedRef.current) return;
    if (!VOICE_STATES.includes(demo.state)) return;
    voiceAttemptedRef.current = true;
    let cancelled = false;
    void (async () => {
      const token = await api.getVoiceToken(demo.sessionId!);
      if (cancelled) return;
      if (!token) {
        setVoiceStatus("unavailable");
        return;
      }
      const ok = await joinMuted(token);
      if (cancelled) return;
      setVoiceStatus(ok ? "muted" : "unavailable");
    })();
    return () => {
      cancelled = true;
    };
  }, [demo.sessionId, demo.state]);

  useEffect(() => {
    if (demo.state !== "DIALING" && demo.state !== "IN_CALL") return;
    const timer = window.setTimeout(() => {
      void connectIfNeeded().then((ok) => {
        if (ok) {
          setVoiceStatus((status) =>
            status === "off" || status === "unavailable" ? "muted" : status,
          );
        }
      });
    }, 1500);
    return () => window.clearTimeout(timer);
  }, [demo.state]);

  useEffect(() => {
    if (!demo.attentionStartedAt || demo.summary) return;
    const timer = window.setInterval(() => setNow(Date.now()), 250);
    return () => window.clearInterval(timer);
  }, [demo.attentionStartedAt, demo.summary]);

  useEffect(() => {
    if (!demo.sessionId) return;
    if (demo.state !== "ENDED" && demo.state !== "SUMMARIZED") return;
    void api
      .getSummary(demo.sessionId)
      .then((summary) => {
        setDemo((current) => {
          if (current.summary && !current.summary.outcome.toLowerCase().startsWith("stub")) {
            return current;
          }
          if (demo.state === "SUMMARIZED" || !summary.outcome.toLowerCase().startsWith("stub")) {
            return { ...current, summary };
          }
          return current;
        });
      })
      .catch(() => {
        // leave local summary in place
      });
  }, [demo.sessionId, demo.state]);

  useEffect(() => {
    return () => {
      replayAbort.current?.abort();
      destroyVoice();
    };
  }, []);

  const ensureSession = useCallback(async (): Promise<string> => {
    if (demo.sessionId) return demo.sessionId;
    const sessionId = await api.createSession();
    sessionIdRef.current = sessionId;
    sessionStorage.setItem(STORAGE_KEY, sessionId);
    setDemo((current) => ({
      ...current,
      sessionId,
      state: "CREATED",
    }));
    return sessionId;
  }, [demo.sessionId]);

  const upload = useCallback(
    async (file: File) => {
      setBusy(true);
      setError(null);
      try {
        const sessionId = await ensureSession();
        const extracted = await api.uploadDocument(sessionId, file);
        setDemo((current) => ({
          ...current,
          sessionId,
          extracted,
          state: "EXTRACTED",
        }));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Upload failed");
      } finally {
        setBusy(false);
      }
    },
    [ensureSession],
  );

  const requestPlan = useCallback(
    async (goal: string) => {
      if (!demo.sessionId) return;
      setBusy(true);
      setError(null);
      try {
        const plan = await api.requestPlan(demo.sessionId, goal);
        setDemo((current) => ({
          ...current,
          plan,
          state: "PLAN_PENDING",
        }));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Plan failed");
      } finally {
        setBusy(false);
      }
    },
    [demo.sessionId],
  );

  const editPlan = useCallback(
    async (goal: string) => {
      if (!demo.sessionId) return false;
      setBusy(true);
      setError(null);
      try {
        const plan = await api.requestPlan(demo.sessionId, goal);
        setDemo((current) => ({
          ...current,
          plan,
          state: "PLAN_PENDING",
        }));
        return true;
      } catch (err) {
        const message =
          err instanceof api.ApiError && err.status === 409
            ? "Server will not re-plan from this state yet."
            : err instanceof Error
              ? err.message
              : "Could not update plan";
        setError(message);
        return false;
      } finally {
        setBusy(false);
      }
    },
    [demo.sessionId],
  );

  const approve = useCallback(async () => {
    if (!demo.sessionId) return;
    setBusy(true);
    setError(null);
    try {
      // Device must be registered before A adds the browser conference leg.
      if (voiceStatus !== "muted" && voiceStatus !== "live") {
        const token = await api.getVoiceToken(demo.sessionId);
        if (token) {
          voiceAttemptedRef.current = true;
          const ok = await joinMuted(token);
          setVoiceStatus(ok ? "muted" : "unavailable");
        } else {
          setVoiceStatus("unavailable");
        }
      }
      const result = await api.approvePlan(demo.sessionId);
      setDemo((current) => ({
        ...current,
        state: result.state,
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approve failed");
    } finally {
      setBusy(false);
    }
  }, [demo.sessionId, voiceStatus]);

  const takeover = useCallback(async () => {
    if (!demo.sessionId) return;
    setBusy(true);
    setError(null);
    const localOnly =
      fakeSource.current ||
      voiceStatus === "unavailable" ||
      voiceStatus === "off";
    try {
      const ok = await api.takeover(demo.sessionId);
      if (!ok && !localOnly) {
        setError("Takeover failed — the browser leg may not have joined yet.");
        setBusy(false);
        return;
      }
    } catch (err) {
      if (!localOnly) {
        setError(err instanceof Error ? err.message : "Takeover failed");
        setBusy(false);
        return;
      }
    }
    unmuteCall();
    takenOverRef.current = true;
    setVoiceStatus((status) => (status === "muted" ? "live" : status));
    setDemo((current) => ({
      ...current,
      state: "HUMAN_CONTROL",
      attentionStartedAt: current.attentionStartedAt ?? Date.now(),
    }));
    takeoverWaiters.current.forEach((resolve) => resolve());
    takeoverWaiters.current = [];
    setBusy(false);
  }, [demo.sessionId, voiceStatus]);

  const reset = useCallback(() => {
    replayAbort.current?.abort();
    replayAbort.current = null;
    replayStartedRef.current = false;
    liveCallRef.current = false;
    voiceAttemptedRef.current = false;
    takenOverRef.current = false;
    fakeSource.current = false;
    takeoverWaiters.current = [];
    sessionIdRef.current = null;
    destroyVoice();
    sessionStorage.removeItem(STORAGE_KEY);
    setVoiceStatus("off");
    setError(null);
    setHydrated(true);
    setDemo(INITIAL);
    router.replace(routes.home);
  }, [router]);

  const attentionSeconds = useMemo(() => {
    if (demo.summary) return demo.summary.human_attention_seconds;
    if (!demo.attentionStartedAt) return 0;
    return Math.floor((now - demo.attentionStartedAt) / 1000);
  }, [demo.attentionStartedAt, demo.summary, now]);

  const screen = screenFor(demo.state, demo.summary);
  const dest = pathFor(demo.sessionId, demo.state, demo.summary);
  const onAuthPath =
    pathname === routes.login ||
    pathname === routes.logout ||
    pathname.startsWith("/auth");

  useEffect(() => {
    if (!hydrated || onAuthPath) return;
    if (pathname !== dest) router.replace(dest);
  }, [hydrated, onAuthPath, pathname, dest, router]);

  return {
    demo,
    screen,
    busy,
    error,
    attentionSeconds,
    voiceStatus,
    hydrated,
    routeReady: hydrated && (onAuthPath || pathname === dest),
    dest,
    upload,
    requestPlan,
    editPlan,
    approve,
    takeover,
    reset,
  };
}

export type DemoSession = ReturnType<typeof useDemoSession>;

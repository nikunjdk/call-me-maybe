"use client";

import { createContext, useContext, type ReactNode } from "react";
import { useDemoSession, type DemoSession } from "./useDemoSession";

const SessionContext = createContext<DemoSession | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const value = useDemoSession();
  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
}

export function useSession(): DemoSession {
  const value = useContext(SessionContext);
  if (!value) {
    throw new Error("useSession must be used within SessionProvider");
  }
  return value;
}

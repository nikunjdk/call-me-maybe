import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { API_BASE } from "./lib/env";
import { authDisabled } from "./lib/authDisabled";
import { pathFor, routes, type SessionStep } from "./lib/paths";
import type { Session } from "./lib/types";

function sessionStep(pathname: string): { id: string; step: SessionStep } | null {
  const match = pathname.match(/^\/session\/([^/]+)(?:\/(plan|call|summary))?\/?$/);
  if (!match) return null;
  const step = (match[2] ?? "intent") as SessionStep;
  return { id: match[1], step };
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (pathname === routes.login) {
    const target = authDisabled() ? routes.home : routes.authLogin;
    return NextResponse.redirect(new URL(target, request.url));
  }

  if (pathname === routes.logout) {
    const target = authDisabled() ? routes.home : routes.authLogout;
    return NextResponse.redirect(new URL(target, request.url));
  }

  if (!authDisabled()) {
    const { auth0 } = await import("./lib/auth0");
    if (auth0) {
      const authResponse = await auth0.middleware(request);
      if (pathname.startsWith("/auth")) return authResponse;
      const session = await auth0.getSession(request);
      if (!session) {
        const login = new URL(routes.authLogin, request.url);
        return NextResponse.redirect(login);
      }
    }
  }

  const parsed = sessionStep(pathname);
  if (parsed) {
    try {
      const res = await fetch(`${API_BASE}/api/session/${parsed.id}`, {
        cache: "no-store",
      });
      if (!res.ok) {
        return NextResponse.redirect(new URL(routes.home, request.url));
      }
      const session = (await res.json()) as Session;
      const dest = pathFor(session.session_id, session.state, session.summary);
      const current = routes.step(parsed.id, parsed.step);
      // Client-side replay can sit on /summary while C is still PLAN_APPROVED.
      if (parsed.step === "summary" && dest === routes.call(parsed.id)) {
        return NextResponse.next();
      }
      if (dest !== current) {
        return NextResponse.redirect(new URL(dest, request.url));
      }
    } catch {
      return NextResponse.redirect(new URL(routes.home, request.url));
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|icon.png|logo.png|sitemap.xml|robots.txt).*)",
  ],
};

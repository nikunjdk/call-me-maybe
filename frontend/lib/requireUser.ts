import { redirect } from "next/navigation";
import { auth0 } from "./auth0";
import { authDisabled } from "./authDisabled";
import { routes } from "./paths";

export async function requireUser(): Promise<void> {
  if (authDisabled() || !auth0) return;
  try {
    const session = await auth0.getSession();
    if (!session) redirect(routes.login);
  } catch {
    redirect(routes.login);
  }
}

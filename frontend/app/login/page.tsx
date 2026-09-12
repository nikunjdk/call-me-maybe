import { redirect } from "next/navigation";
import { authDisabled } from "@/lib/authDisabled";
import { routes } from "@/lib/paths";

export const dynamic = "force-dynamic";

export default function LoginPage() {
  if (authDisabled()) redirect(routes.home);
  redirect(routes.authLogin);
}

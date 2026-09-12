import Link from "next/link";
import { routes } from "@/lib/paths";

export default function NotFound() {
  return (
    <div className="space-y-3">
      <h1 className="font-display text-3xl text-ink">Page not found</h1>
      <p className="text-sm text-muted">That URL is not part of the demo flow.</p>
      <Link href={routes.home} className="text-sm text-ink underline underline-offset-4">
        Go to start
      </Link>
    </div>
  );
}

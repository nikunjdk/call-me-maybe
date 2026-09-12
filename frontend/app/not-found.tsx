import Link from "next/link";
import { routes } from "@/lib/paths";

export default function NotFound() {
  return (
    <div className="card space-y-3 px-5 py-6">
      <h1 className="font-display text-4xl text-ink">Page not found</h1>
      <p className="text-lg text-muted">That URL is not part of the demo flow.</p>
      <Link href={routes.home} className="btn btn-primary w-full sm:w-auto">
        Go to start
      </Link>
    </div>
  );
}

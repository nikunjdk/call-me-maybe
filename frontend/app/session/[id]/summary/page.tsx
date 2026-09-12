import { SummaryScreen } from "@/components/SummaryScreen";
import { requireUser } from "@/lib/requireUser";

export const dynamic = "force-dynamic";

export default async function SummaryPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  await requireUser();
  await params;
  return <SummaryScreen />;
}

import { PlanScreen } from "@/components/PlanScreen";
import { requireUser } from "@/lib/requireUser";

export const dynamic = "force-dynamic";

export default async function PlanPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  await requireUser();
  await params;
  return <PlanScreen />;
}

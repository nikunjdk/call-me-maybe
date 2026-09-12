import { IntentScreen } from "@/components/IntentScreen";
import { requireUser } from "@/lib/requireUser";

export const dynamic = "force-dynamic";

export default async function SessionIntentPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  await requireUser();
  await params;
  return <IntentScreen />;
}

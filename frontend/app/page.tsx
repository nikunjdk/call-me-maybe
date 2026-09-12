import { IntentScreen } from "@/components/IntentScreen";
import { requireUser } from "@/lib/requireUser";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  await requireUser();
  return <IntentScreen />;
}

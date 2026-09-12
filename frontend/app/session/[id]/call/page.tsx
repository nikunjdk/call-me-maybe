import { CallScreen } from "@/components/CallScreen";
import { requireUser } from "@/lib/requireUser";

export const dynamic = "force-dynamic";

export default async function CallPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  await requireUser();
  await params;
  return <CallScreen />;
}

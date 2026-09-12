"use client";

import { UploadIntent } from "@/components/UploadIntent";
import { ScreenGate } from "@/components/AppChrome";
import { useSession } from "@/lib/session-context";

export function IntentScreen() {
  const session = useSession();
  return (
    <ScreenGate>
      <UploadIntent
        extracted={session.demo.extracted}
        busy={session.busy}
        onUpload={session.upload}
        onPlan={session.requestPlan}
      />
    </ScreenGate>
  );
}

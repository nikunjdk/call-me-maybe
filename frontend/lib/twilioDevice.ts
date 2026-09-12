import type { Call, Device } from "@twilio/voice-sdk";

let device: Device | null = null;
let call: Call | null = null;
let registered = false;

export async function joinMuted(token: string): Promise<boolean> {
  try {
    destroyVoice();
    const { Device: VoiceDevice } = await import("@twilio/voice-sdk");
    device = new VoiceDevice(token, { logLevel: "error" });
    device.on("incoming", (incoming) => {
      incoming.accept();
      incoming.mute(true);
      call = incoming;
    });
    await device.register();
    registered = true;
    return true;
  } catch (error) {
    console.warn("Twilio Voice register failed", error);
    destroyVoice();
    return false;
  }
}

/** Outbound join if the incoming conference ring never arrived. */
export async function connectIfNeeded(): Promise<boolean> {
  if (call) return true;
  if (!device || !registered) return false;
  try {
    call = await device.connect();
    call.mute(true);
    return true;
  } catch (error) {
    console.warn("Twilio Voice connect failed", error);
    return false;
  }
}

export function unmuteCall(): void {
  call?.mute(false);
}

export function destroyVoice(): void {
  try {
    call?.disconnect();
    try {
      void device?.unregister();
    } catch {
      // ignore
    }
    device?.destroy();
  } catch {
    // ignore
  }
  call = null;
  device = null;
  registered = false;
}

import type { Call, Device } from "@twilio/voice-sdk";

let device: Device | null = null;
let call: Call | null = null;

export async function joinMuted(token: string): Promise<boolean> {
  try {
    destroyVoice();
    const { Device: VoiceDevice } = await import("@twilio/voice-sdk");
    device = new VoiceDevice(token, { logLevel: "error" });
    call = await device.connect();
    call.mute(true);
    return true;
  } catch (error) {
    console.warn("Twilio Voice join failed", error);
    destroyVoice();
    return false;
  }
}

export function unmuteCall(): void {
  call?.mute(false);
}

export function destroyVoice(): void {
  try {
    call?.disconnect();
    device?.destroy();
  } catch {
    // ignore
  }
  call = null;
  device = null;
}

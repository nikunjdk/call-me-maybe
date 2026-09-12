export function formatClock(totalSeconds: number): string {
  const seconds = Math.max(0, Math.floor(totalSeconds));
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${minutes}:${rest.toString().padStart(2, "0")}`;
}

export function formatAttentionPhrase(seconds: number): string {
  if (seconds < 60) {
    return `${seconds} second${seconds === 1 ? "" : "s"}`;
  }
  return formatClock(seconds);
}

export function closingMetric(
  totalCallSeconds: number,
  humanAttentionSeconds: number,
): string {
  return `Total call ${formatClock(totalCallSeconds)} · Your attention ${formatAttentionPhrase(humanAttentionSeconds)}`;
}

export function authDisabled(): boolean {
  return process.env.AUTH_DISABLED !== "false";
}

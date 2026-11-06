const LOCALE = "en-GB";

export function formatDate(value: string | Date | null | undefined): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat(LOCALE, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(value));
}

export function formatDateTime(value: string | Date | null | undefined): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat(LOCALE, {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function formatRelative(value: string | Date | null | undefined): string {
  if (!value) return "Never";
  const seconds = Math.round((new Date(value).getTime() - Date.now()) / 1000);
  const units: Array<[Intl.RelativeTimeFormatUnit, number]> = [
    ["year", 31_536_000],
    ["month", 2_592_000],
    ["day", 86_400],
    ["hour", 3_600],
    ["minute", 60],
  ];
  const rtf = new Intl.RelativeTimeFormat(LOCALE, { numeric: "auto" });
  for (const [unit, size] of units) {
    if (Math.abs(seconds) >= size) return rtf.format(Math.round(seconds / size), unit);
  }
  return "just now";
}

export function formatNumber(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : value.toLocaleString(LOCALE);
}

/** "Mozilla/5.0 (X11; Linux…) Chrome/…" -> "Chrome on Linux" */
export function describeUserAgent(ua: string | null): string {
  if (!ua) return "Unknown device";
  const browser =
    /Edg\//.test(ua) ? "Edge"
    : /Firefox\//.test(ua) ? "Firefox"
    : /Chrome\//.test(ua) ? "Chrome"
    : /Safari\//.test(ua) ? "Safari"
    : /curl|python|httpx/i.test(ua) ? "API client"
    : "Browser";
  const os =
    /Windows/.test(ua) ? "Windows"
    : /Mac OS X/.test(ua) ? "macOS"
    : /Android/.test(ua) ? "Android"
    : /iPhone|iPad/.test(ua) ? "iOS"
    : /Linux/.test(ua) ? "Linux"
    : "";
  return os ? `${browser} on ${os}` : browser;
}

export function formatAuditAction(action: string): string {
  const labels: Record<string, string> = {
    "auth.setup": "Completed initial setup",
    "auth.login": "Signed in",
    "auth.logout": "Signed out",
    "auth.lockout": "Account locked",
    "user.create": "Created user",
    "user.update": "Updated user",
    "user.delete": "Deleted user",
    "user.password_reset": "Reset password",
    "user.password_change": "Changed password",
    "user.profile_update": "Updated profile",
    "user.unlock": "Unlocked user",
    "user.sessions_revoke": "Revoked sessions",
    "session.revoke": "Revoked a session",
    "role.create": "Created role",
    "role.update": "Updated role permissions",
    "role.delete": "Deleted role",
    "auth.mfa_challenge": "Passed password, awaiting 2FA",
    "auth.password_reset_request": "Requested a password reset",
    "user.password_reset_by_email": "Reset password by email link",
    "user.mfa_enable": "Turned on two-factor",
    "user.mfa_disable": "Turned off two-factor",
    "user.mfa_reset": "Reset two-factor (admin)",
    "user.mfa_recovery_codes": "Generated new recovery codes",
    "user.mfa_change": "Two-factor change attempt",
  };
  return labels[action] ?? action;
}

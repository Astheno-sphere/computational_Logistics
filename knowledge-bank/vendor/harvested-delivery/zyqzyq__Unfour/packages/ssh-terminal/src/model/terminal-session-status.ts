import type { SshSessionSummary } from "@unfour/command-client";
import type { ConnectionStatusValue, TFunction } from "@unfour/ui";

export function terminalSessionStatus(
  session: SshSessionSummary | null | undefined,
): ConnectionStatusValue {
  if (!session) {
    return "disconnected";
  }

  if (session.status === "failed") {
    return "error";
  }
  if (session.status === "degraded" || session.status === "reconnecting") {
    return "reconnecting";
  }
  return session.status;
}

export function terminalSessionStatusLabel(
  session: SshSessionSummary | null | undefined,
  t?: TFunction,
) {
  const translate = (key: string, params?: Record<string, string | number>) =>
    t ? t(key, params) : fallbackLabel(key, params);

  if (!session) {
    return translate("ssh.sessionStatus.disconnected");
  }
  if (session.status === "reconnecting") {
    return translate("ssh.sessionStatus.reconnecting", {
      attempt: session.reconnectAttempt,
    });
  }
  if (session.status === "degraded") {
    return translate("ssh.sessionStatus.degraded");
  }
  return translate(`ssh.sessionStatus.${session.status}`);
}

// Plain-English fallback for callers without an i18n translator (keeps the
// model usable in tests and non-React contexts).
function fallbackLabel(key: string, params?: Record<string, string | number>) {
  const status = key.replace("ssh.sessionStatus.", "");
  if (status === "reconnecting") {
    return `reconnecting ${params?.attempt ?? 0}/3`;
  }
  if (status === "degraded") {
    return "connection degraded";
  }
  return status;
}

export function shouldRenderTerminalPane(
  session: SshSessionSummary | null | undefined,
  eventCount = 0,
) {
  if (!session) {
    return false;
  }
  if (eventCount > 0) {
    return true;
  }
  return ["connected", "degraded", "reconnecting"].includes(session.status);
}

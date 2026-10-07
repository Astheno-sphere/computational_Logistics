import type { SshSessionSummary } from "@unfour/command-client";
import { ConnectionStatus, useI18n } from "@unfour/ui";
import {
  terminalSessionStatus,
  terminalSessionStatusLabel,
} from "../model/terminal-session-status";

export function TerminalSessionTabMeta({ session }: { session: SshSessionSummary }) {
  const { t } = useI18n();
  return (
    <ConnectionStatus
      dotOnly
      label={terminalSessionStatusLabel(session, t)}
      status={terminalSessionStatus(session)}
      variant="dot"
    />
  );
}

import { useMemo, type ReactNode } from "react";
import { ConnectionStatus, StatusBar, useI18n } from "@unfour/ui";
import { useWorkspaceStore } from "@unfour/workspace-core";
import { useSshConnections } from "../hooks/useSshConnections";
import { useTerminalSessions } from "../hooks/useTerminalSessions";
import { useTerminalStore } from "../model/terminal-state";
import { sshEndpointLabel } from "../model/ssh-connection-state";
import {
  terminalSessionStatus,
  terminalSessionStatusLabel,
} from "../model/terminal-session-status";

export function TerminalStatusBar({
  rightAccessory,
  workspaceId,
  workspaceName,
}: {
  rightAccessory?: ReactNode;
  workspaceId: string;
  workspaceName: string;
}) {
  const { t } = useI18n();
  const selectedSshConnectionId = useWorkspaceStore((state) => state.selectedSshConnectionId);
  const activeSessionId = useTerminalStore((state) => state.activeSessionId);
  const connectionsQuery = useSshConnections(workspaceId);
  const sessionsQuery = useTerminalSessions(workspaceId);
  const selectedConnection = useMemo(
    () => connectionsQuery.data?.find((item) => item.id === selectedSshConnectionId) ?? null,
    [connectionsQuery.data, selectedSshConnectionId],
  );
  const activeSession = useMemo(
    () => sessionsQuery.data?.find((item) => item.sessionId === activeSessionId) ?? null,
    [activeSessionId, sessionsQuery.data],
  );

  return (
    <StatusBar>
      <div className="flex min-w-0 items-center gap-3">
        <span className="truncate">{workspaceName}</span>
        <span className="truncate">{sshEndpointLabel(selectedConnection)}</span>
        <ConnectionStatus
          label={terminalSessionStatusLabel(activeSession, t)}
          status={terminalSessionStatus(activeSession)}
          variant="dot"
        />
      </div>
      <div className="flex shrink-0 items-center gap-3">
        <span>
          {activeSession
            ? `${activeSession.cols}×${activeSession.rows}`
            : t("ssh.status.noPty")}
        </span>
        <span>{selectedConnection?.authKind ?? t("ssh.status.noAuth")}</span>
        <span>{t("ssh.status.encoding")}</span>
        {rightAccessory}
      </div>
    </StatusBar>
  );
}

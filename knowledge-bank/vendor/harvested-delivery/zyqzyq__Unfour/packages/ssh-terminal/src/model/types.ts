import type { SshConnection, SshSessionEvent, SshSessionSummary } from "@unfour/command-client";

export type TerminalConnectionState =
  | "not-configured"
  | "idle"
  | "connecting"
  | "connected"
  | "error"
  | "disconnected"
  | "reconnecting";

export type TerminalSplitMode = "single" | "vertical" | "horizontal";

export type TerminalPaneId = "primary" | "secondary";

export type TerminalEventLevel = "info" | "warning" | "error";

export type TerminalLogEvent = SshSessionEvent & {
  level?: TerminalEventLevel;
};

export type TerminalSessionTabState = {
  connection?: SshConnection | null;
  modified?: boolean;
  session: SshSessionSummary;
  title: string;
};

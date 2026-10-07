import { useTerminalStore } from "../model/terminal-state";

export function useTerminalLayout() {
  return {
    activeSessionId: useTerminalStore((state) => state.activeSessionId),
    exportedLog: useTerminalStore((state) => state.exportedLog),
    setActiveSessionId: useTerminalStore((state) => state.setActiveSessionId),
    setExportedLog: useTerminalStore((state) => state.setExportedLog),
    setTerminalEvents: useTerminalStore((state) => state.setTerminalEvents),
    terminalEvents: useTerminalStore((state) => state.terminalEvents),
  };
}

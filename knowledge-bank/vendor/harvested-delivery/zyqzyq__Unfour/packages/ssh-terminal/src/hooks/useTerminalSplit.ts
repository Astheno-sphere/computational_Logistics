import { useTerminalStore } from "../model/terminal-state";

export function useTerminalSplit() {
  return {
    mode: useTerminalStore((state) => state.splitMode),
    setMode: useTerminalStore((state) => state.setSplitMode),
  };
}

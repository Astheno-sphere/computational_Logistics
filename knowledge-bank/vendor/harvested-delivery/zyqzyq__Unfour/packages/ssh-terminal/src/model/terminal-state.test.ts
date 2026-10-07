import { describe, expect, it } from "vitest";
import {
  MAX_CACHED_TERMINAL_WORKSPACES,
  MAX_DISMISSED_SESSION_IDS,
  useTerminalStore,
} from "./terminal-state";

function resetStore() {
  useTerminalStore.setState({
    byWorkspace: {},
    activeSessionId: null,
    dismissedSessionIds: [],
    exportedLog: null,
    frontendFailedSessions: {},
    searchOpen: false,
    searchQuery: "",
    splitMode: "single",
    terminalEvents: [],
    terminalInput: "",
    terminalSearchAddon: null,
    workspaceId: null,
    workspaceOrder: [],
  });
}

describe("terminal-state store", () => {
  it("stores and clears the search addon reference", () => {
    resetStore();
    const store = useTerminalStore.getState();
    expect(store.terminalSearchAddon).toBeNull();

    const mockAddon = {
      findNext: () => true,
      findPrevious: () => false,
      clearDecorations: () => {},
      dispose: () => {},
    };
    store.setTerminalSearchAddon(mockAddon);
    expect(useTerminalStore.getState().terminalSearchAddon).toBe(mockAddon);

    store.setTerminalSearchAddon(null);
    expect(useTerminalStore.getState().terminalSearchAddon).toBeNull();
  });

  it("preserves search addon across workspace activation", () => {
    resetStore();
    const store = useTerminalStore.getState();

    const mockAddon = {
      findNext: () => true,
      findPrevious: () => false,
      clearDecorations: () => {},
      dispose: () => {},
    };
    store.setTerminalSearchAddon(mockAddon);
    store.activateWorkspace("ws-1");

    // Addon should be preserved when activating a workspace.
    expect(useTerminalStore.getState().terminalSearchAddon).toBe(mockAddon);
    expect(useTerminalStore.getState().workspaceId).toBe("ws-1");
  });

  it("keeps streaming output chunks immutable for incremental rendering", () => {
    resetStore();
    const store = useTerminalStore.getState();

    store.appendTerminalEvents([
      {
        sessionId: "s1",
        kind: "output",
        data: "line 1\r\n",
        createdAt: "2026-01-01T00:00:00Z",
      },
    ]);
    store.appendTerminalEvents([
      {
        sessionId: "s1",
        kind: "output",
        data: "line 2\r\n",
        createdAt: "2026-01-01T00:00:01Z",
      },
    ]);

    const events = useTerminalStore.getState().terminalEvents;
    expect(events).toHaveLength(2);
    expect(events.map((event) => event.data)).toEqual(["line 1\r\n", "line 2\r\n"]);
    expect(events[1].createdAt).toBe("2026-01-01T00:00:01Z");
  });

  it("bounds retained output for a long-lived session", () => {
    resetStore();
    const store = useTerminalStore.getState();
    const events = Array.from({ length: 2_100 }, (_, index) => ({
      sessionId: "s1",
      kind: "output" as const,
      data: `${index}\r\n`,
      createdAt: `2026-01-01T00:00:${String(index % 60).padStart(2, "0")}Z`,
    }));

    store.appendTerminalEvents(events);

    const retained = useTerminalStore.getState().terminalEvents;
    expect(retained).toHaveLength(2_000);
    expect(retained[0].data).toBe("100\r\n");
    expect(retained.at(-1)?.data).toBe("2099\r\n");
  });

  it("splits oversized output and enforces the per-session character budget", () => {
    resetStore();
    const store = useTerminalStore.getState();

    store.appendTerminalEvents([
      {
        sessionId: "s1",
        kind: "output",
        data: "x".repeat(1_100_000),
        createdAt: "2026-01-01T00:00:00Z",
      },
    ]);

    const retained = useTerminalStore.getState().terminalEvents;
    expect(retained.length).toBeGreaterThan(1);
    expect(retained.reduce((total, event) => total + event.data.length, 0)).toBeLessThanOrEqual(
      1_000_000,
    );
    expect(retained.every((event) => event.data.length <= 64_000)).toBe(true);
  });

  it("keeps input and different sessions as separate terminal events", () => {
    resetStore();
    const store = useTerminalStore.getState();

    store.appendTerminalEvents([
      {
        sessionId: "s1",
        kind: "output",
        data: "line 1\r\n",
        createdAt: "2026-01-01T00:00:00Z",
      },
      {
        sessionId: "s1",
        kind: "input",
        data: "vim file.txt",
        createdAt: "2026-01-01T00:00:01Z",
      },
      {
        sessionId: "s2",
        kind: "output",
        data: "line 2\r\n",
        createdAt: "2026-01-01T00:00:02Z",
      },
    ]);

    const events = useTerminalStore.getState().terminalEvents;
    expect(events).toHaveLength(3);
    expect(events.map((event) => event.kind)).toEqual(["output", "input", "output"]);
  });

  it("clears events for a specific session", () => {
    resetStore();
    const store = useTerminalStore.getState();

    store.appendTerminalEvents([
      {
        sessionId: "s1",
        kind: "output",
        data: "session 1",
        createdAt: "2026-01-01T00:00:00Z",
      },
      {
        sessionId: "s2",
        kind: "output",
        data: "session 2",
        createdAt: "2026-01-01T00:00:00Z",
      },
    ]);

    store.clearTerminalSessionEvents("s1");
    const events = useTerminalStore.getState().terminalEvents;
    expect(events).toHaveLength(1);
    expect(events[0].sessionId).toBe("s2");
  });

  it("hydrates persisted history once without replacing streamed output", () => {
    resetStore();
    const store = useTerminalStore.getState();
    const history = [
      {
        sessionId: "s1",
        kind: "output",
        data: "persisted\r\n",
        createdAt: "2026-01-01T00:00:00Z",
      },
    ];

    store.hydrateTerminalSession("s1", history);
    store.hydrateTerminalSession("s1", history);
    store.hydrateTerminalSession("s2", [
      {
        ...history[0],
        sessionId: "s2",
        data: "other session\r\n",
      },
    ]);

    const events = useTerminalStore.getState().terminalEvents;
    expect(events).toHaveLength(2);
    expect(events.map((event) => event.data)).toEqual([
      "persisted\r\n",
      "other session\r\n",
    ]);
  });

  it("toggles search open state", () => {
    resetStore();
    const store = useTerminalStore.getState();

    expect(store.searchOpen).toBe(false);
    store.setSearchOpen(true);
    expect(useTerminalStore.getState().searchOpen).toBe(true);
    store.setSearchOpen(false);
    expect(useTerminalStore.getState().searchOpen).toBe(false);
  });

  it("keeps only the most recently used workspace terminal slices", () => {
    resetStore();
    const store = useTerminalStore.getState();

    for (let index = 0; index <= MAX_CACHED_TERMINAL_WORKSPACES; index += 1) {
      store.activateWorkspace(`ws-${index}`);
      store.appendTerminalEvents([
        {
          sessionId: `session-${index}`,
          kind: "output",
          data: `workspace-${index}`,
          createdAt: "2026-01-01T00:00:00Z",
        },
      ]);
    }

    const state = useTerminalStore.getState();
    expect(state.workspaceOrder).toEqual(["ws-1", "ws-2", "ws-3", "ws-4"]);
    expect(Object.keys(state.byWorkspace)).toEqual(["ws-1", "ws-2", "ws-3"]);

    store.activateWorkspace("ws-0");
    expect(useTerminalStore.getState().terminalEvents).toEqual([]);
  });

  it("bounds dismissed session ids per workspace", () => {
    resetStore();
    const store = useTerminalStore.getState();
    for (let index = 0; index <= MAX_DISMISSED_SESSION_IDS; index += 1) {
      store.dismissSession(`session-${index}`);
    }

    const dismissed = useTerminalStore.getState().dismissedSessionIds;
    expect(dismissed).toHaveLength(MAX_DISMISSED_SESSION_IDS);
    expect(dismissed[0]).toBe("session-1");
    expect(dismissed.at(-1)).toBe(`session-${MAX_DISMISSED_SESSION_IDS}`);
  });
});

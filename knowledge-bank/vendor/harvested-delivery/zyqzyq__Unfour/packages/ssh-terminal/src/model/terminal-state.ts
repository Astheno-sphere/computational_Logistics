import { create } from "zustand";
import type { SshSessionEvent, SshSessionSummary } from "@unfour/command-client";
import type { TerminalSplitMode } from "./types";

type SearchAddonLike = {
  findNext: (term: string) => boolean;
  findPrevious: (term: string) => boolean;
  clearDecorations: () => void;
  dispose: () => void;
};

// The slice of terminal UI state that is scoped to a single workspace. The
// search addon is intentionally NOT part of the slice: it is a handle to the
// live xterm instance owned by the mounted `TerminalPage`, so it stays global
// and is never partitioned or cleared on workspace switch.
type TerminalSlice = {
  activeSessionId: string | null;
  dismissedSessionIds: string[];
  exportedLog: string | null;
  frontendFailedSessions: Record<string, SshSessionSummary>;
  searchOpen: boolean;
  searchQuery: string;
  splitMode: TerminalSplitMode;
  terminalEvents: SshSessionEvent[];
  terminalInput: string;
};

type TerminalStore = {
  // Bounded per-workspace archive. `activateWorkspace` swaps the flat fields
  // below to the slice for the newly active workspace and retains only the most
  // recently used workspace buffers.
  byWorkspace: Record<string, TerminalSlice>;
  activeSessionId: string | null;
  dismissedSessionIds: string[];
  exportedLog: string | null;
  frontendFailedSessions: Record<string, SshSessionSummary>;
  searchOpen: boolean;
  searchQuery: string;
  splitMode: TerminalSplitMode;
  terminalEvents: SshSessionEvent[];
  terminalInput: string;
  terminalSearchAddon: SearchAddonLike | null;
  workspaceId: string | null;
  workspaceOrder: string[];
  activateWorkspace: (workspaceId: string) => void;
  addFrontendFailedSession: (session: SshSessionSummary) => void;
  appendTerminalEvents: (events: SshSessionEvent[]) => void;
  clearTerminalSessionEvents: (sessionId: string | null) => void;
  dismissSession: (sessionId: string) => void;
  hydrateTerminalSession: (sessionId: string, events: SshSessionEvent[]) => void;
  resetTerminalEvents: () => void;
  setActiveSessionId: (sessionId: string | null) => void;
  setExportedLog: (content: string | null) => void;
  setSearchOpen: (open: boolean) => void;
  setSearchQuery: (query: string) => void;
  setSplitMode: (mode: TerminalSplitMode) => void;
  setTerminalSearchAddon: (addon: SearchAddonLike | null) => void;
  startTerminalSession: (sessionId: string, events: SshSessionEvent[]) => void;
  setTerminalEvents: (events: SshSessionEvent[]) => void;
  setTerminalInput: (input: string) => void;
};

export function defaultTerminalInput() {
  return "";
}

function createDefaultSlice(): TerminalSlice {
  return {
    activeSessionId: null,
    dismissedSessionIds: [],
    exportedLog: null,
    frontendFailedSessions: {},
    searchOpen: false,
    searchQuery: "",
    splitMode: "single",
    terminalEvents: [],
    terminalInput: defaultTerminalInput(),
  };
}

function sliceFromFlat(state: TerminalStore): TerminalSlice {
  return {
    activeSessionId: state.activeSessionId,
    dismissedSessionIds: state.dismissedSessionIds,
    exportedLog: state.exportedLog,
    frontendFailedSessions: state.frontendFailedSessions,
    searchOpen: state.searchOpen,
    searchQuery: state.searchQuery,
    splitMode: state.splitMode,
    terminalEvents: state.terminalEvents,
    terminalInput: state.terminalInput,
  };
}

function flatFromSlice(slice: TerminalSlice) {
  return {
    activeSessionId: slice.activeSessionId,
    dismissedSessionIds: slice.dismissedSessionIds,
    exportedLog: slice.exportedLog,
    frontendFailedSessions: slice.frontendFailedSessions,
    searchOpen: slice.searchOpen,
    searchQuery: slice.searchQuery,
    splitMode: slice.splitMode,
    terminalEvents: slice.terminalEvents,
    terminalInput: slice.terminalInput,
  };
}

export const useTerminalStore = create<TerminalStore>((set) => ({
  byWorkspace: {},
  activeSessionId: null,
  dismissedSessionIds: [],
  exportedLog: null,
  frontendFailedSessions: {},
  searchOpen: false,
  searchQuery: "",
  splitMode: "single",
  terminalEvents: [],
  terminalInput: defaultTerminalInput(),
  terminalSearchAddon: null,
  workspaceId: null,
  workspaceOrder: [],
  activateWorkspace: (workspaceId) =>
    set((state) => {
      if (state.workspaceId === workspaceId) {
        return state;
      }
      // Archive the current flat slice under the previously active workspace
      // (if any), then load the target workspace's recent slice. Bounded LRU
      // retention avoids both switch flicker and process-lifetime growth.
      const nextByWorkspace: Record<string, TerminalSlice> =
        state.workspaceId !== null
          ? { ...state.byWorkspace, [state.workspaceId]: sliceFromFlat(state) }
          : { ...state.byWorkspace };
      const nextSlice = nextByWorkspace[workspaceId] ?? createDefaultSlice();
      // The active workspace lives in the flat fields, so remove its archived
      // snapshot instead of retaining a stale duplicate of the same buffer.
      delete nextByWorkspace[workspaceId];
      const workspaceOrder = [
        ...state.workspaceOrder.filter((id) => id !== workspaceId),
        workspaceId,
      ].slice(-MAX_CACHED_TERMINAL_WORKSPACES);
      const retainedWorkspaceIds = new Set(workspaceOrder);
      for (const archivedWorkspaceId of Object.keys(nextByWorkspace)) {
        if (!retainedWorkspaceIds.has(archivedWorkspaceId)) {
          delete nextByWorkspace[archivedWorkspaceId];
        }
      }
      return {
        ...flatFromSlice(nextSlice),
        byWorkspace: nextByWorkspace,
        // The search addon belongs to the live xterm instance and must survive
        // workspace switches untouched.
        terminalSearchAddon: state.terminalSearchAddon,
        workspaceId,
        workspaceOrder,
      };
    }),
  addFrontendFailedSession: (session) =>
    set((state) => {
      // Remove any previous failed session for the same connectionId so only
      // one stale tab per connection accumulates.
      const next = { ...state.frontendFailedSessions };
      for (const [id, existing] of Object.entries(next)) {
        if (existing.connectionId === session.connectionId) {
          delete next[id];
        }
      }
      next[session.sessionId] = session;
      return { frontendFailedSessions: next };
    }),
  appendTerminalEvents: (events) =>
    set((state) => ({
      terminalEvents: appendBoundedTerminalEvents(state.terminalEvents, events),
    })),
  clearTerminalSessionEvents: (sessionId) =>
    set((state) => ({
      exportedLog: null,
      terminalEvents: sessionId
        ? state.terminalEvents.filter((event) => event.sessionId !== sessionId)
        : [],
    })),
  dismissSession: (sessionId) =>
    set((state) => {
      // The backend keeps closed sessions in its list as history, so a closed
      // tab would otherwise reappear on the next poll. Track dismissed ids and
      // filter them out of the visible tab strip.
      const nextFailed = { ...state.frontendFailedSessions };
      delete nextFailed[sessionId];
      return {
        activeSessionId: state.activeSessionId === sessionId ? null : state.activeSessionId,
        dismissedSessionIds: [
          ...state.dismissedSessionIds.filter((id) => id !== sessionId),
          sessionId,
        ].slice(-MAX_DISMISSED_SESSION_IDS),
        frontendFailedSessions: nextFailed,
        terminalEvents: state.terminalEvents.filter((event) => event.sessionId !== sessionId),
      };
    }),
  hydrateTerminalSession: (sessionId, events) =>
    set((state) => {
      if (state.terminalEvents.some((event) => event.sessionId === sessionId)) {
        return state;
      }
      return {
        terminalEvents: appendBoundedTerminalEvents(state.terminalEvents, events),
      };
    }),
  resetTerminalEvents: () =>
    set({
      activeSessionId: null,
      dismissedSessionIds: [],
      exportedLog: null,
      frontendFailedSessions: {},
      terminalEvents: [],
      terminalInput: defaultTerminalInput(),
    }),
  setActiveSessionId: (activeSessionId) => set({ activeSessionId }),
  setExportedLog: (exportedLog) => set({ exportedLog }),
  setSearchOpen: (searchOpen) => set({ searchOpen }),
  setSearchQuery: (searchQuery) => set({ searchQuery }),
  setSplitMode: (splitMode) => set({ splitMode }),
  setTerminalSearchAddon: (terminalSearchAddon) => set({ terminalSearchAddon }),
  startTerminalSession: (sessionId, events) =>
    set((state) => ({
      activeSessionId: sessionId,
      dismissedSessionIds: state.dismissedSessionIds.filter((id) => id !== sessionId),
      exportedLog: null,
      terminalEvents: appendBoundedTerminalEvents(
        state.terminalEvents.filter((event) => event.sessionId !== sessionId),
        events,
      ),
    })),
  setTerminalEvents: (terminalEvents) =>
    set({ terminalEvents: appendBoundedTerminalEvents([], terminalEvents) }),
  setTerminalInput: (terminalInput) => set({ terminalInput }),
}));

const MAX_TERMINAL_EVENTS_PER_SESSION = 2_000;
const MAX_TERMINAL_CHARS_PER_SESSION = 1_000_000;
const MAX_TERMINAL_EVENTS_PER_WORKSPACE = 8_000;
const MAX_TERMINAL_CHARS_PER_WORKSPACE = 4_000_000;
const MAX_TERMINAL_EVENT_CHARS = 64_000;
export const MAX_CACHED_TERMINAL_WORKSPACES = 4;
export const MAX_DISMISSED_SESSION_IDS = 100;

function appendBoundedTerminalEvents(
  currentEvents: SshSessionEvent[],
  nextEvents: SshSessionEvent[],
) {
  const terminalEvents = [...currentEvents, ...splitOversizedTerminalEvents(nextEvents)];
  const usageBySession = new Map<string, { chars: number; events: number }>();
  const retained: SshSessionEvent[] = [];
  let workspaceChars = 0;
  let workspaceEvents = 0;

  // Retain the newest bounded tail for every session. Events stay immutable so
  // TerminalPane can use object identity as its incremental-render cursor even
  // when older entries are discarded from a long-lived stream.
  for (let index = terminalEvents.length - 1; index >= 0; index -= 1) {
    const event = terminalEvents[index];
    const usage = usageBySession.get(event.sessionId) ?? { chars: 0, events: 0 };
    if (
      workspaceEvents >= MAX_TERMINAL_EVENTS_PER_WORKSPACE ||
      workspaceChars + event.data.length > MAX_TERMINAL_CHARS_PER_WORKSPACE ||
      usage.events >= MAX_TERMINAL_EVENTS_PER_SESSION ||
      usage.chars + event.data.length > MAX_TERMINAL_CHARS_PER_SESSION
    ) {
      continue;
    }
    retained.push(event);
    workspaceChars += event.data.length;
    workspaceEvents += 1;
    usageBySession.set(event.sessionId, {
      chars: usage.chars + event.data.length,
      events: usage.events + 1,
    });
  }

  return retained.reverse();
}

function splitOversizedTerminalEvents(events: SshSessionEvent[]) {
  return events.flatMap((event) => {
    if (event.data.length <= MAX_TERMINAL_EVENT_CHARS) {
      return event;
    }
    const chunks: SshSessionEvent[] = [];
    for (let offset = 0; offset < event.data.length; offset += MAX_TERMINAL_EVENT_CHARS) {
      chunks.push({
        ...event,
        data: event.data.slice(offset, offset + MAX_TERMINAL_EVENT_CHARS),
      });
    }
    return chunks;
  });
}
export function redactTerminalLog(value: string) {
  return value
    .split(/\r?\n/)
    .map((line) => {
      if (
        /(^|\b)(authorization|cookie|proxy-authorization|x-api-key|x-auth-token|password|passphrase|private[-_ ]?key)(\b|:|=)/i.test(
          line,
        )
      ) {
        return "<redacted>";
      }

      return line;
    })
    .join("\n");
}

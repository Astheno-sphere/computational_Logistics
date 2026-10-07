// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import type { SftpTransferState } from "@unfour/command-client";
import {
  DEFAULT_SFTP_PANEL_WIDTH,
  MAX_SFTP_PANEL_WIDTH,
  MIN_SFTP_PANEL_WIDTH,
  clampSftpPanelWidth,
  maxSftpPanelWidth,
  preferFresherTransfer,
  useSftpStore,
} from "./sftp-state";

afterEach(() => {
  window.localStorage.clear();
  useSftpStore.setState({
    panelWidth: DEFAULT_SFTP_PANEL_WIDTH,
    tabs: {},
    transfers: {},
  });
});

function transfer(
  overrides: Partial<SftpTransferState> & Pick<SftpTransferState, "transferId" | "status">,
): SftpTransferState {
  return {
    workspaceId: "workspace-1",
    sessionId: "session-a",
    connectionId: "connection-a",
    direction: "download",
    localPath: "C:/tmp/a.bin",
    remotePath: "/tmp/a.bin",
    transferredBytes: 0,
    totalBytes: 100,
    bytesPerSecond: 0,
    error: null,
    startedAt: "2026-01-01T00:00:00.000Z",
    finishedAt: null,
    ...overrides,
  };
}

describe("SFTP panel state", () => {
  it("clamps the resize width to a recoverable range and the available surface", () => {
    expect(clampSftpPanelWidth(10)).toBe(MIN_SFTP_PANEL_WIDTH);
    expect(clampSftpPanelWidth(2_000)).toBe(MAX_SFTP_PANEL_WIDTH);
    expect(clampSftpPanelWidth(800, 800)).toBe(480);
    expect(maxSftpPanelWidth(1_280)).toBe(MAX_SFTP_PANEL_WIDTH);
    expect(maxSftpPanelWidth(500)).toBe(MIN_SFTP_PANEL_WIDTH);
  });

  it("persists the last width and scopes open/path state by terminal session and connection", () => {
    const state = useSftpStore.getState();
    state.setPanelWidth(420);
    state.setPanelOpen("session-a", "connection-a", true);
    state.setPanelPath("session-a", "connection-a", "/srv/a");

    expect(window.localStorage.getItem("unfour.ssh.sftp-panel-width")).toBe("420");
    expect(useSftpStore.getState().tabs["session-a"]).toMatchObject({
      connectionId: "connection-a",
      open: true,
      path: "/srv/a",
    });
    expect(useSftpStore.getState().tabs["session-b"]).toBeUndefined();
  });

  it("scopes multi-select paths per session and clears them on navigate", () => {
    const state = useSftpStore.getState();
    state.setSelectedPath("session-a", "connection-a", "/srv/a/one.txt");
    state.setSelectedPaths(
      "session-a",
      "connection-a",
      ["/srv/a/one.txt", "/srv/a/two.txt"],
      "/srv/a/two.txt",
    );

    expect(useSftpStore.getState().tabs["session-a"]).toMatchObject({
      selectedPath: "/srv/a/two.txt",
      selectedPaths: ["/srv/a/one.txt", "/srv/a/two.txt"],
    });

    state.setPanelPath("session-a", "connection-a", "/srv/b");
    expect(useSftpStore.getState().tabs["session-a"]).toMatchObject({
      path: "/srv/b",
      selectedPath: null,
      selectedPaths: [],
    });
  });

  it("does not let a stale running frame overwrite a finished transfer", () => {
    const finished = transfer({
      transferId: "t-1",
      status: "success",
      transferredBytes: 100,
      finishedAt: "2026-01-01T00:00:01.000Z",
    });
    const staleRunning = transfer({
      transferId: "t-1",
      status: "running",
      transferredBytes: 40,
    });
    expect(preferFresherTransfer(finished, staleRunning)).toEqual(finished);
    expect(preferFresherTransfer(staleRunning, finished)).toEqual(finished);
  });

  it("keeps higher transferred progress when both frames are still running", () => {
    const older = transfer({ transferId: "t-2", status: "running", transferredBytes: 10 });
    const newer = transfer({ transferId: "t-2", status: "running", transferredBytes: 80 });
    expect(preferFresherTransfer(older, newer)).toEqual(newer);
    expect(preferFresherTransfer(newer, older)).toEqual(newer);
  });

  it("drops finished transfers that the bounded backend no longer returns", () => {
    const state = useSftpStore.getState();
    for (let index = 0; index < 40; index += 1) {
      state.upsertTransfer(
        transfer({
          transferId: `finished-${index}`,
          status: "success",
          startedAt: `2026-01-01T00:00:${String(index).padStart(2, "0")}.000Z`,
        }),
      );
    }
    state.upsertTransfer(
      transfer({ transferId: "active", status: "running", startedAt: "2026-01-02" }),
    );

    const retained = useSftpStore.getState().transfers["session-a"];
    expect(retained.filter((item) => item.status === "success")).toHaveLength(32);
    expect(retained.some((item) => item.transferId === "active")).toBe(true);

    state.setTransfers("session-a", []);
    expect(useSftpStore.getState().transfers["session-a"]).toEqual([
      expect.objectContaining({ transferId: "active" }),
    ]);
  });

  it("removes tab and transfer state when a terminal session closes", () => {
    const state = useSftpStore.getState();
    state.setPanelOpen("session-a", "connection-a", true);
    state.upsertTransfer(transfer({ transferId: "t-closed", status: "success" }));

    state.removeSession("session-a");

    expect(useSftpStore.getState().tabs["session-a"]).toBeUndefined();
    expect(useSftpStore.getState().transfers["session-a"]).toBeUndefined();
  });
});

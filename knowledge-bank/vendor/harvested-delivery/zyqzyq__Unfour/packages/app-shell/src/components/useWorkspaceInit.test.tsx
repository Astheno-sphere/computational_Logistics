// @vitest-environment jsdom
import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { useWorkspaceStore } from "@unfour/workspace-core";
import { useWorkspaceInit } from "./useWorkspaceInit";

describe("useWorkspaceInit", () => {
  beforeEach(() => {
    useWorkspaceStore.getState().setActiveWorkspace("stale-workspace");
  });

  it("keeps the frontend active workspace synchronized with command-bus state", async () => {
    const { rerender } = renderHook(
      ({ workspaceId }) => useWorkspaceInit(workspaceId, undefined, undefined),
      { initialProps: { workspaceId: "workspace-one" } },
    );

    await waitFor(() =>
      expect(useWorkspaceStore.getState().activeWorkspaceId).toBe("workspace-one"),
    );

    rerender({ workspaceId: "workspace-two" });
    await waitFor(() =>
      expect(useWorkspaceStore.getState().activeWorkspaceId).toBe("workspace-two"),
    );
  });
});

import { describe, expect, it } from "vitest";
import { mockStore, mockWorkspace } from "./state";
import { handleWorkspaceMock } from "./workspace";

describe("workspace browser mock", () => {
  it("requires every active environment exactly once when reordering", () => {
    const activeIds = mockStore.workspaceEnvironments
      .filter(
        (environment) =>
          environment.workspaceId === mockWorkspace.id && !environment.deletedAt,
      )
      .map((environment) => environment.id);
    expect(activeIds.length).toBeGreaterThan(0);

    expect(() =>
      handleWorkspaceMock("workspace_environments_reorder", {
        workspaceId: mockWorkspace.id,
        environmentIds: [],
      }),
    ).toThrow("every active environment exactly once");
    expect(() =>
      handleWorkspaceMock("workspace_environments_reorder", {
        workspaceId: mockWorkspace.id,
        environmentIds: [activeIds[0], activeIds[0]],
      }),
    ).toThrow("every active environment exactly once");
    expect(() =>
      handleWorkspaceMock("workspace_environments_reorder", {
        workspaceId: mockWorkspace.id,
        environmentIds: activeIds,
      }),
    ).not.toThrow();
  });
});

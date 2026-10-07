import { useEffect } from "react";
import type { DatabaseConnection } from "@unfour/command-client";
import { useWorkspaceStore } from "@unfour/workspace-core";

type WorkspaceState = ReturnType<typeof useWorkspaceStore.getState>;
type LayoutData = Parameters<WorkspaceState["hydrateLayout"]>[0];

export function useWorkspaceInit(
  activeWorkspaceIdFromQuery: string | undefined,
  layoutData: LayoutData | undefined,
  databaseConnections: DatabaseConnection[] | undefined,
) {
  const {
    activeWorkspaceId,
    hydrateLayout,
    selectedDatabaseConnectionId,
    setActiveWorkspace,
    setSelectedDatabaseConnection,
  } = useWorkspaceStore();

  useEffect(() => {
    if (activeWorkspaceIdFromQuery && activeWorkspaceIdFromQuery !== activeWorkspaceId) {
      setActiveWorkspace(activeWorkspaceIdFromQuery);
    }
  }, [activeWorkspaceId, setActiveWorkspace, activeWorkspaceIdFromQuery]);

  useEffect(() => {
    if (layoutData) {
      hydrateLayout(layoutData);
    }
  }, [hydrateLayout, layoutData]);

  useEffect(() => {
    if (
      selectedDatabaseConnectionId &&
      databaseConnections &&
      !databaseConnections.some((item) => item.id === selectedDatabaseConnectionId)
    ) {
      setSelectedDatabaseConnection(null);
    }
  }, [selectedDatabaseConnectionId, setSelectedDatabaseConnection, databaseConnections]);
}

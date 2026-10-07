import type { DatabaseConnection } from "@unfour/command-client";
import type {
  DatabaseTableWorkspaceTab,
  PendingTableChange,
  TableEditing,
} from "./types";
import {
  buildPendingChangesSql,
  databaseRowKey,
  stageRowDelete,
  stageRowInsert,
  stageRowUpdate,
} from "./table-row-editing";

type TableTabPatch =
  | Partial<Omit<DatabaseTableWorkspaceTab, "id" | "kind">>
  | ((tab: DatabaseTableWorkspaceTab) => Partial<Omit<DatabaseTableWorkspaceTab, "id" | "kind">>);

export function createTableEditing({
  applyPendingChanges,
  connection,
  connected,
  mutationPending,
  tab,
  updateTableTab,
}: {
  applyPendingChanges: () => Promise<void>;
  connection: DatabaseConnection | null;
  connected: boolean;
  mutationPending: boolean;
  tab: DatabaseTableWorkspaceTab | null;
  updateTableTab: (tabId: string, patch: TableTabPatch) => void;
}): TableEditing | null {
  if (!tab?.tableView || !connection || !connected || connection.readOnly) return null;

  const primaryKeyColumns = tab.table.columns
    .filter((column) => column.primaryKey)
    .map((column) => column.name);
  const updatePending = (
    updater: (changes: PendingTableChange[]) => PendingTableChange[],
  ) => updateTableTab(tab.id, (current) => ({ error: null, pendingChanges: updater(current.pendingChanges) }));

  return {
    canInsert: tab.table.kind === "table",
    canUpdateDelete: primaryKeyColumns.length > 0 && tab.table.kind === "table",
    pending: mutationPending,
    pendingChanges: tab.pendingChanges,
    previewSql: buildPendingChangesSql(tab.table, tab.pendingChanges, connection?.driver ?? "sqlite"),
    primaryKeyColumns,
    rowKey: (row) =>
      tab.queryResult ? databaseRowKey(tab.queryResult, row, primaryKeyColumns) : JSON.stringify(row),
    onApply: () => void applyPendingChanges(),
    onDeleteRow: (row, rowKey) => {
      if (!tab.queryResult || (!primaryKeyColumns.length && !rowKey?.startsWith("new:"))) return;
      updatePending((changes) =>
        stageRowDelete(changes, tab.queryResult!, row, primaryKeyColumns, rowKey),
      );
    },
    onInsertRow: (values) => {
      const id = globalThis.crypto?.randomUUID?.() ?? `row-${Date.now()}`;
      updatePending((changes) => stageRowInsert(changes, values, id));
    },
    onRevert: () => updateTableTab(tab.id, { error: null, pendingChanges: [] }),
    onUpdateCell: (row, columnName, value, rowKey) => {
      if (!tab.queryResult || (!primaryKeyColumns.length && !rowKey?.startsWith("new:"))) return;
      updatePending((changes) =>
        stageRowUpdate(
          changes,
          {
            columnName,
            nextValue: value,
            primaryKeyColumns,
            result: tab.queryResult!,
            row,
            rowKeyOverride: rowKey,
          },
        ),
      );
    },
  };
}

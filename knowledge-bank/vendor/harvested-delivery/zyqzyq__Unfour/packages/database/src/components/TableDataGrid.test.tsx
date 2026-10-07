// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { DatabaseQueryResult } from "@unfour/command-client";
import type { TableEditing } from "../model/types";
import { calculateAutoFitWidth } from "./table-data-grid-helpers";
import { TableDataGrid } from "./TableDataGrid";

vi.mock("./table-data-grid-helpers", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./table-data-grid-helpers")>();
  return {
    ...actual,
    calculateAutoFitWidth: vi.fn(actual.calculateAutoFitWidth),
  };
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const result: DatabaseQueryResult = {
  affectedRows: 0,
  columns: [
    { dataType: "INTEGER", name: "id" },
    { dataType: "TEXT", name: "name" },
  ],
  durationMs: 1,
  rows: [["1", "Ada"]],
  safety: { classification: "read", confirmed: true, message: null, requiresConfirmation: false },
};

const editing: TableEditing = {
  canInsert: true,
  canUpdateDelete: true,
  onApply: vi.fn(),
  onDeleteRow: vi.fn(),
  onInsertRow: vi.fn(),
  onRevert: vi.fn(),
  onUpdateCell: vi.fn(),
  pending: false,
  pendingChanges: [{
    id: "update:1",
    operation: "update",
    originalValues: [{ column: "name", mode: "value", value: "Ada" }],
    primaryKey: [{ column: "id", mode: "value", value: "1" }],
    rowKey: "1",
    values: [{ column: "name", mode: "value", value: "Ada Lovelace" }],
  }],
  previewSql: "UPDATE users SET name = ? WHERE id = ?",
  primaryKeyColumns: ["id"],
  rowKey: (row) => row[0] ?? "",
};

describe("TableDataGrid", () => {
  it("does not recalculate auto-fit widths for interaction-only rerenders", () => {
    render(<TableDataGrid editing={editing} result={result} />);

    expect(calculateAutoFitWidth).toHaveBeenCalledTimes(result.columns.length);

    fireEvent.click(screen.getByRole("button", { name: "Ada Lovelace" }));

    expect(calculateAutoFitWidth).toHaveBeenCalledTimes(result.columns.length);
  });

  it("keeps the grid body neutral during an initial load instead of flashing fake rows", () => {
    const { container } = render(<TableDataGrid loading result={result} />);

    expect(screen.queryByText("Ada")).toBeNull();
    expect(container.querySelector(".animate-pulse")).toBeNull();
  });

  it("reserves room for the delete action before editing becomes available", () => {
    const view = render(<TableDataGrid loading result={result} />);

    expect(view.container.querySelector("col")?.getAttribute("style")).toContain("72px");

    view.rerender(<TableDataGrid editing={editing} result={result} />);

    expect(screen.getByRole("button", { name: /delete row/i })).toBeTruthy();
    expect(view.container.querySelector("col")?.getAttribute("style")).toContain("72px");
  });
});

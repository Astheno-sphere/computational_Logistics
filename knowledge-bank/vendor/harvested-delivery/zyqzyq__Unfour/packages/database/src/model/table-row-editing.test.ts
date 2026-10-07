import { describe, expect, it } from "vitest";
import type { DatabaseQueryResult, DatabaseTable } from "@unfour/command-client";
import {
  buildPendingChangesSql,
  databaseRowKey,
  databaseValue,
  pendingValue,
  stageRowDelete,
  stageRowInsert,
  stageRowUpdate,
} from "./table-row-editing";

const result: DatabaseQueryResult = {
  columns: [
    { name: "id", dataType: "INTEGER" },
    { name: "name", dataType: "TEXT" },
    { name: "note", dataType: "TEXT" },
  ],
  rows: [["1", "Ada", null]],
  affectedRows: 0,
  durationMs: 1,
  safety: { classification: "select", requiresConfirmation: false, confirmed: false, message: null },
};

const table: DatabaseTable = {
  name: "users",
  kind: "table",
  columns: [],
  schema: "public",
};

describe("table row editing", () => {
  it("uses primary-key values for a stable row key", () => {
    expect(databaseRowKey(result, result.rows[0], ["id"])).toBe(
      JSON.stringify([["id", "value", "1"]]),
    );
  });

  it("merges staged cell edits while preserving empty string and NULL", () => {
    const row = ["1", "Ada", "memo"];
    const first = stageRowUpdate([], {
      columnName: "name",
      nextValue: databaseValue("name", ""),
      primaryKeyColumns: ["id"],
      result,
      row,
    });
    const second = stageRowUpdate(first, {
      columnName: "note",
      nextValue: databaseValue("note", null),
      primaryKeyColumns: ["id"],
      result,
      row,
    });

    expect(second).toHaveLength(1);
    expect(second[0].values).toEqual([
      { column: "name", mode: "value", value: "" },
      { column: "note", mode: "null", value: null },
    ]);
    expect(second[0].originalValues).toEqual([
      { column: "name", mode: "value", value: "Ada" },
      { column: "note", mode: "value", value: "memo" },
    ]);
    expect(pendingValue(second, second[0].rowKey, "name", "Ada")).toBe("");
    expect(pendingValue(second, second[0].rowKey, "note", "old")).toBeNull();
  });

  it("turns an updated row into one staged delete", () => {
    const update = stageRowUpdate([], {
      columnName: "name",
      nextValue: databaseValue("name", "Grace"),
      primaryKeyColumns: ["id"],
      result,
      row: result.rows[0],
    });
    const deletion = stageRowDelete(update, result, result.rows[0], ["id"]);
    expect(deletion).toHaveLength(1);
    expect(deletion[0].operation).toBe("delete");
  });

  it("removes a staged update when the cell returns to its original value", () => {
    const changed = stageRowUpdate([], {
      columnName: "name",
      nextValue: databaseValue("name", "Grace"),
      primaryKeyColumns: ["id"],
      result,
      row: result.rows[0],
    });
    expect(
      stageRowUpdate(changed, {
        columnName: "name",
        nextValue: databaseValue("name", "Ada"),
        primaryKeyColumns: ["id"],
        result,
        row: result.rows[0],
      }),
    ).toEqual([]);
  });

  it("edits and removes a staged insert without requiring a primary key", () => {
    const inserted = stageRowInsert([], [databaseValue("name", "Lin")], "draft-1");
    const edited = stageRowUpdate(inserted, {
      columnName: "name",
      nextValue: databaseValue("name", "Lin Chen"),
      primaryKeyColumns: [],
      result,
      row: [null, "Lin", null],
      rowKeyOverride: "new:draft-1",
    });
    expect(edited[0].values).toEqual([databaseValue("name", "Lin Chen")]);
    expect(stageRowDelete(edited, result, [null, "Lin Chen", null], [], "new:draft-1")).toEqual([]);
  });

  it("renders escaped SQL previews and driver-specific default inserts", () => {
    const insert = stageRowInsert(
      [],
      [
        { column: "id", mode: "default", value: null },
        databaseValue("name", "O'Brien"),
      ],
      "draft-1",
    );
    expect(buildPendingChangesSql(table, insert, "postgres")).toContain("'O''Brien'");

    const defaults = stageRowInsert([], [{ column: "id", mode: "default", value: null }], "draft-2");
    expect(buildPendingChangesSql({ ...table, schema: null }, defaults, "mysql")).toBe(
      "INSERT INTO `users` () VALUES ();",
    );
  });
});

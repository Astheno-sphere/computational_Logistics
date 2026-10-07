import type {
  DatabaseCellValue,
  DatabaseQueryResult,
  DatabaseTable,
} from "@unfour/command-client";
import type { PendingTableChange } from "./types";

type DataRow = Array<string | null>;

export function databaseValue(column: string, value: string | null): DatabaseCellValue {
  return value === null
    ? { column, mode: "null", value: null }
    : { column, mode: "value", value };
}

export function rowValues(result: DatabaseQueryResult, row: DataRow): DatabaseCellValue[] {
  return result.columns.map((column, index) => databaseValue(column.name, row[index] ?? null));
}

function comparableRowValues(result: DatabaseQueryResult, row: DataRow) {
  return rowValues(result, row).filter(
    (cell) =>
      cell.mode === "null" ||
      (cell.value !== "<unsupported>" && !cell.value?.startsWith("<binary ")),
  );
}

function originalCellValue(result: DatabaseQueryResult, row: DataRow, columnName: string) {
  const index = result.columns.findIndex((column) => column.name === columnName);
  if (index < 0) return null;
  const cell = databaseValue(columnName, row[index] ?? null);
  return cell.value === "<unsupported>" || cell.value?.startsWith("<binary ") ? null : cell;
}

export function primaryKeyValues(
  result: DatabaseQueryResult,
  row: DataRow,
  primaryKeyColumns: string[],
): DatabaseCellValue[] {
  return primaryKeyColumns.map((column) => {
    const index = result.columns.findIndex((candidate) => candidate.name === column);
    return databaseValue(column, index >= 0 ? row[index] ?? null : null);
  });
}

export function databaseRowKey(
  result: DatabaseQueryResult,
  row: DataRow,
  primaryKeyColumns: string[],
): string {
  const cells = primaryKeyColumns.length
    ? primaryKeyValues(result, row, primaryKeyColumns)
    : rowValues(result, row);
  return JSON.stringify(cells.map((cell) => [cell.column, cell.mode, cell.value ?? null]));
}

export function stageRowUpdate(
  changes: PendingTableChange[],
  input: {
    columnName: string;
    nextValue: DatabaseCellValue;
    primaryKeyColumns: string[];
    result: DatabaseQueryResult;
    row: DataRow;
    rowKeyOverride?: string;
  },
): PendingTableChange[] {
  const { columnName, nextValue, primaryKeyColumns, result, row, rowKeyOverride } = input;
  const rowKey = rowKeyOverride ?? databaseRowKey(result, row, primaryKeyColumns);
  const existing = changes.find((change) => change.rowKey === rowKey);
  if (existing?.operation === "delete") {
    return changes;
  }
  if (existing?.operation === "insert") {
    return changes.map((change) =>
      change.id === existing.id
        ? { ...change, values: replaceCell(change.values, columnName, nextValue) }
        : change,
    );
  }
  if (existing?.operation === "update") {
    const original = originalCellValue(result, row, columnName);
    const stagedOriginal =
      existing.originalValues.find((cell) => cell.column === columnName) ?? original;
    if (stagedOriginal && sameCellValue(stagedOriginal, nextValue)) {
      const remainingValues = existing.values.filter((cell) => cell.column !== columnName);
      if (!remainingValues.length) return changes.filter((change) => change.id !== existing.id);
      return changes.map((change) =>
        change.id === existing.id
          ? {
              ...change,
              originalValues: change.originalValues.filter((cell) => cell.column !== columnName),
              values: remainingValues,
            }
          : change,
      );
    }
    return changes.map((change) =>
      change.id === existing.id
        ? {
            ...change,
            originalValues:
              original && !change.originalValues.some((cell) => cell.column === columnName)
                ? [...change.originalValues, original]
                : change.originalValues,
            values: replaceCell(change.values, columnName, nextValue),
          }
        : change,
    );
  }
  const original = originalCellValue(result, row, columnName);
  return [
    ...changes,
    {
      id: `update:${rowKey}`,
      operation: "update",
      originalValues: original ? [original] : [],
      primaryKey: primaryKeyValues(result, row, primaryKeyColumns),
      rowKey,
      values: [nextValue],
    },
  ];
}

export function stageRowDelete(
  changes: PendingTableChange[],
  result: DatabaseQueryResult,
  row: DataRow,
  primaryKeyColumns: string[],
  rowKeyOverride?: string,
): PendingTableChange[] {
  const rowKey = rowKeyOverride ?? databaseRowKey(result, row, primaryKeyColumns);
  const existing = changes.find((change) => change.rowKey === rowKey);
  if (existing?.operation === "insert") {
    return changes.filter((change) => change.id !== existing.id);
  }
  const deletion: PendingTableChange = {
    id: `delete:${rowKey}`,
    operation: "delete",
    originalValues: comparableRowValues(result, row),
    primaryKey: existing?.primaryKey ?? primaryKeyValues(result, row, primaryKeyColumns),
    rowKey,
    values: [],
  };
  return [...changes.filter((change) => change.rowKey !== rowKey), deletion];
}

export function stageRowInsert(
  changes: PendingTableChange[],
  values: DatabaseCellValue[],
  id: string,
): PendingTableChange[] {
  return [
    ...changes,
    {
      id,
      operation: "insert",
      originalValues: [],
      primaryKey: [],
      rowKey: `new:${id}`,
      values,
    },
  ];
}

export function pendingValue(
  changes: PendingTableChange[],
  rowKey: string,
  columnName: string,
  fallback: string | null,
): string | null {
  const change = changes.find((candidate) => candidate.rowKey === rowKey);
  const cell = change?.values.find((candidate) => candidate.column === columnName);
  if (!cell) return fallback;
  if (cell.mode === "null") return null;
  if (cell.mode === "default") return "DEFAULT";
  return cell.value ?? "";
}

export function buildPendingChangesSql(
  table: DatabaseTable,
  changes: PendingTableChange[],
  driver: "sqlite" | "postgres" | "mysql",
): string {
  const quote = (identifier: string) =>
    driver === "mysql"
      ? `\`${identifier.split("`").join("``")}\``
      : `"${identifier.split('"').join('""')}"`;
  const qualifier = table.schema ?? table.catalog;
  const qualified = qualifier ? `${quote(qualifier)}.${quote(table.name)}` : quote(table.name);
  const literal = (cell: DatabaseCellValue) => {
    if (cell.mode === "null") return "NULL";
    if (cell.mode === "default") return "DEFAULT";
    return `'${(cell.value ?? "").split("'").join("''")}'`;
  };
  const predicate = (cell: DatabaseCellValue) =>
    cell.mode === "null"
      ? `${quote(cell.column)} IS NULL`
      : `${quote(cell.column)} = ${literal(cell)}`;

  return changes
    .map((change) => {
      if (change.operation === "insert") {
        const values = change.values.filter((cell) => cell.mode !== "default");
        if (!values.length) {
          return driver === "mysql"
            ? `INSERT INTO ${qualified} () VALUES ();`
            : `INSERT INTO ${qualified} DEFAULT VALUES;`;
        }
        return `INSERT INTO ${qualified} (${values.map((cell) => quote(cell.column)).join(", ")}) VALUES (${values.map(literal).join(", ")});`;
      }
      const where = [...change.primaryKey, ...change.originalValues].map(predicate).join(" AND ");
      if (change.operation === "delete") return `DELETE FROM ${qualified} WHERE ${where};`;
      const set = change.values.map((cell) => `${quote(cell.column)} = ${literal(cell)}`).join(", ");
      return `UPDATE ${qualified} SET ${set} WHERE ${where};`;
    })
    .join("\n\n");
}

function replaceCell(
  values: DatabaseCellValue[],
  columnName: string,
  nextValue: DatabaseCellValue,
) {
  return [...values.filter((cell) => cell.column !== columnName), nextValue];
}

function sameCellValue(left: DatabaseCellValue, right: DatabaseCellValue) {
  const leftNull = left.mode === "null" || left.value === null;
  const rightNull = right.mode === "null" || right.value === null;
  return leftNull && rightNull ? true : left.mode === right.mode && left.value === right.value;
}

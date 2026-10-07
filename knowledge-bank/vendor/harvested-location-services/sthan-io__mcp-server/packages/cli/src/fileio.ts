import { readFileSync, writeFileSync } from "node:fs";
import { extname } from "node:path";
import { parse } from "csv-parse/sync";
import { stringify } from "csv-stringify/sync";
import ExcelJS from "exceljs";

export interface InputRow {
  /** Original columns from the file (just `{ address }` for plain-text input). */
  original: Record<string, string>;
  /** The address string to process. */
  address: string;
}

export interface ParsedInput {
  rows: InputRow[];
  headers: string[];
}

const ADDRESS_HEADER_CANDIDATES = [
  "address",
  "fulladdress",
  "addr",
  "streetaddress",
  "mailingaddress",
];

const normalize = (s: string) => s.toLowerCase().replace(/[\s_-]/g, "");

/** Resolve the address column name, or exit(4) with a helpful message. */
function resolveColumn(headers: string[], column?: string): string {
  if (column) {
    const found = headers.find((h) => normalize(h) === normalize(column));
    if (found) return found;
    console.error(
      `Column "${column}" not found. Available columns: ${headers.join(", ")}`
    );
    process.exit(4);
  }
  for (const candidate of ADDRESS_HEADER_CANDIDATES) {
    const found = headers.find((h) => normalize(h) === candidate);
    if (found) return found;
  }
  if (headers.length === 1) return headers[0];
  console.error(
    `Could not auto-detect an address column. Use --column. Available: ${headers.join(", ")}`
  );
  process.exit(4);
}

/** Read an input file into rows, dispatching on file extension. */
export async function readInput(
  path: string,
  column?: string
): Promise<ParsedInput> {
  const ext = extname(path).toLowerCase();
  if (ext === ".xlsx") return readXlsx(path, column);
  if (ext === ".csv" || ext === ".tsv") {
    return readDelimited(path, ext === ".tsv" ? "\t" : ",", column);
  }
  return readText(path);
}

function readDelimited(
  path: string,
  delimiter: string,
  column?: string
): ParsedInput {
  const content = readFileSync(path, "utf8");
  const records = parse(content, {
    columns: true,
    skip_empty_lines: true,
    trim: true,
    bom: true,
    delimiter,
  }) as Record<string, string>[];
  const headers = records.length ? Object.keys(records[0]) : [];
  if (!headers.length) return { rows: [], headers };
  const addrCol = resolveColumn(headers, column);
  const rows = records.map((rec) => ({
    original: rec,
    address: (rec[addrCol] ?? "").trim(),
  }));
  return { rows, headers };
}

async function readXlsx(path: string, column?: string): Promise<ParsedInput> {
  const wb = new ExcelJS.Workbook();
  await wb.xlsx.readFile(path);
  const ws = wb.worksheets[0];
  if (!ws || ws.rowCount < 1) return { rows: [], headers: [] };

  const headers: string[] = [];
  ws.getRow(1).eachCell((cell, col) => {
    headers[col - 1] = String(cell.text ?? "").trim();
  });
  const named = headers.filter(Boolean);
  if (!named.length) return { rows: [], headers: [] };
  const addrCol = resolveColumn(named, column);
  const addrIdx = headers.findIndex((h) => h === addrCol);

  const rows: InputRow[] = [];
  for (let i = 2; i <= ws.rowCount; i++) {
    const row = ws.getRow(i);
    const original: Record<string, string> = {};
    let hasValue = false;
    headers.forEach((h, idx) => {
      if (!h) return;
      const v = String(row.getCell(idx + 1).text ?? "").trim();
      original[h] = v;
      if (v) hasValue = true;
    });
    if (!hasValue) continue;
    rows.push({ original, address: (original[headers[addrIdx]] ?? "").trim() });
  }
  return { rows, headers: named };
}

function readText(path: string): ParsedInput {
  const lines = readFileSync(path, "utf8")
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);
  return {
    rows: lines.map((address) => ({ original: { address }, address })),
    headers: ["address"],
  };
}

/** Write result rows to .csv (default) or .xlsx, by output extension. */
export async function writeOutput(
  path: string,
  rows: Array<Record<string, string>>,
  headers: string[]
): Promise<void> {
  if (extname(path).toLowerCase() === ".xlsx") {
    const wb = new ExcelJS.Workbook();
    const ws = wb.addWorksheet("Results");
    ws.addRow(headers);
    ws.getRow(1).font = { bold: true };
    for (const r of rows) ws.addRow(headers.map((h) => r[h] ?? ""));
    await wb.xlsx.writeFile(path);
    return;
  }
  const csv = stringify(rows, { header: true, columns: headers });
  writeFileSync(path, csv);
}

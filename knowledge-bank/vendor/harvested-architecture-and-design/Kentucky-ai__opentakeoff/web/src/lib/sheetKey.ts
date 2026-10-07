// Sheet-key convention: page 1 = bare file name; pages 2+ = "name#page".
// Lives in its own module so pure-math consumers (totals.js) don't drag in
// pdfjs-dist via sheets.ts for a two-line parser.
export interface ParsedSheetKey { file: string; page: number }

// Inverse of sheetKey: split on the LAST '#' and only when the tail is
// numeric — file names may contain '#'.
export function parseSheetKey(key: string): ParsedSheetKey {
  const i = key.lastIndexOf("#");
  if (i > 0 && /^\d+$/.test(key.slice(i + 1))) return { file: key.slice(0, i), page: parseInt(key.slice(i + 1), 10) };
  return { file: key, page: 1 };
}

// THE canonical sheet order — file name, then numeric page. Every sheet-ordered
// output (by-sheet totals, the report's grouped-by-sheet view, the Marked Set
// PDF) sorts with this one comparator so they can never drift apart.
export function compareSheetKeys(ka: string, kb: string): number {
  const a = parseSheetKey(ka), b = parseSheetKey(kb);
  return a.file === b.file ? a.page - b.page : a.file.localeCompare(b.file);
}

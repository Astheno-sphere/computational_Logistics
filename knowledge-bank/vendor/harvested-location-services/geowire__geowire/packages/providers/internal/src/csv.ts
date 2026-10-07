/**
 * RFC 4180 준수 CSV 파서 (경량, 의존성 없음).
 * 따옴표로 감싼 필드 안의 쉼표·개행·이스케이프(`""`)를 처리한다.
 */
export function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let field = "";
  let row: string[] = [];
  let inQuotes = false;
  let i = 0;
  const n = text.length;

  const endField = (): void => {
    row.push(field);
    field = "";
  };
  const endRow = (): void => {
    endField();
    rows.push(row);
    row = [];
  };

  while (i < n) {
    const ch = text[i]!;
    if (inQuotes) {
      if (ch === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i += 2;
          continue;
        }
        inQuotes = false;
        i++;
        continue;
      }
      field += ch;
      i++;
      continue;
    }
    if (ch === '"') {
      inQuotes = true;
      i++;
    } else if (ch === ",") {
      endField();
      i++;
    } else if (ch === "\r") {
      // \r\n 또는 단독 \r 모두 줄바꿈으로 처리
      if (text[i + 1] === "\n") i++;
      endRow();
      i++;
    } else if (ch === "\n") {
      endRow();
      i++;
    } else {
      field += ch;
      i++;
    }
  }
  // 마지막 필드/행 마무리 (완전 빈 입력이 아니거나 진행 중인 내용이 있으면)
  if (field.length > 0 || row.length > 0) endRow();

  return rows;
}

/**
 * CSV 텍스트를 헤더 기반 레코드 배열로 변환한다.
 * 첫 행은 헤더(공백 제거·소문자화). 완전히 빈 행은 건너뛴다.
 */
export function parseCsvRecords(text: string): Record<string, string>[] {
  const rows = parseCsv(text).filter((r) => !(r.length === 1 && r[0]!.trim() === ""));
  if (rows.length === 0) return [];
  const header = rows[0]!.map((h) => h.trim().toLowerCase());
  return rows.slice(1).map((row) => {
    const record: Record<string, string> = {};
    header.forEach((key, idx) => {
      record[key] = (row[idx] ?? "").trim();
    });
    return record;
  });
}

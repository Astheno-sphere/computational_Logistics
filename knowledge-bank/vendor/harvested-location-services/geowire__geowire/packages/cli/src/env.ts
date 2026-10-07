import { readFileSync, writeFileSync, existsSync, appendFileSync } from "node:fs";

/** `.env` 텍스트를 KEY=value 맵으로 파싱 (주석·빈 줄·따옴표 처리) */
export function parseDotEnv(text: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq <= 0) continue;
    const key = line.slice(0, eq).trim();
    let value = line.slice(eq + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    out[key] = value;
  }
  return out;
}

/** `.env` 파일이 있으면 읽어 process.env에 주입한다(기존 값은 덮지 않음). 없으면 no-op */
export function loadDotEnv(path: string, env: NodeJS.ProcessEnv = process.env): void {
  if (!existsSync(path)) return;
  const parsed = parseDotEnv(readFileSync(path, "utf8"));
  for (const [key, value] of Object.entries(parsed)) {
    if (env[key] === undefined) env[key] = value;
  }
}

/** KEY=value 맵을 `.env` 텍스트로 (주석 헤더 포함) */
export function buildEnvContent(vars: Record<string, string>): string {
  const lines = ["# GeoWire environment — keep secret, do not commit"];
  for (const [key, value] of Object.entries(vars)) lines.push(`${key}=${value}`);
  return `${lines.join("\n")}\n`;
}

/** `.gitignore`에 항목이 없으면 추가한다(파일 없으면 생성). 이미 있으면 no-op → true=변경함 */
export function ensureGitignore(path: string, entry: string): boolean {
  if (!existsSync(path)) {
    writeFileSync(path, `${entry}\n`, "utf8");
    return true;
  }
  const content = readFileSync(path, "utf8");
  const entries = content.split(/\r?\n/).map((l) => l.trim());
  if (entries.includes(entry)) return false;
  const prefix = content.endsWith("\n") || content.length === 0 ? "" : "\n";
  appendFileSync(path, `${prefix}${entry}\n`, "utf8");
  return true;
}

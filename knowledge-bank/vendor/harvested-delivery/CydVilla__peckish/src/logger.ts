/**
 * Session audit log — one JSONL file per process under ~/.peckish/logs/.
 *
 * Records what the agent actually did: user turns, every tool call (args,
 * outcome, duration), confirmation prompts and their answers, order submits,
 * and errors. No Anthropic message content is logged beyond what's needed for
 * the audit trail. Logging is best-effort and must never break a turn.
 */
import { homedir } from "node:os";
import { join } from "node:path";
import { mkdirSync, appendFileSync } from "node:fs";

const LOG_DIR = join(homedir(), ".peckish", "logs");
let logFile: string | null = null;
let disabled = false;

function ensureFile(): string | null {
  if (disabled) return null;
  if (!logFile) {
    try {
      mkdirSync(LOG_DIR, { recursive: true });
      const stamp = new Date().toISOString().replace(/[:.]/g, "-");
      logFile = join(LOG_DIR, `session-${stamp}.jsonl`);
    } catch {
      disabled = true;
      return null;
    }
  }
  return logFile;
}

const clip = (s: string, n: number) => (s.length > n ? s.slice(0, n) + "…" : s);

export function logEvent(type: string, data: Record<string, unknown> = {}): void {
  const file = ensureFile();
  if (!file) return;
  try {
    appendFileSync(file, JSON.stringify({ ts: new Date().toISOString(), type, ...data }) + "\n");
  } catch {
    disabled = true;
  }
}

export function logToolCall(
  name: string,
  input: unknown,
  ok: boolean,
  ms: number,
  result?: string,
): void {
  logEvent("tool_call", {
    name,
    input: clip(JSON.stringify(input ?? {}), 800),
    ok,
    ms,
    result_bytes: result?.length ?? 0,
    // Full outcomes for order placement; a short preview otherwise.
    result_preview: result ? clip(result, name === "submit_order" ? 4000 : 200) : undefined,
  });
}

export function currentLogFile(): string | null {
  return logFile;
}

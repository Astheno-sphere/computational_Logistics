/**
 * Persistent user preferences (dietary rules, budget habits, tip defaults).
 * Stored as plain JSON at ~/.peckish/preferences.json so the agent can
 * remember "avoid mushrooms" across sessions.
 */
import { homedir } from "node:os";
import { join } from "node:path";
import { mkdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";

const LEGACY_DIR = join(homedir(), ".dd-agent");
const DIR = join(homedir(), ".peckish");
const FILE = join(DIR, "preferences.json");

// One-time migration from the pre-rename location.
try {
  const legacy = join(LEGACY_DIR, "preferences.json");
  if (!existsSync(FILE) && existsSync(legacy)) {
    mkdirSync(DIR, { recursive: true });
    writeFileSync(FILE, readFileSync(legacy));
  }
} catch {
  // best-effort
}

interface PrefsFile {
  notes: string[];
}

function load(): PrefsFile {
  try {
    if (existsSync(FILE)) {
      const parsed = JSON.parse(readFileSync(FILE, "utf8")) as PrefsFile;
      if (Array.isArray(parsed.notes)) return { notes: parsed.notes.map(String) };
    }
  } catch {
    // Corrupt prefs file — start fresh rather than crash.
  }
  return { notes: [] };
}

function save(prefs: PrefsFile): void {
  mkdirSync(DIR, { recursive: true });
  writeFileSync(FILE, JSON.stringify(prefs, null, 2) + "\n", "utf8");
}

export function listPreferences(): string[] {
  return load().notes;
}

export function addPreference(note: string): string[] {
  const prefs = load();
  const trimmed = note.trim();
  if (trimmed && !prefs.notes.some((n) => n.toLowerCase() === trimmed.toLowerCase())) {
    prefs.notes.push(trimmed);
    save(prefs);
  }
  return prefs.notes;
}

export function removePreference(note: string): string[] {
  const prefs = load();
  const target = note.trim().toLowerCase();
  prefs.notes = prefs.notes.filter((n) => n.toLowerCase() !== target);
  save(prefs);
  return prefs.notes;
}

export function preferencesFilePath(): string {
  return FILE;
}

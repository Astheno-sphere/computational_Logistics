// Child-process helpers for the release script: run with a hard timeout, and
// kill the whole process tree when it expires.
import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";

/**
 * Where tools install when a terminal's PATH does not know about them yet.
 * Windows hands PATH changes only to windows opened AFTER an install: the first
 * real release run died with `spawn gh ENOENT` in a PowerShell window older than
 * the GitHub CLI install, although gh.exe was on the machine PATH.
 */
const WINDOWS_FALLBACKS = {
  gh: [join(process.env.ProgramFiles ?? "C:\\Program Files", "GitHub CLI", "gh.exe")],
};

/** Use the command as-is if PATH can find it; otherwise a known install location. */
function resolveExecutable(command) {
  if (process.platform !== "win32" || !WINDOWS_FALLBACKS[command]) return command;
  const onPath = (process.env.Path ?? process.env.PATH ?? "")
    .split(";")
    .some(dir => dir && existsSync(join(dir, `${command}.exe`)));
  if (onPath) return command;
  return WINDOWS_FALLBACKS[command].find(existsSync) ?? command;
}

/** Turn "could not start" into a sentence that says what to do. */
function launchError(command, error) {
  if (error?.code === "ENOENT") {
    return new Error(
      `${command} could not be started: it is not on this terminal's PATH. If you installed it ` +
        "after opening this window, open a new terminal and run again.",
    );
  }
  return error;
}

/**
 * npm and npx are .cmd shims on Windows and can only be launched through a
 * shell. Everything else (git, gh, node, mcp-publisher) is a real executable and
 * gets its arguments directly — no shell, so no quoting, and a `|` or `"` in an
 * argument stays an argument instead of becoming a pipe.
 */
function needsShell(command) {
  return process.platform === "win32" && /^(npm|npx)$/.test(command);
}

const quote = a => (/[\s<>|&^]/.test(a) ? `"${a}"` : a);

function launch(command, args) {
  if (!needsShell(command)) return { file: resolveExecutable(command), args, shell: false };
  // cmd.exe toggles its quote state on EVERY double quote, backslash or not, so
  // an argument containing one can leave the rest of the line unquoted — and a
  // `>` there becomes a redirect. (An early test created an empty file named
  // "{}" in the repo exactly that way, from `()=>{}`.) % and ! expand variables
  // even inside quotes. Refuse all three rather than pass them on wrongly.
  const unsafe = args.find(a => /["%!]/.test(a));
  if (unsafe !== undefined) {
    throw new Error(`Refusing to pass ${JSON.stringify(unsafe)} to ${command} through cmd: it contains " % or !`);
  }
  return { file: [command, ...args.map(quote)].join(" "), args: [], shell: true };
}

/** Kill a process AND its children — killing only a shell leaves npm running. */
export function killTree(child) {
  if (process.platform === "win32") {
    spawnSync("taskkill", ["/pid", String(child.pid), "/T", "/F"], { stdio: "ignore" });
  } else {
    try {
      process.kill(-child.pid, "SIGKILL");
    } catch {
      child.kill("SIGKILL");
    }
  }
}

/**
 * Run with the terminal attached (npm can ask for a 2FA code, Smithery can open
 * a browser), rejecting and killing the tree if it outlives `timeoutMs`.
 * `display` overrides what is printed, so secrets never reach the log.
 */
export function run(command, args, { timeoutMs, label, display, stdio = "inherit" }) {
  console.log(`  $ ${display ?? [command, ...args.map(quote)].join(" ")}`);
  const { file, args: spawnArgs, shell } = launch(command, args);
  return new Promise((resolve, reject) => {
    const child = spawn(file, spawnArgs, { stdio, shell, detached: process.platform !== "win32" });
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      killTree(child);
      reject(new Error(`${label} timed out after ${Math.round(timeoutMs / 1000)}s and was stopped`));
    }, timeoutMs);
    child.on("exit", code => {
      clearTimeout(timer);
      if (timedOut) return;
      if (code === 0) resolve(code);
      else reject(new Error(`${label} exited with code ${code}`));
    });
    child.on("error", error => {
      clearTimeout(timer);
      if (!timedOut) reject(launchError(command, error));
    });
  });
}

/**
 * Run quietly and return the output, for checks. Two-minute ceiling.
 *
 * Throws if the command cannot be STARTED. Returning ok:false instead is what
 * let the release script read "gh is missing" as "the GitHub release does not
 * exist yet" and go on to try creating it.
 */
export function capture(command, args) {
  const { file, args: spawnArgs, shell } = launch(command, args);
  const result = spawnSync(file, spawnArgs, { shell, encoding: "utf8", timeout: 120_000 });
  if (result.error) throw launchError(command, result.error);
  // trimEnd, not trim: leading spaces are meaningful (git status --porcelain).
  return { ok: result.status === 0, out: (result.stdout ?? "").trimEnd(), err: (result.stderr ?? "").trimEnd() };
}

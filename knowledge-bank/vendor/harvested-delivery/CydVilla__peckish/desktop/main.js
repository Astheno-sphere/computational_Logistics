/**
 * Peckish for Mac — Electron shell.
 *
 * Thin by design: no agent logic lives here. The shell
 *   1. walks the user through first-run setup (dd-cli install, DoorDash
 *      sign-in, Anthropic API key) in a native window — no terminal;
 *   2. forks the published Peckish web server (peckish/dist/web.js) on a
 *      random free localhost port with the API key injected into its env;
 *   3. points a BrowserWindow at it. The web app's confirm modal remains the
 *      one and only order gate.
 *
 * The API key is stored with Electron safeStorage (macOS keychain-backed
 * encryption) — never plaintext on disk.
 */
const {
  app,
  BrowserWindow,
  ipcMain,
  utilityProcess,
  safeStorage,
  shell,
  dialog,
} = require("electron");
const { execFile, spawn } = require("node:child_process");
const { createHash } = require("node:crypto");
const { existsSync, readFileSync, writeFileSync, mkdirSync, rmSync } = require("node:fs");
const net = require("node:net");
const { homedir, tmpdir } = require("node:os");
const path = require("node:path");

// ---------------------------------------------------------------------------
// dd-cli release pin — update BOTH lines together when bumping the version.
// The hash is the SHA256 of the official release tarball; the installer
// refuses to run anything whose digest doesn't match.
// ---------------------------------------------------------------------------
const DD_CLI_VERSION = "0.2.0";
const DD_CLI_SHA256 = "cd6502c1704d12b7d7e9b64dc58fda7efac1a7765a7e0eb887260f7a7dcc6442";
const DD_CLI_ASSET = `dd-cli-v${DD_CLI_VERSION}-darwin-arm64.tar.gz`;
const DD_CLI_URL = `https://github.com/doordash-oss/doordash-cli/releases/download/v${DD_CLI_VERSION}/${DD_CLI_ASSET}`;

const DD_CLI_HOME = path.join(homedir(), ".local", "bin", "dd-cli");

let onboardingWin = null;
let mainWin = null;
let serverProc = null;
let serverPort = null;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function ddCliPath() {
  if (process.env.DD_CLI_PATH && existsSync(process.env.DD_CLI_PATH)) {
    return process.env.DD_CLI_PATH;
  }
  if (existsSync(DD_CLI_HOME)) return DD_CLI_HOME;
  return null; // GUI apps don't inherit shell PATH; only explicit paths count
}

/** Resolve {installed, signedIn} by running a read-only dd-cli command. */
function checkDdCli() {
  return new Promise((resolve) => {
    const bin = ddCliPath();
    if (!bin) return resolve({ installed: false, signedIn: false });
    execFile(bin, ["--json-output", "address", "list"], { timeout: 30_000 }, (err, stdout, stderr) => {
      if (!err) return resolve({ installed: true, signedIn: true });
      const detail = `${stdout}\n${stderr}\n${err.message}`;
      if (/missing credentials|sign in with dd-cli login|token has expired/i.test(detail)) {
        return resolve({ installed: true, signedIn: false });
      }
      // Binary exists but errored some other way — treat as signed-in-unknown,
      // surface the detail so the user isn't stuck on a blank ✗.
      resolve({ installed: true, signedIn: false, error: detail.trim().slice(0, 400) });
    });
  });
}

const keyFile = () => path.join(app.getPath("userData"), "anthropic-key.enc");

function hasApiKey() {
  return existsSync(keyFile()) && safeStorage.isEncryptionAvailable();
}

function loadApiKey() {
  if (!hasApiKey()) return null;
  try {
    return safeStorage.decryptString(readFileSync(keyFile()));
  } catch {
    return null;
  }
}

function getFreePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.listen(0, "127.0.0.1", () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
    srv.on("error", reject);
  });
}

function sendProgress(step, state, detail) {
  if (onboardingWin && !onboardingWin.isDestroyed()) {
    onboardingWin.webContents.send("progress", { step, state, detail: detail ?? null });
  }
}

// ---------------------------------------------------------------------------
// dd-cli guided install (download → verify SHA256 → install.sh)
// ---------------------------------------------------------------------------

async function installDdCli() {
  sendProgress("ddcli", "working", `Downloading dd-cli v${DD_CLI_VERSION}…`);
  const res = await fetch(DD_CLI_URL, { redirect: "follow" });
  if (!res.ok) {
    throw new Error(
      `Download failed (HTTP ${res.status}). If you don't have DoorDash CLI access yet, join the waitlist first.`,
    );
  }
  const buf = Buffer.from(await res.arrayBuffer());

  sendProgress("ddcli", "working", "Verifying SHA256 checksum…");
  const digest = createHash("sha256").update(buf).digest("hex");
  if (digest !== DD_CLI_SHA256) {
    throw new Error(
      `Checksum mismatch — refusing to install. Expected ${DD_CLI_SHA256}, got ${digest}. ` +
        "The release may have changed; update the app or install dd-cli manually.",
    );
  }

  const workDir = path.join(tmpdir(), `peckish-ddcli-${Date.now()}`);
  mkdirSync(workDir, { recursive: true });
  const tarPath = path.join(workDir, DD_CLI_ASSET);
  writeFileSync(tarPath, buf);

  sendProgress("ddcli", "working", "Extracting…");
  await run("/usr/bin/tar", ["-xzf", tarPath, "-C", workDir]);
  const extracted = path.join(workDir, `dd-cli-v${DD_CLI_VERSION}-darwin-arm64`);
  const installScript = path.join(extracted, "install.sh");
  if (!existsSync(installScript)) throw new Error("install.sh missing from verified tarball");

  sendProgress("ddcli", "working", "Running installer…");
  await run("/bin/bash", [installScript], { cwd: extracted });
  rmSync(workDir, { recursive: true, force: true });

  if (!ddCliPath()) throw new Error("Installer finished but dd-cli was not found at ~/.local/bin/dd-cli");
}

function run(cmd, args, opts = {}) {
  return new Promise((resolve, reject) => {
    execFile(cmd, args, { timeout: 120_000, ...opts }, (err, stdout, stderr) => {
      if (err) reject(new Error(`${cmd} failed: ${(stderr || stdout || err.message).slice(0, 400)}`));
      else resolve(stdout);
    });
  });
}

// ---------------------------------------------------------------------------
// DoorDash sign-in (dd-cli login opens the browser; we poll until it works)
// ---------------------------------------------------------------------------

let loginChild = null;

function startLogin() {
  const bin = ddCliPath();
  if (!bin) throw new Error("dd-cli is not installed yet");
  if (loginChild) return; // already in progress
  loginChild = spawn(bin, ["login"], { stdio: "ignore", detached: false });
  loginChild.on("exit", () => {
    loginChild = null;
  });
}

// ---------------------------------------------------------------------------
// Server lifecycle
// ---------------------------------------------------------------------------

async function startServer() {
  const apiKey = loadApiKey();
  if (!apiKey) throw new Error("No API key saved");
  serverPort = await getFreePort();
  const entry = require.resolve("peckish/dist/web.js");
  serverProc = utilityProcess.fork(entry, [], {
    env: {
      ...process.env,
      PECKISH_PORT: String(serverPort),
      ANTHROPIC_API_KEY: apiKey,
    },
    stdio: "pipe",
  });
  let bootLog = "";
  serverProc.stdout?.on("data", (d) => (bootLog += d));
  serverProc.stderr?.on("data", (d) => (bootLog += d));
  const exited = new Promise((_, reject) => {
    serverProc.once("exit", (code) => {
      if (code !== 0) reject(new Error(`Peckish server exited (${code}): ${bootLog.trim().slice(0, 500)}`));
    });
  });

  // Wait until /api/state answers (server does its own dd-cli preflight first)
  const ready = (async () => {
    const deadline = Date.now() + 30_000;
    while (Date.now() < deadline) {
      try {
        const r = await fetch(`http://127.0.0.1:${serverPort}/api/state`);
        if (r.ok) return;
      } catch {
        /* not up yet */
      }
      await new Promise((r) => setTimeout(r, 300));
    }
    throw new Error(`Peckish server did not come up: ${bootLog.trim().slice(0, 500)}`);
  })();
  await Promise.race([ready, exited]);
}

function stopServer() {
  if (serverProc) {
    try {
      serverProc.kill();
    } catch {
      /* already gone */
    }
    serverProc = null;
  }
}

// ---------------------------------------------------------------------------
// Windows
// ---------------------------------------------------------------------------

const ALLOWED_EXTERNAL = [
  "https://github.com/doordash-oss/doordash-cli",
  "https://console.anthropic.com",
  "https://github.com/CydVilla/peckish",
  "https://www.doordash.com", // "edit address" link in the web UI
];

function wireExternalLinks(win) {
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (ALLOWED_EXTERNAL.some((p) => url.startsWith(p))) shell.openExternal(url);
    return { action: "deny" };
  });
}

function openOnboarding() {
  onboardingWin = new BrowserWindow({
    width: 640,
    height: 640,
    resizable: false,
    title: "Set up Peckish",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  wireExternalLinks(onboardingWin);
  onboardingWin.loadFile(path.join(__dirname, "onboarding.html"));
  onboardingWin.on("closed", () => (onboardingWin = null));
}

async function openApp() {
  await startServer();
  mainWin = new BrowserWindow({
    width: 1100,
    height: 800,
    title: "Peckish",
    webPreferences: { contextIsolation: true, nodeIntegration: false },
  });
  wireExternalLinks(mainWin);
  await mainWin.loadURL(`http://127.0.0.1:${serverPort}/`);
  mainWin.on("closed", () => (mainWin = null));
  if (onboardingWin && !onboardingWin.isDestroyed()) onboardingWin.close();
}

// ---------------------------------------------------------------------------
// IPC
// ---------------------------------------------------------------------------

ipcMain.handle("get-status", async () => {
  const dd = await checkDdCli();
  return {
    ddInstalled: dd.installed,
    ddSignedIn: dd.signedIn,
    ddError: dd.error ?? null,
    hasApiKey: hasApiKey(),
    encryptionAvailable: safeStorage.isEncryptionAvailable(),
    ddCliVersion: DD_CLI_VERSION,
  };
});

ipcMain.handle("install-ddcli", async () => {
  try {
    await installDdCli();
    sendProgress("ddcli", "done");
    return { ok: true };
  } catch (err) {
    sendProgress("ddcli", "error", err.message);
    return { ok: false, error: err.message };
  }
});

ipcMain.handle("start-login", async () => {
  try {
    startLogin();
    return { ok: true };
  } catch (err) {
    return { ok: false, error: err.message };
  }
});

ipcMain.handle("check-signin", async () => {
  const dd = await checkDdCli();
  return { signedIn: dd.signedIn };
});

ipcMain.handle("save-api-key", async (_e, key) => {
  const trimmed = String(key ?? "").trim();
  if (!trimmed.startsWith("sk-ant-")) {
    return { ok: false, error: "That doesn't look like an Anthropic API key (should start with sk-ant-)." };
  }
  if (!safeStorage.isEncryptionAvailable()) {
    return { ok: false, error: "macOS keychain encryption unavailable — cannot store the key safely." };
  }
  writeFileSync(keyFile(), safeStorage.encryptString(trimmed), { mode: 0o600 });
  return { ok: true };
});

ipcMain.handle("launch", async () => {
  try {
    await openApp();
    return { ok: true };
  } catch (err) {
    return { ok: false, error: err.message };
  }
});

ipcMain.handle("open-external", (_e, url) => {
  if (ALLOWED_EXTERNAL.some((p) => String(url).startsWith(p))) shell.openExternal(url);
});

// ---------------------------------------------------------------------------
// App lifecycle
// ---------------------------------------------------------------------------

app.whenReady().then(async () => {
  const dd = await checkDdCli();
  if (dd.installed && dd.signedIn && hasApiKey()) {
    try {
      await openApp();
    } catch (err) {
      dialog.showErrorBox("Peckish failed to start", String(err.message ?? err));
      openOnboarding();
    }
  } else {
    openOnboarding();
  }

  // Dev hook: PECKISH_SHELL_SHOT=/path.png captures the front window and quits.
  if (process.env.PECKISH_SHELL_SHOT) {
    const deadline = Date.now() + 25_000;
    const tryShot = async () => {
      const win = mainWin ?? onboardingWin;
      if (win && !win.webContents.isLoading()) {
        await new Promise((r) => setTimeout(r, 1500)); // let SSE/state render
        const img = await win.webContents.capturePage();
        writeFileSync(process.env.PECKISH_SHELL_SHOT, img.toPNG());
        app.quit();
      } else if (Date.now() > deadline) {
        app.quit();
      } else {
        setTimeout(tryShot, 1000);
      }
    };
    setTimeout(tryShot, 3000);
  }
});

app.on("window-all-closed", () => app.quit());
app.on("before-quit", stopServer);

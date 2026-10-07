// Release atlasfetch-mcp everywhere it is distributed, in order, with a
// timeout on every step.
//
//   node scripts/release.mjs --dry-run      check everything, publish nothing
//   node scripts/release.mjs                release the version in package.json
//   node scripts/release.mjs --from smithery   resume from a step
//   node scripts/release.mjs --skip smithery   leave a step out
//
// Steps: preflight, build, npm-publish, npm-wait, npm-deprecate, registry,
// smithery, github-release, verify.
//
// Safe to re-run: npm-publish, registry and github-release each check whether
// their part is already done and skip it. Smithery cannot be checked, so it
// always publishes unless skipped.
//
// Before running: bump the version in package.json, server.json (twice),
// manifest.json and src/server.ts, commit and push. Preflight refuses to go
// further if any of that is not true.
//
// Needs: npm login (atlasiq), gh auth, key.pem in this folder, mcp-publisher
// (MCP_PUBLISHER, default E:/Claude/mcp-publisher.exe), and a Smithery login.
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { capture, run } from "./lib/proc.mjs";

const PACKAGE = "atlasfetch-mcp";
const REGISTRY_NAME = "xyz.atlasfetch/atlasfetch";
const SMITHERY_NAME = "atlasfetch/atlasfetch";
const GITHUB_REPO = "atlasfetch-dev/atlasfetch-mcp";
const BRANCH = "master";
const PUBLISHER = process.env.MCP_PUBLISHER ?? "E:/Claude/mcp-publisher.exe";

const MIN = 60_000;
const STEPS = ["preflight", "build", "npm-publish", "npm-wait", "npm-deprecate", "registry", "smithery", "github-release", "verify"];

// ── Arguments ────────────────────────────────────────────────────────────────
const argv = process.argv.slice(2);
const dryRun = argv.includes("--dry-run");
const argValue = flag => { const i = argv.indexOf(flag); return i >= 0 ? argv[i + 1] : undefined; };
const from = argValue("--from");
const skip = new Set((argValue("--skip") ?? "").split(",").filter(Boolean));
for (const name of [from, ...skip].filter(Boolean)) {
  if (!STEPS.includes(name)) fail(`Unknown step "${name}". Steps: ${STEPS.join(", ")}`);
}

const startAt = from ? STEPS.indexOf(from) : 0;
const version = JSON.parse(readFileSync("package.json", "utf8")).version;
const tag = `v${version}`;

// ── Helpers ──────────────────────────────────────────────────────────────────
function fail(message) {
  console.error(`\n✗ ${message}`);
  process.exit(1);
}

function log(message) {
  console.log(`  ${message}`);
}

// Every HTTP check goes through here. The MCP Registry's search endpoint is
// genuinely slow — 40s measured while releasing 0.1.5, which a flat 30s timeout
// turned into a failed release step after npm had already published. So: a
// timeout the caller chooses, and retries, because "slow" is not "broken".
async function fetchJson(url, { timeoutMs = 30_000, attempts = 3 } = {}) {
  let lastError;
  for (let attempt = 1; attempt <= attempts; attempt++) {
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(timeoutMs) });
      return { status: response.status, body: response.ok ? await response.json() : null };
    } catch (error) {
      lastError = error;
      if (attempt < attempts) {
        log(`${new URL(url).host} did not answer in ${Math.round(timeoutMs / 1000)}s (${error.message}); retrying`);
        await sleep(5_000);
      }
    }
  }
  throw new Error(`${new URL(url).host} did not answer after ${attempts} tries: ${lastError.message}`);
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function npmHasVersion() {
  // Straight to the registry, not `npm view`, which can answer from its cache.
  const { status } = await fetchJson(`https://registry.npmjs.org/${PACKAGE}/${version}?t=${Date.now()}`);
  return status === 200;
}

async function registryLatest() {
  // The listing is cached upstream: without the throwaway parameter, verify
  // read 0.1.3 as latest for 0.1.4, which had been live for minutes.
  const { body } = await fetchJson(
    `https://registry.modelcontextprotocol.io/v0.1/servers?search=${encodeURIComponent(REGISTRY_NAME)}&t=${Date.now()}`,
    { timeoutMs: 2 * MIN },
  );
  const entries = (body?.servers ?? []).map(e => ({
    version: (e.server ?? e).version,
    name: (e.server ?? e).name,
    latest: (e._meta ?? {})["io.modelcontextprotocol.registry/official"]?.isLatest,
  }));
  return entries.filter(e => e.name === REGISTRY_NAME);
}

/**
 * The commit to tag: the one npm actually published, which npm records as
 * gitHead — not whatever HEAD is now. A release that stops halfway and resumes
 * after a fix would otherwise tag a commit whose code is not in the published
 * tarball. Falls back to HEAD when npm has no gitHead, or when it names a commit
 * GitHub has never seen (gh needs a --target it can resolve).
 */
async function releaseTarget() {
  const head = capture("git", ["rev-parse", "HEAD"]).out;
  const { body } = await fetchJson(`https://registry.npmjs.org/${PACKAGE}/${version}?t=${Date.now()}`);
  const gitHead = body?.gitHead;
  if (!gitHead) {
    log(`npm records no gitHead for ${version}; tagging HEAD ${head.slice(0, 7)}`);
    return head;
  }
  capture("git", ["fetch", "-q", "origin", BRANCH]);
  if (!capture("git", ["merge-base", "--is-ancestor", gitHead, `origin/${BRANCH}`]).ok) {
    log(`npm published ${gitHead.slice(0, 7)}, which is not on origin/${BRANCH}; tagging HEAD ${head.slice(0, 7)}`);
    return head;
  }
  log(gitHead === head
    ? `tagging HEAD ${head.slice(0, 7)}, which is what npm published`
    : `tagging ${gitHead.slice(0, 7)}, the commit npm published (HEAD is ${head.slice(0, 7)})`);
  return gitHead;
}

// ── Steps ────────────────────────────────────────────────────────────────────
const steps = {
  async preflight() {
    const pkg = JSON.parse(readFileSync("package.json", "utf8"));
    const server = JSON.parse(readFileSync("server.json", "utf8"));
    const manifest = JSON.parse(readFileSync("manifest.json", "utf8"));
    const sourceVersion = readFileSync("src/version.ts", "utf8").match(/^export const VERSION = '([^']+)'/m)?.[1];
    const versions = {
      "package.json": pkg.version,
      "server.json": server.version,
      "server.json packages[0]": server.packages[0].version,
      "manifest.json": manifest.version,
      "src/version.ts": sourceVersion,
    };
    if (new Set(Object.values(versions)).size !== 1) fail(`Versions disagree: ${JSON.stringify(versions)}`);
    log(`version ${version} in all five places`);

    const branch = capture("git", ["branch", "--show-current"]).out;
    if (branch !== BRANCH) fail(`On branch "${branch}", expected ${BRANCH}.`);
    const dirty = capture("git", ["status", "--porcelain"]).out;
    if (dirty) fail(`Uncommitted changes:\n${dirty}`);
    capture("git", ["fetch", "-q", "origin", BRANCH]);
    const head = capture("git", ["rev-parse", "HEAD"]).out;
    const remote = capture("git", ["rev-parse", `origin/${BRANCH}`]).out;
    if (head !== remote) fail(`HEAD ${head.slice(0, 7)} is not what GitHub has (${remote.slice(0, 7)}). Push first.`);
    log(`git clean and pushed at ${head.slice(0, 7)}`);

    const npmUser = capture("npm", ["whoami"]);
    if (!npmUser.ok) fail("Not logged in to npm. Run: npm login");
    log(`npm user ${npmUser.out}`);

    // The atlasiq account has npm 2FA with auth-type "web": every write
    // (publish, deprecate) opens a browser and waits. Without a terminal, npm
    // cannot do that and fails at once with EOTP — which is how the first run
    // of this script stopped, at npm-deprecate.
    const npmWrites = ["npm-publish", "npm-deprecate"].some(s => !skip.has(s) && STEPS.indexOf(s) >= startAt);
    if (npmWrites && !process.stdin.isTTY) {
      log("WARNING: not an interactive terminal. npm publish/deprecate need a browser 2FA confirmation");
      log("         and will fail with EOTP here. Run this from your own PowerShell window.");
    }

    if (!capture("gh", ["auth", "status"]).ok) fail("gh is not logged in. Run: gh auth login");
    log("gh authenticated");

    if (!skip.has("registry")) {
      if (!existsSync("key.pem")) fail("key.pem is missing: the registry login needs it.");
      if (!existsSync(PUBLISHER)) fail(`mcp-publisher not found at ${PUBLISHER}. Set MCP_PUBLISHER.`);
      log("key.pem and mcp-publisher present");
    }

    const published = await npmHasVersion();
    log(published ? `npm already has ${version} — npm-publish will be skipped` : `npm does not have ${version} yet`);
    if (!published) {
      const { body } = await fetchJson(`https://registry.npmjs.org/${PACKAGE}`);
      const latest = body?.["dist-tags"]?.latest;
      const newer = (a, b) => a.split(".").map(Number).reduce((r, n, i) => r || n - Number(b.split(".")[i]), 0) > 0;
      if (latest && !newer(version, latest)) fail(`${version} is not newer than npm's latest (${latest}). Bump the version.`);
      log(`npm latest is ${latest}; ${version} is newer`);
    }
  },

  async build() {
    await run("npm", ["run", "pack:mcpb"], { timeoutMs: 10 * MIN, label: "build" });
    for (const file of [`atlasfetch-${version}.mcpb`, `atlasfetch-${version}.smithery.mcpb`]) {
      if (!existsSync(file)) fail(`${file} was not produced.`);
    }
  },

  async "npm-publish"() {
    if (await npmHasVersion()) return log(`npm already has ${version}; skipping.`);
    await run("npm", ["publish"], { timeoutMs: 10 * MIN, label: "npm publish" });
  },

  async "npm-wait"() {
    // The MCP registry checks npm when publishing. Last time it was refused
    // because npm had not finished processing the release yet.
    const deadline = Date.now() + 20 * MIN;
    while (!(await npmHasVersion())) {
      if (Date.now() > deadline) throw new Error(`npm still not serving ${version} after 20 minutes`);
      log("npm not serving it yet; checking again in 20s");
      await sleep(20_000);
    }
    log(`npm serves ${version}`);
  },

  async "npm-deprecate"() {
    const message = `Superseded by ${version}. Use npx -y ${PACKAGE}@latest`;
    // Ten minutes, like publish: the browser 2FA confirmation happens inside it.
    await run("npm", ["deprecate", `${PACKAGE}@<${version}`, message], { timeoutMs: 10 * MIN, label: "npm deprecate" });
  },

  async registry() {
    const current = await registryLatest();
    if (current.some(e => e.version === version)) return log(`MCP Registry already has ${version}; skipping.`);
    await run("node", ["scripts/registry-login.mjs"], { timeoutMs: 3 * MIN, label: "registry login" });
    await run(PUBLISHER, ["publish"], { timeoutMs: 5 * MIN, label: "registry publish" });
  },

  async smithery() {
    await run("npx", ["-y", "@smithery/cli@4.11.1", "mcp", "publish", `./atlasfetch-${version}.smithery.mcpb`, "-n", SMITHERY_NAME], {
      timeoutMs: 15 * MIN,
      label: "smithery publish",
    });
  },

  async "github-release"() {
    if (capture("gh", ["release", "view", tag, "--repo", GITHUB_REPO]).ok) return log(`GitHub release ${tag} already exists; skipping.`);
    const notesFile = join(".github", "release-notes", `${tag}.md`);
    const notes = existsSync(notesFile)
      ? readFileSync(notesFile, "utf8")
      : `Release ${version}.\n\nInstall: \`npx -y ${PACKAGE}@${version}\`, or download the \`.mcpb\` below for Claude Desktop.`;
    const tempNotes = join(mkdtempSync(join(tmpdir(), "release-")), "notes.md");
    writeFileSync(tempNotes, notes);
    const target = await releaseTarget();
    try {
      await run("gh", ["release", "create", tag, `atlasfetch-${version}.mcpb`, "--repo", GITHUB_REPO, "--target", target, "--title", tag, "--notes-file", tempNotes, "--latest"], {
        timeoutMs: 5 * MIN,
        label: "github release",
      });
    } finally {
      rmSync(tempNotes, { force: true });
    }
  },

  async verify() {
    const problems = [];

    const { body: pkg } = await fetchJson(`https://registry.npmjs.org/${PACKAGE}?t=${Date.now()}`);
    const npmLatest = pkg?.["dist-tags"]?.latest;
    (npmLatest === version ? log : m => problems.push(m))(`npm latest: ${npmLatest}`);
    const stale = Object.entries(pkg?.versions ?? {}).filter(([v, meta]) => v !== version && !meta.deprecated).map(([v]) => v);
    (stale.length === 0 ? log : m => problems.push(m))(`older versions not deprecated: ${stale.join(", ") || "none"}`);

    if (!skip.has("registry")) {
      // A fresh publish can take a moment to become "latest". Allow five
      // minutes: each poll of that search endpoint can itself take most of one.
      const deadline = Date.now() + 5 * MIN;
      let latest = (await registryLatest()).find(e => e.latest);
      while (latest?.version !== version && Date.now() < deadline) {
        log(`MCP Registry still reports ${latest?.version} as latest; checking again in 15s`);
        await sleep(15_000);
        latest = (await registryLatest()).find(e => e.latest);
      }
      (latest?.version === version ? log : m => problems.push(m))(`MCP Registry latest: ${latest?.version}`);
    }

    if (!skip.has("github-release")) {
      const release = capture("gh", ["release", "view", tag, "--repo", GITHUB_REPO, "--json", "assets", "--jq", "[.assets[].name]|join(\",\")"]);
      (release.ok && release.out.includes(`atlasfetch-${version}.mcpb`) ? log : m => problems.push(m))(`GitHub release ${tag} assets: ${release.out || "missing"}`);
    }

    // Last: install the published package from an empty folder and use it.
    await run("node", ["scripts/registry-smoke.mjs"], { timeoutMs: 5 * MIN, label: "clean npx install" });

    if (problems.length) throw new Error(`Verification found problems:\n    - ${problems.join("\n    - ")}`);
  },
};

// ── Run ──────────────────────────────────────────────────────────────────────
const plan = STEPS.slice(startAt).filter(s => !skip.has(s));
const planned = dryRun ? ["preflight"] : plan;

console.log(`\nReleasing ${PACKAGE} ${version}${dryRun ? " — DRY RUN, nothing will be published" : ""}`);
console.log(`Steps: ${plan.join(" → ")}\n`);

// Resuming with --from skips preflight, and with it the tool checks. Check the
// tools the remaining steps need anyway, before any of them runs.
try {
  if (!planned.includes("preflight")) {
    const needs = new Set();
    if (planned.some(s => s.startsWith("npm-") || s === "build")) needs.add("npm");
    if (planned.some(s => s === "github-release" || s === "verify")) needs.add("gh");
    for (const tool of needs) {
      const check = capture(tool, ["--version"]);
      if (!check.ok) fail(`${tool} is installed but failed to run: ${check.err || check.out}`);
    }
  }
} catch (error) {
  fail(error.message);
}

for (const name of planned) {
  const started = Date.now();
  console.log(`▶ ${name}`);
  try {
    await steps[name]();
  } catch (error) {
    fail(`${name} failed: ${error.message}\n  Fix it, then resume with: node scripts/release.mjs --from ${name}`);
  }
  console.log(`✓ ${name} (${Math.round((Date.now() - started) / 1000)}s)\n`);
}

if (dryRun) {
  console.log(`Dry run passed. Would run next: ${plan.filter(s => s !== "preflight").join(" → ")}`);
} else {
  console.log(`Released ${PACKAGE} ${version}.`);
}

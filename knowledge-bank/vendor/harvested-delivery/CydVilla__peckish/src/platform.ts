/**
 * Where Peckish is allowed to run, and how sign-in can happen there.
 *
 * dd-cli v0.2.2 added Linux (amd64) builds, so the Mac is no longer the only
 * backend — but a Linux host is usually a container, VM or cloud sandbox with
 * no browser and no OS keychain, and `dd-cli login` cannot finish in one. That
 * case has its own path: mint a token with `dd-cli export-token` on a machine
 * that does have a browser, then inject it as DD_CLI_ACCESS_TOKEN here.
 *
 * Everything below is a pure function of (platform, arch, env) so the surfaces
 * can ask the same questions and the tests can drive every branch.
 */
import { platform as osPlatform, arch as osArch } from "node:os";

/** dd-cli ships builds for these two targets only. */
export type PlatformId = "darwin-arm64" | "linux-amd64" | "unsupported";

/** First dd-cli release with Linux builds and `export-token`. */
export const DD_CLI_LINUX_MIN_VERSION = "0.2.2";

/** First dd-cli release Peckish works against at all (`--intent` is required). */
export const DD_CLI_MIN_VERSION = "0.2.1";

/**
 * The dd-cli Peckish is built against. Below this, ordering still works, but
 * address lookup (0.2.3), promo-aware menus and `--address-id` (0.2.4), and
 * the search filters, pickup availability and weight-priced items (0.2.5) are
 * unavailable — Peckish detects the version and leaves those paths off.
 */
export const DD_CLI_RECOMMENDED_VERSION = "0.2.5";

/** Parse the first semver-looking token out of `dd-cli --version` output. */
export function parseVersion(output: string): string | null {
  // Tolerates a leading "v" (dd-cli prints both forms across releases).
  return output.match(/v?(\d+\.\d+\.\d+)\b/)?.[1] ?? null;
}

/** Compare dotted numeric versions: negative if a < b, 0 if equal, positive if a > b. */
export function compareVersions(a: string, b: string): number {
  const pa = a.split(".").map(Number);
  const pb = b.split(".").map(Number);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const d = (pa[i] ?? 0) - (pb[i] ?? 0);
    if (d !== 0) return d;
  }
  return 0;
}

/**
 * How the installed dd-cli is described to the model. Newer releases are
 * additive, so an older binary just means fewer options — the model is told
 * which, once, instead of discovering it as a failed call mid-order.
 */
export function ddCliVersionLine(version: string | null | undefined): string {
  if (!version) return "unknown";
  if (compareVersions(version, DD_CLI_RECOMMENDED_VERSION) >= 0) return version;
  const missing: string[] = [];
  if (compareVersions(version, "0.2.3") < 0)
    missing.push("address lookup (find_address/add_address)");
  if (compareVersions(version, "0.2.4") < 0)
    missing.push("promo-aware menus and address_id search");
  if (compareVersions(version, "0.2.5") < 0)
    missing.push("search filters, pickup availability and weight-priced items");
  return (
    `${version} — older than the ${DD_CLI_RECOMMENDED_VERSION} Peckish targets, so these are ` +
    `unavailable: ${missing.join("; ")}. Mention the upgrade only if the user asks for one of them.`
  );
}

/** What the user gets told when their dd-cli predates a feature they asked for. */
export function upgradeHint(current: string | null): string {
  const have = current ? `dd-cli ${current} is installed` : "your dd-cli version could not be read";
  return (
    `${have}; this needs dd-cli ≥ ${DD_CLI_RECOMMENDED_VERSION}. Download the newer ` +
    "asset from https://github.com/doordash-oss/doordash-cli/releases and reinstall."
  );
}

export function platformId(platform = osPlatform(), arch = osArch()): PlatformId {
  if (platform === "darwin" && arch === "arm64") return "darwin-arm64";
  if (platform === "linux" && arch === "x64") return "linux-amd64";
  return "unsupported";
}

/** The release asset for this platform, or null when dd-cli ships none. */
export function ddCliAsset(version: string, id: PlatformId = platformId()): string | null {
  return id === "unsupported" ? null : `dd-cli-v${version}-${id}.tar.gz`;
}

/**
 * Can an interactive `dd-cli login` complete here? It hands off to a browser,
 * which needs a desktop session: macOS always has one, Linux needs a display.
 */
export function canBrowserSignin(
  env: NodeJS.ProcessEnv = process.env,
  platform = osPlatform(),
): boolean {
  if (platform === "darwin") return true;
  if (platform !== "linux") return false;
  return Boolean(env.DISPLAY || env.WAYLAND_DISPLAY);
}

/** True when a token was injected for a browserless environment. */
export function hasInjectedToken(env: NodeJS.ProcessEnv = process.env): boolean {
  return Boolean(env.DD_CLI_ACCESS_TOKEN?.trim());
}

const EXPORT_TOKEN_STEPS =
  "on a machine with a browser run `dd-cli export-token` (dd-cli ≥ " +
  `${DD_CLI_LINUX_MIN_VERSION}), then set DD_CLI_ACCESS_TOKEN to that token in the ` +
  "environment running Peckish and retry.";

/**
 * What to tell the user (and the model) when DoorDash sign-in isn't working.
 * Three distinct situations, three different fixes.
 */
export function signinHint(
  env: NodeJS.ProcessEnv = process.env,
  platform = osPlatform(),
): string {
  if (hasInjectedToken(env)) {
    return (
      "DD_CLI_ACCESS_TOKEN is set but DoorDash rejected it, so that token is invalid or " +
      `expired — mint a fresh one: ${EXPORT_TOKEN_STEPS}`
    );
  }
  if (canBrowserSignin(env, platform)) {
    return "The user must run `dd-cli login` in a separate terminal (or approve Peckish's sign-in assist, which runs it for them), then retry.";
  }
  return (
    "This environment has no browser session, so `dd-cli login` cannot complete here — " +
    EXPORT_TOKEN_STEPS
  );
}

/** Install instructions for the platform actually in use. */
export function installHint(id: PlatformId = platformId()): string {
  if (id === "unsupported") {
    return (
      `dd-cli publishes macOS (Apple Silicon) and Linux (x86_64) builds only — this machine is ` +
      `${osPlatform()}/${osArch()}, which has no dd-cli build.`
    );
  }
  return (
    `Install it from https://github.com/doordash-oss/doordash-cli/releases (asset ` +
    `dd-cli-v<version>-${id}.tar.gz, verify its SHA256, then \`bash install.sh\`), or set ` +
    "DD_CLI_PATH to an existing binary."
  );
}

import { z } from "zod";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { createWriteStream } from "node:fs";
import { unlink, mkdir, readdir, readFile, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Readable } from "node:stream";
import { pipeline } from "node:stream/promises";
import { randomUUID } from "node:crypto";

const execFileAsync = promisify(execFile);

const AscBuildEntrySchema = z.object({
  id: z.string(),
  attributes: z.object({
    buildNumber: z.string().optional(),
    version: z.string().optional(),
  }).optional(),
  buildNumber: z.string().optional(),
  version: z.string().optional(),
});

const AscUploadResponseSchema = z.object({
  data: z.union([z.array(AscBuildEntrySchema), AscBuildEntrySchema]),
});

const EXEC_BUFFER = 32 * 1024 * 1024;          // 32 MB — covers large build/app lists
const UPLOAD_TIMEOUT_MS = 30 * 60 * 1000;     // 30 min — upload + Apple processing wait
const CLI_TIMEOUT_MS = 60_000;                 // 60 s  — list / status commands
const DOWNLOAD_TIMEOUT_MS = 15 * 60 * 1000;   // 15 min — artifact download from Codemagic
const MAX_ARTIFACT_BYTES = 4 * 1024 ** 3;     // 4 GB  — sanity cap before streaming to disk

/**
 * Run an `asc` CLI command and parse its JSON output.
 * Requires ASC_KEY_ID, ASC_ISSUER_ID, ASC_PRIVATE_KEY_B64, and ASC_BYPASS_KEYCHAIN=1
 * to be set in the environment.
 * @param args - CLI arguments, e.g. ["apps", "list"].
 * @returns Parsed JSON response from the CLI.
 */
export async function runAsc<T>(args: string[]): Promise<T> {
  try {
    const { stdout } = await execFileAsync("asc", [...args, "--output", "json"], {
      maxBuffer: EXEC_BUFFER,
      timeout: CLI_TIMEOUT_MS,
    });
    return JSON.parse(stdout) as T;
  } catch (error) {
    throw new Error(`asc ${args[0]} failed: ${error instanceof Error ? error.message : String(error)}`);
  }
}

export interface AscAppRaw {
  id: string;
  attributes: {
    name: string;
    bundleId: string;
    sku: string;
  };
}

export interface AscApp {
  id: string;
  name: string;
  bundleId: string;
}

/** List all apps in App Store Connect. */
export async function listAscApps(): Promise<AscApp[]> {
  const response = await runAsc<{ data: AscAppRaw[] }>(["apps", "list"]);
  return response.data.map(app => ({
    id: app.id,
    name: app.attributes.name,
    bundleId: app.attributes.bundleId,
  }));
}

interface AscBuildRaw {
  id: string;
  attributes: {
    version: string;
    uploadedDate: string;
    processingState: string;
    expired: boolean;
  };
}

export interface AscBuild {
  id: string;
  version: string;
  uploadedDate: string;
  processingState: string;
  expired: boolean;
}

/**
 * List TestFlight builds for an app in App Store Connect.
 * @param appId - The App Store Connect app ID.
 */
export async function listAscBuilds(appId: string): Promise<AscBuild[]> {
  const response = await runAsc<{ data: AscBuildRaw[] }>(["builds", "list", "--app", appId]);
  return response.data.map(b => ({
    id: b.id,
    version: b.attributes.version,
    uploadedDate: b.attributes.uploadedDate,
    processingState: b.attributes.processingState,
    expired: b.attributes.expired,
  }));
}

interface AscBetaGroupRaw {
  id: string;
  attributes: {
    name: string;
    isInternalGroup?: boolean;
    feedbackEnabled: boolean;
  };
}

export interface AscBetaGroup {
  id: string;
  name: string;
  isInternalGroup: boolean;
  feedbackEnabled: boolean;
}

/**
 * List TestFlight beta groups for an app.
 * @param appId - The App Store Connect app ID.
 */
export async function listTestFlightGroups(appId: string): Promise<AscBetaGroup[]> {
  const response = await runAsc<{ data: AscBetaGroupRaw[] }>(["testflight", "groups", "list", "--app", appId]);
  return response.data.map(g => ({
    id: g.id,
    name: g.attributes.name,
    isInternalGroup: g.attributes.isInternalGroup ?? false,
    feedbackEnabled: g.attributes.feedbackEnabled,
  }));
}

export interface AscReviewStatus {
  appId: string;
  reviewState: string;
  nextAction: string;
  blockers: string[];
  version: {
    id: string;
    version: string;
    platform: string;
    state: string;
  } | null;
}

/**
 * Get the current App Store review status for an app.
 * @param appId - The App Store Connect app ID.
 */
export async function getReviewStatus(appId: string): Promise<AscReviewStatus> {
  return runAsc<AscReviewStatus>(["review", "status", "--app", appId]);
}

export interface AscReleaseStatus {
  app: {
    id: string;
    bundleId: string;
    name: string;
  };
  summary: {
    health: string;
    nextAction: string;
    blockers: string[];
  };
  builds: {
    latest: {
      version: string;
      buildNumber: string;
      processingState: string;
      uploadedDate: string;
    } | null;
  };
  testflight: {
    betaReviewState: string;
    submittedDate: string;
  } | null;
  appstore: {
    version: string;
    state: string;
    platform: string;
  } | null;
  submission: {
    inFlight: boolean;
    blockingIssues: string[];
  };
}

/**
 * Get a full release pipeline status for an app — builds, TestFlight, App Store, and submission state.
 * @param appId - The App Store Connect app ID.
 */
export async function getReleaseStatus(appId: string): Promise<AscReleaseStatus> {
  return runAsc<AscReleaseStatus>(["status", "--app", appId]);
}

/**
 * Run a preflight readiness check for an App Store version.
 * Returns an ordered remediation plan — the first item is the next thing to fix.
 * @param appId - The App Store Connect app ID.
 * @param version - App Store version string e.g. "1.2.3".
 */
export async function validateAppSubmission(appId: string, version: string): Promise<unknown> {
  return runAsc<unknown>(["validate", "--app", appId, "--version", version]);
}

/**
 * Download an IPA from a URL and upload it to TestFlight.
 * The IPA is saved to a temp file, uploaded via the asc CLI, then deleted.
 * @param appId - The App Store Connect app ID.
 * @param ipaUrl - Direct download URL for the IPA (e.g. a Codemagic artifact URL).
 * @param betaGroup - Optional TestFlight beta group name to distribute to after upload.
 */
export async function uploadToTestFlight(
  appId: string,
  ipaUrl: string,
  betaGroup?: string,
  apiToken?: string,
): Promise<string> {
  const tempPath = join(tmpdir(), `cm-${randomUUID()}.ipa`);

  const response = await fetch(ipaUrl, {
    headers: apiToken ? { "x-auth-token": apiToken } : {},
    signal: AbortSignal.timeout(DOWNLOAD_TIMEOUT_MS),
  });
  if (!response.ok) {
    throw new Error(`Failed to download IPA: ${response.status} ${response.statusText}`);
  }
  const ipaLen = parseInt(response.headers.get("content-length") ?? "0", 10);
  if (ipaLen > MAX_ARTIFACT_BYTES) throw new Error(`IPA too large to download: ${ipaLen} bytes`);
  if (!response.body) throw new Error("IPA response body is empty");
  await pipeline(Readable.fromWeb(response.body as Parameters<typeof Readable.fromWeb>[0]), createWriteStream(tempPath));

  try {
    const args = ["builds", "upload", "--app", appId, "--ipa", tempPath, "--wait"];
    if (betaGroup) args.push("--group", betaGroup);
    const { stdout } = await execFileAsync("asc", args, {
      maxBuffer: EXEC_BUFFER,
      timeout: UPLOAD_TIMEOUT_MS,
    });
    return stdout;
  } finally {
    await unlink(tempPath).catch(() => { });
  }
}

export interface AscBuildUploadResult {
  id: string;
  buildNumber: string;
  version: string;
}

/**
 * Download an IPA from a URL and upload it to App Store Connect.
 * Does NOT wait for Apple's processing pipeline — returns as soon as the upload commits (~2-5 min).
 * Poll list_asc_builds until processingState is VALID before calling submitForAppStoreReview.
 * @param appId - The App Store Connect app ID.
 * @param ipaUrl - Direct download URL for the IPA (e.g. a Codemagic artifact URL).
 * @returns Build ID, build number, and version string for use in subsequent calls.
 */
export async function uploadBuildToAsc(appId: string, ipaUrl: string, apiToken?: string): Promise<AscBuildUploadResult> {
  const tempPath = join(tmpdir(), `cm-${randomUUID()}.ipa`);
  const response = await fetch(ipaUrl, {
    headers: apiToken ? { "x-auth-token": apiToken } : {},
    signal: AbortSignal.timeout(DOWNLOAD_TIMEOUT_MS),
  });
  if (!response.ok) throw new Error(`Failed to download IPA: ${response.status} ${response.statusText}`);
  const ipaLen = parseInt(response.headers.get("content-length") ?? "0", 10);
  if (ipaLen > MAX_ARTIFACT_BYTES) throw new Error(`IPA too large to download: ${ipaLen} bytes`);
  if (!response.body) throw new Error("IPA response body is empty");
  await pipeline(Readable.fromWeb(response.body as Parameters<typeof Readable.fromWeb>[0]), createWriteStream(tempPath));
  try {
    const { stdout } = await execFileAsync("asc", [
      "builds", "upload", "--app", appId, "--ipa", tempPath, "--output", "json",
    ], { maxBuffer: EXEC_BUFFER, timeout: UPLOAD_TIMEOUT_MS });
    const parsed = AscUploadResponseSchema.parse(JSON.parse(stdout));
    const build = Array.isArray(parsed.data) ? parsed.data[0] : parsed.data;
    if (!build) throw new Error(`Unexpected upload response — no build entry in: ${stdout.slice(0, 200)}`);
    return {
      id: build.id,
      buildNumber: build.attributes?.buildNumber ?? build.buildNumber ?? "unknown",
      version: build.attributes?.version ?? build.version ?? "unknown",
    };
  } finally {
    await unlink(tempPath).catch(() => {});
  }
}

/**
 * Attach an already-uploaded and VALID build to an App Store version and submit for review.
 * The build must have processingState VALID — use list_asc_builds to confirm before calling this.
 * @param appId - The App Store Connect app ID.
 * @param version - Version string e.g. "1.2.3".
 * @param buildId - Build UUID from uploadBuildToAsc or listAscBuilds.
 */
export async function submitForAppStoreReview(appId: string, version: string, buildId: string): Promise<unknown> {
  return runAsc(["review", "submit", "--app", appId, "--version", version, "--build", buildId, "--confirm"]);
}

/** Resolve a version string (e.g. "1.2.3") to its App Store version ID. */
async function getAppStoreVersionId(appId: string, version: string): Promise<string> {
  const result = await runAsc<{ data: Array<{ id: string }> }>(
    ["versions", "list", "--app", appId, "--version", version]
  );
  if (!result.data.length) throw new Error(`No App Store version found for ${version}`);
  return result.data[0].id;
}

export interface VersionMetadataFields {
  whatsNew?: string;
  description?: string;
  keywords?: string;
  promotionalText?: string;
  supportUrl?: string;
  marketingUrl?: string;
}

/**
 * Update App Store version localization metadata (What's New, description, keywords, etc.).
 * @param appId - The App Store Connect app ID.
 * @param version - Version string e.g. "1.2.3" — resolved to a version ID internally.
 * @param locale - BCP-47 locale e.g. "en-US", "de-DE", "zh-Hans".
 * @param fields - One or more fields to update.
 */
export async function setVersionMetadata(
  appId: string,
  version: string,
  locale: string,
  fields: VersionMetadataFields,
): Promise<unknown> {
  const versionId = await getAppStoreVersionId(appId, version);
  const args = ["localizations", "update", "--version", versionId, "--locale", locale];
  if (fields.whatsNew) args.push("--whats-new", fields.whatsNew);
  if (fields.description) args.push("--description", fields.description);
  if (fields.keywords) args.push("--keywords", fields.keywords);
  if (fields.promotionalText) args.push("--promotional-text", fields.promotionalText);
  if (fields.supportUrl) args.push("--support-url", fields.supportUrl);
  if (fields.marketingUrl) args.push("--marketing-url", fields.marketingUrl);
  return runAsc<unknown>(args);
}

/**
 * Set export compliance on a build.
 * Most apps only use standard HTTPS/TLS — set usesNonExemptEncryption=false.
 * Only set true if the app implements custom/proprietary encryption beyond standard protocols.
 * @param appId - The App Store Connect app ID.
 * @param usesNonExemptEncryption - false for HTTPS/TLS-only apps (most common); true for custom encryption.
 * @param buildId - Specific build ID to update. Defaults to the latest build for the app.
 */
export async function setExportCompliance(
  appId: string,
  usesNonExemptEncryption: boolean,
  buildId?: string,
): Promise<unknown> {
  const args = ["builds", "update"];
  if (buildId) {
    args.push("--build-id", buildId);
  } else {
    args.push("--app", appId, "--latest");
  }
  args.push(`--uses-non-exempt-encryption=${String(usesNonExemptEncryption)}`);
  return runAsc<unknown>(args);
}

/**
 * Release an App Store version that is in the "Pending Developer Release" state.
 * This makes the update publicly available immediately.
 * @param appId - The App Store Connect app ID.
 * @param version - Version string e.g. "1.2.3".
 */
export async function releaseVersion(appId: string, version: string): Promise<unknown> {
  const versionId = await getAppStoreVersionId(appId, version);
  return runAsc<unknown>(["versions", "release", "--version-id", versionId, "--confirm"]);
}

/**
 * Manage a phased rollout for an App Store version.
 * @param appId - The App Store Connect app ID.
 * @param version - Version string e.g. "1.2.3".
 * @param action - "create": set up phased rollout before submission.
 *                 "pause": pause an in-progress rollout.
 *                 "resume": resume a paused rollout.
 *                 "complete": release to all users immediately.
 */
export async function setPhasedRelease(
  appId: string,
  version: string,
  action: "create" | "pause" | "resume" | "complete",
): Promise<unknown> {
  const versionId = await getAppStoreVersionId(appId, version);
  if (action === "create") {
    return runAsc<unknown>(["versions", "phased-release", "create", "--version-id", versionId]);
  }
  const phasedRelease = await runAsc<{ id: string }>(
    ["versions", "phased-release", "view", "--version-id", versionId]
  );
  const state = action === "pause" ? "PAUSED" : action === "resume" ? "ACTIVE" : "COMPLETE";
  return runAsc<unknown>(["versions", "phased-release", "update", "--id", phasedRelease.id, "--state", state]);
}

/**
 * Submit a build for TestFlight beta app review.
 * Required before external beta groups can access the build.
 * @param buildId - The App Store Connect build ID (from list_asc_builds).
 */
export async function submitBetaReview(buildId: string): Promise<unknown> {
  return runAsc<unknown>(["testflight", "review", "submit", "--build-id", buildId, "--confirm"]);
}

/**
 * Add a tester to TestFlight by email, optionally to a specific group.
 * @param appId - The App Store Connect app ID.
 * @param email - Tester email address.
 * @param group - Group name or ID to add the tester to (optional).
 */
export async function addTestFlightTester(
  appId: string,
  email: string,
  group?: string,
): Promise<unknown> {
  const args = ["testflight", "testers", "add", "--app", appId, "--email", email];
  if (group) args.push("--group", group);
  return runAsc<unknown>(args);
}

/**
 * Create a new TestFlight beta group for an app.
 * @param appId - The App Store Connect app ID.
 * @param name - Display name for the group.
 * @param internal - If true, creates an internal group (Apple employees/org members only).
 */
export async function createTestFlightGroup(
  appId: string,
  name: string,
  internal = false,
): Promise<unknown> {
  const args = ["testflight", "groups", "create", "--app", appId, "--name", name];
  if (internal) args.push("--internal");
  return runAsc<unknown>(args);
}

// Fields that live in app-info/{locale}.json
const APP_INFO_FIELDS = new Set(["name", "subtitle", "privacyPolicyUrl", "privacyChoicesUrl", "privacyPolicyText"]);
// Fields that live in version/{version}/{locale}.json
const VERSION_FIELDS = new Set(["description", "keywords", "marketingUrl", "promotionalText", "supportUrl", "whatsNew"]);

export interface IosStoreListingLocale {
  appInfo?: Record<string, string>;
  version?: Record<string, string>;
}

export type IosStoreListingFields = Partial<{
  name: string;
  subtitle: string;
  privacyPolicyUrl: string;
  privacyChoicesUrl: string;
  privacyPolicyText: string;
  description: string;
  keywords: string;
  marketingUrl: string;
  promotionalText: string;
  supportUrl: string;
  whatsNew: string;
}>;

/**
 * Pull all App Store Connect metadata for an app version.
 * Returns an object keyed by locale code, with app-info and version fields separated.
 * @param appId - The App Store Connect app ID.
 * @param version - The version string e.g. "1.2.3".
 */
export async function getIosStoreListing(
  appId: string,
  version: string,
): Promise<Record<string, IosStoreListingLocale>> {
  const tempDir = join(tmpdir(), `asc-metadata-${randomUUID()}`);
  await mkdir(tempDir, { recursive: true });
  try {
    await execFileAsync(
      "asc",
      ["metadata", "pull", "--app", appId, "--version", version, "--dir", tempDir],
      { maxBuffer: EXEC_BUFFER, timeout: CLI_TIMEOUT_MS },
    );
    const result: Record<string, IosStoreListingLocale> = {};

    // Read app-info locales — directory may not exist for apps with no localizations yet.
    const appInfoDir = join(tempDir, "app-info");
    const appInfoFiles = await readdir(appInfoDir).catch(() => [] as string[]);
    for (const file of appInfoFiles.filter(f => f.endsWith(".json"))) {
      const locale = file.slice(0, -5);
      result[locale] = { ...result[locale], appInfo: JSON.parse(await readFile(join(appInfoDir, file), "utf8")) };
    }

    // Read version locales.
    const versionDir = join(tempDir, "version", version);
    const versionFiles = await readdir(versionDir).catch(() => [] as string[]);
    for (const file of versionFiles.filter(f => f.endsWith(".json"))) {
      const locale = file.slice(0, -5);
      result[locale] = { ...result[locale], version: JSON.parse(await readFile(join(versionDir, file), "utf8")) };
    }

    return result;
  } finally {
    await rm(tempDir, { recursive: true, force: true });
  }
}

/**
 * Update App Store Connect metadata for a single locale.
 * Only the fields provided are written — omitted fields are left unchanged.
 * Fields are split across the two canonical files (app-info and version).
 * @param appId - The App Store Connect app ID.
 * @param version - The version string e.g. "1.2.3".
 * @param locale - BCP-47 locale code e.g. "en-US".
 * @param fields - Fields to update (any subset of app-info and version fields).
 */
export async function setIosStoreListing(
  appId: string,
  version: string,
  locale: string,
  fields: IosStoreListingFields,
): Promise<void> {
  const tempDir = join(tmpdir(), `asc-metadata-${randomUUID()}`);
  try {
    const appInfoData = Object.fromEntries(
      Object.entries(fields).filter(([k]) => APP_INFO_FIELDS.has(k)),
    );
    const versionData = Object.fromEntries(
      Object.entries(fields).filter(([k]) => VERSION_FIELDS.has(k)),
    );

    // Build only the directories and files we actually need.
    if (Object.keys(appInfoData).length > 0) {
      const dir = join(tempDir, "app-info");
      await mkdir(dir, { recursive: true });
      await writeFile(join(dir, `${locale}.json`), JSON.stringify(appInfoData, null, 2));
    }
    if (Object.keys(versionData).length > 0) {
      const dir = join(tempDir, "version", version);
      await mkdir(dir, { recursive: true });
      await writeFile(join(dir, `${locale}.json`), JSON.stringify(versionData, null, 2));
    }

    await execFileAsync(
      "asc",
      ["metadata", "validate", "--dir", tempDir],
      { maxBuffer: EXEC_BUFFER, timeout: CLI_TIMEOUT_MS },
    );
    await execFileAsync(
      "asc",
      ["metadata", "apply", "--app", appId, "--version", version, "--dir", tempDir],
      { maxBuffer: EXEC_BUFFER, timeout: CLI_TIMEOUT_MS },
    );
  } finally {
    await rm(tempDir, { recursive: true, force: true });
  }
}

// ---------------------------------------------------------------------------
// Screenshots
// ---------------------------------------------------------------------------

const SCREENSHOT_UPLOAD_TIMEOUT_MS = 5 * 60 * 1000;

/**
 * Download a single screenshot URL to a directory.
 * Extension is inferred from the URL path first, then the Content-Type header.
 * Files are named screenshot_00.png, screenshot_01.jpg, etc.
 */
async function downloadScreenshot(url: string, destDir: string, index: number): Promise<void> {
  const response = await fetch(url, { signal: AbortSignal.timeout(30_000) });
  if (!response.ok) throw new Error(`Failed to download screenshot ${index + 1}: HTTP ${response.status}`);
  const urlPath = new URL(url).pathname;
  const extMatch = urlPath.match(/\.(png|jpe?g)$/i);
  const contentType = response.headers.get("content-type") ?? "";
  const ext = extMatch ? extMatch[1].toLowerCase().replace("jpeg", "jpg") : contentType.includes("png") ? "png" : "jpg";
  const destPath = join(destDir, `screenshot_${String(index).padStart(2, "0")}.${ext}`);
  await writeFile(destPath, Buffer.from(await response.arrayBuffer()));
}

export interface IosScreenshotType {
  deviceType: string;
  dimensions: { width: number; height: number }[];
}

/**
 * List the screenshot device types and their required pixel dimensions.
 * By default returns the two most-required types (IPHONE_65 and IPAD_PRO_3GEN_129).
 * Pass all=true to get the full matrix.
 * @param all - If true, return all supported device types instead of just the common ones.
 */
export async function listIosScreenshotTypes(all = false): Promise<IosScreenshotType[]> {
  const args = ["screenshots", "sizes"];
  if (all) args.push("--all");
  const result = await runAsc<{ sizes: { displayType: string; dimensions: { width: number; height: number }[] }[] }>(args);
  return result.sizes.map(s => ({
    deviceType: s.displayType.replace(/^APP_/, ""),
    dimensions: s.dimensions,
  }));
}

/**
 * Download screenshots from URLs and upload them to App Store Connect for a
 * specific device type and locale.
 * Downloads run in parallel; upload uses the asc CLI fan-out mode (locale subdir).
 * @param appId - The App Store Connect app ID.
 * @param version - The version string e.g. "1.2.3".
 * @param locale - BCP-47 locale code e.g. "en-US".
 * @param deviceType - Device type string e.g. "IPHONE_65" (from list_ios_screenshot_types).
 * @param screenshotUrls - URLs of screenshot images to upload (max 10).
 * @param replace - If true, delete existing screenshots for this device type before uploading.
 */
export async function uploadIosScreenshots(
  appId: string,
  version: string,
  locale: string,
  deviceType: string,
  screenshotUrls: string[],
  replace = false,
): Promise<unknown> {
  const tempDir = join(tmpdir(), `asc-screenshots-${randomUUID()}`);
  const localeDir = join(tempDir, locale);
  await mkdir(localeDir, { recursive: true });
  try {
    await Promise.all(screenshotUrls.map((url, i) => downloadScreenshot(url, localeDir, i)));
    const args = [
      "screenshots", "upload",
      "--app", appId,
      "--version", version,
      "--path", tempDir,
      "--device-type", deviceType,
      "--output", "json",
    ];
    if (replace) args.push("--replace");
    const { stdout } = await execFileAsync("asc", args, {
      maxBuffer: EXEC_BUFFER,
      timeout: SCREENSHOT_UPLOAD_TIMEOUT_MS,
    });
    return JSON.parse(stdout);
  } finally {
    await rm(tempDir, { recursive: true, force: true });
  }
}
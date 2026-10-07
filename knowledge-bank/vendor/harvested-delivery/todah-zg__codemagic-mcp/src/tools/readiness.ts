import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { listAscBuilds, getIosStoreListing, validateAppSubmission } from "../asc.js";
import { listBundles, listTracks } from "../googleplay.js";
import { getAndroidStoreListing } from "../androidpublisher.js";

interface Check {
  name: string;
  status: "pass" | "fail" | "unknown";
  detail: string;
  fix_by?: "agent" | "human";
  tool?: string;
  where?: string;
}

function renderReport(platform: string, target: string, checks: Check[]): string {
  const agentBlockers = checks.filter(c => c.status === "fail" && c.fix_by === "agent");
  const humanItems = checks.filter(c => c.fix_by === "human");

  const lines: string[] = [
    `${platform} Publish Readiness — ${target}`,
    "─".repeat(54),
    "",
    "CHECKS",
  ];

  for (const c of checks) {
    const icon = c.status === "pass" ? "✓" : c.status === "fail" ? "✗" : "?";
    lines.push(`  ${icon}  ${c.name}: ${c.detail}`);
  }

  if (agentBlockers.length > 0) {
    lines.push("", "BLOCKERS  (agent can fix)");
    for (const b of agentBlockers) {
      lines.push(`  • ${b.name} → call ${b.tool}`);
    }
  }

  lines.push("", "HUMAN-REQUIRED  (cannot be verified via API — confirm manually before submitting)");
  for (const h of humanItems) {
    lines.push(`  • ${h.name}${h.where ? `  →  ${h.where}` : ""}`);
  }

  const ready = agentBlockers.length === 0;
  const verdict = ready
    ? "Looks ready — confirm the human-required items above, then submit"
    : `Not ready — ${agentBlockers.length} blocker(s) must be fixed first`;
  lines.push("", `VERDICT: ${verdict}`);

  return lines.join("\n");
}

async function runIosChecks(appId: string, version: string): Promise<Check[]> {
  const checks: Check[] = [];

  // Check: VALID build available
  try {
    const builds = await listAscBuilds(appId);
    const valid = builds.find(b => b.processingState === "VALID" && !b.expired);
    if (valid) {
      checks.push({ name: "Valid build", status: "pass", detail: `v${valid.version} is VALID` });
    } else if (builds.length > 0) {
      const latest = builds[0];
      checks.push({
        name: "Valid build",
        status: "fail",
        detail: `Latest build (v${latest.version}) is ${latest.processingState}${latest.expired ? ", expired" : ""}`,
        fix_by: "agent",
        tool: "upload_build_to_asc",
      });
    } else {
      checks.push({
        name: "Valid build",
        status: "fail",
        detail: "No builds found — upload a build first",
        fix_by: "agent",
        tool: "upload_build_to_asc",
      });
    }
  } catch (e) {
    checks.push({ name: "Valid build", status: "unknown", detail: `Could not check: ${e instanceof Error ? e.message : String(e)}` });
  }

  // Check: What's New and description set
  try {
    const listing = await getIosStoreListing(appId, version);
    const locale = listing["en-US"] ?? Object.values(listing)[0];
    if (!locale) {
      checks.push({
        name: "Store listing (en-US)",
        status: "fail",
        detail: "No listing data found",
        fix_by: "agent",
        tool: "set_ios_store_listing",
      });
    } else {
      const missing: string[] = [];
      if (!locale.version?.["whatsNew"]) missing.push("What's New");
      if (!locale.version?.["description"]) missing.push("description");
      if (missing.length > 0) {
        checks.push({
          name: "Store listing (en-US)",
          status: "fail",
          detail: `Missing: ${missing.join(", ")}`,
          fix_by: "agent",
          tool: "set_ios_store_listing",
        });
      } else {
        checks.push({ name: "Store listing (en-US)", status: "pass", detail: "What's New and description are set" });
      }
    }
  } catch (e) {
    checks.push({ name: "Store listing (en-US)", status: "unknown", detail: `Could not check: ${e instanceof Error ? e.message : String(e)}` });
  }

  // Check: binary and metadata validation via asc validate
  // asc validate exits non-zero when there are blockers — execFileAsync throws, so
  // a thrown error here means real issues; no throw means clean.
  try {
    await validateAppSubmission(appId, version);
    checks.push({ name: "Binary validation (asc validate)", status: "pass", detail: "No blockers" });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    checks.push({
      name: "Binary validation (asc validate)",
      status: "fail",
      detail: msg.slice(0, 400),
      fix_by: "agent",
      tool: "validate_app_submission",
    });
  }

  // Static human-required items — always present because there is no API for them
  checks.push(
    { name: "Age rating questionnaire", status: "unknown", detail: "Cannot verify via API", fix_by: "human", where: "App Store Connect → App Information → Age Rating" },
    { name: "Privacy nutrition labels", status: "unknown", detail: "Declare what data the app collects", fix_by: "human", where: "App Store Connect → App Privacy" },
    { name: "Privacy policy URL", status: "unknown", detail: "A live public URL is required", fix_by: "human", where: "App Store Connect → App Information → Privacy Policy URL" },
    { name: "Legal agreements", status: "unknown", detail: "Free Apps Agreement (and Paid Apps if applicable) must be Active", fix_by: "human", where: "App Store Connect → Business → Agreements" },
  );

  return checks;
}

async function runAndroidChecks(packageName: string, language: string): Promise<Check[]> {
  const checks: Check[] = [];

  // Check: at least one bundle uploaded
  try {
    const bundles = await listBundles(packageName);
    if (bundles.length > 0) {
      const latest = bundles[bundles.length - 1];
      checks.push({ name: "Bundle uploaded", status: "pass", detail: `Latest version code: ${latest.versionCode}` });
    } else {
      checks.push({
        name: "Bundle uploaded",
        status: "fail",
        detail: "No AAB bundles found — upload to the internal track first",
        fix_by: "agent",
        tool: "upload_to_google_play",
      });
    }
  } catch (e) {
    checks.push({ name: "Bundle uploaded", status: "unknown", detail: `Could not check: ${e instanceof Error ? e.message : String(e)}` });
  }

  // Check: internal track has a release
  try {
    const tracks = await listTracks(packageName);
    const internal = tracks.find(t => t.track === "internal");
    if (internal?.releases && internal.releases.length > 0) {
      const r = internal.releases[0];
      checks.push({ name: "Internal track release", status: "pass", detail: `${r.name ?? "release"} — ${r.status}` });
    } else {
      checks.push({
        name: "Internal track release",
        status: "fail",
        detail: "No release on internal track — upload with track=internal first",
        fix_by: "agent",
        tool: "upload_to_google_play",
      });
    }
  } catch (e) {
    checks.push({ name: "Internal track release", status: "unknown", detail: `Could not check: ${e instanceof Error ? e.message : String(e)}` });
  }

  // Check: store listing completeness
  try {
    const listing = await getAndroidStoreListing(packageName, language);
    const missing: string[] = [];
    if (!listing.title) missing.push("title");
    if (!listing.shortDescription) missing.push("shortDescription");
    if (!listing.fullDescription) missing.push("fullDescription");
    if (missing.length > 0) {
      checks.push({
        name: `Store listing (${language})`,
        status: "fail",
        detail: `Missing: ${missing.join(", ")}`,
        fix_by: "agent",
        tool: "set_android_store_listing",
      });
    } else {
      checks.push({ name: `Store listing (${language})`, status: "pass", detail: "Title, short description, and full description are set" });
    }
  } catch (e) {
    checks.push({ name: `Store listing (${language})`, status: "unknown", detail: `Could not check: ${e instanceof Error ? e.message : String(e)}` });
  }

  // Static human-required items
  checks.push(
    { name: "Content rating (IARC)", status: "unknown", detail: "Complete the rating questionnaire", fix_by: "human", where: "Play Console → Policy → App content → Content rating" },
    { name: "Data safety form", status: "unknown", detail: "Export CSV from Play Console and submit via set_android_data_safety", fix_by: "human", where: "Play Console → Policy → App content → Data safety" },
    { name: "App access", status: "unknown", detail: "Provide test credentials if app requires login", fix_by: "human", where: "Play Console → Policy → App content → App access" },
    { name: "Closed testing (new accounts)", status: "unknown", detail: "New personal accounts need 20+ testers for 14+ days before production access", fix_by: "human", where: "Play Console → Testing → Closed testing" },
  );

  return checks;
}

export function registerReadinessTools(server: McpServer): void {

  server.registerTool("check_publish_readiness", {
    description:
      "Aggregate publish-readiness checks for iOS or Android into a single pass/fail report. " +
      "API-verifiable checks (valid build, store listing completeness, binary validation) run live. " +
      "Items that have no API (age rating, privacy labels, content policy, legal agreements) are always " +
      "listed as 'human required' so nothing is silently skipped. " +
      "Each item is tagged as 'agent can fix' or 'human required', giving a clear action plan. " +
      "Call this before submit_for_app_store_review (iOS) or promoting to production (Android). " +
      "Use first_publish_ios or first_publish_android prompts for the one-time account/app-record setup.",
    inputSchema: {
      platform: z.enum(["ios", "android"]).describe("Target platform"),
      app_id: z.string().optional().describe("App Store Connect app ID — required for iOS (from list_asc_apps)"),
      version: z.string().optional().describe("App Store version string e.g. '1.2.0' — required for iOS"),
      package_name: z.string().optional().describe("Android package name e.g. com.example.myapp — required for Android"),
      language: z.string().optional().describe("BCP-47 language for listing check, Android only (default: en-US)"),
    },
  }, async ({ platform, app_id, version, package_name, language }) => {
    if (platform === "ios") {
      if (!app_id || !version) {
        return { content: [{ type: "text", text: "app_id and version are required for platform=ios." }], isError: true };
      }
      const checks = await runIosChecks(app_id, version);
      return { content: [{ type: "text", text: renderReport("iOS", `${app_id} v${version}`, checks) }] };
    } else {
      if (!package_name) {
        return { content: [{ type: "text", text: "package_name is required for platform=android." }], isError: true };
      }
      const checks = await runAndroidChecks(package_name, language ?? "en-US");
      return { content: [{ type: "text", text: renderReport("Android", package_name, checks) }] };
    }
  });

}

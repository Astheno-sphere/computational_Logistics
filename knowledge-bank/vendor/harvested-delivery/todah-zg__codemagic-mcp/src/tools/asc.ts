import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { listAscApps, listAscBuilds, listTestFlightGroups, getReviewStatus, getReleaseStatus, uploadToTestFlight, uploadBuildToAsc, submitForAppStoreReview, validateAppSubmission, setVersionMetadata, setExportCompliance, releaseVersion, setPhasedRelease, submitBetaReview, addTestFlightTester, createTestFlightGroup, getIosStoreListing, setIosStoreListing, listIosScreenshotTypes, uploadIosScreenshots } from "../asc.js";

export function registerAscTools(server: McpServer, apiToken: string): void {

  server.registerTool("list_asc_apps", {
    description: "List apps in App Store Connect. Call this first to get the ASC app ID needed by all other App Store Connect tools.",
  }, async () => {
    const apps = await listAscApps();
    const text = apps.map(app => `${app.name} (${app.bundleId}) — ID: ${app.id}`).join("\n");
    return {
      content: [{ type: "text", text: text || "No apps found." }],
    };
  });

  server.registerTool("list_asc_builds", {
    description: "List TestFlight builds for an app in App Store Connect. Find the highest version number, increment by 1, and pass that as BUILD_NUMBER in trigger_build variables before triggering a release build.",
    inputSchema: {
      app_id: z.string().describe("The App Store Connect app ID"),
    },
  }, async ({ app_id }) => {
    const builds = await listAscBuilds(app_id);
    const text = builds.map(b =>
      `v${b.version} — ${b.processingState}${b.expired ? " (expired)" : ""} — uploaded ${b.uploadedDate} (${b.id})`
    ).join("\n");
    return {
      content: [{ type: "text", text: text || "No builds found." }],
    };
  });

  server.registerTool("list_testflight_groups", {
    description: "List TestFlight beta groups for an app. Use a group name from this list in the beta_group parameter of upload_to_testflight to distribute to testers automatically after upload.",
    inputSchema: {
      app_id: z.string().describe("The App Store Connect app ID"),
    },
  }, async ({ app_id }) => {
    const groups = await listTestFlightGroups(app_id);
    const text = groups.map(g =>
      `${g.name} — ${g.isInternalGroup ? "internal" : "external"} (${g.id})`
    ).join("\n");
    return {
      content: [{ type: "text", text: text || "No groups found." }],
    };
  });

  server.registerTool("get_asc_review_status", {
    description: "Get the current App Store review status for an app. Call this after submitting to the App Store to monitor progress and check for blockers.",
    inputSchema: {
      app_id: z.string().describe("The App Store Connect app ID"),
    },
  }, async ({ app_id }) => {
    const status = await getReviewStatus(app_id);
    const lines = [
      `Review state: ${status.reviewState}`,
      `Version: ${status.version?.version ?? "none"} (${status.version?.state ?? "unknown"})`,
      `Next action: ${status.nextAction}`,
    ];
    if (status.blockers.length > 0) {
      lines.push(`Blockers:\n${status.blockers.map(b => `  - ${b}`).join("\n")}`);
    }
    return {
      content: [{ type: "text", text: lines.join("\n") }],
    };
  });

  server.registerTool("get_asc_release_status", {
    description: "Get a full release pipeline status dashboard for an app, including latest build, TestFlight, App Store version, and submission state",
    inputSchema: {
      app_id: z.string().describe("The App Store Connect app ID"),
    },
  }, async ({ app_id }) => {
    const status = await getReleaseStatus(app_id);
    const lines = [
      `${status.app.name} (${status.app.bundleId})`,
      `Health: ${status.summary.health.toUpperCase()}`,
      `Next action: ${status.summary.nextAction}`,
      ``,
      `Latest build: ${status.builds.latest ? `v${status.builds.latest.version} build ${status.builds.latest.buildNumber} — ${status.builds.latest.processingState}` : "none"}`,
      `TestFlight: ${status.testflight ? `${status.testflight.betaReviewState}` : "not submitted"}`,
      `App Store: ${status.appstore ? `v${status.appstore.version} — ${status.appstore.state}` : "none"}`,
      `Submission in flight: ${status.submission.inFlight ? "yes" : "no"}`,
    ];
    if (status.summary.blockers.length > 0) {
      lines.push(`\nBlockers:\n${status.summary.blockers.map(b => `  - ${b}`).join("\n")}`);
    }
    return {
      content: [{ type: "text", text: lines.join("\n") }],
    };
  });

  server.registerTool("validate_app_submission", {
    description:
      "Run a preflight readiness check for an App Store version before submitting for review. " +
      "Checks metadata completeness, build attachment, export compliance, pricing, screenshots, and more. " +
      "Returns an ordered remediation plan — fix the first item, then call again to confirm it is resolved. " +
      "Call this before publish_to_app_store with submit_for_review=true.",
    inputSchema: {
      app_id: z.string().describe("The App Store Connect app ID (from list_asc_apps)"),
      version: z.string().describe("App Store version string e.g. '1.2.3'"),
    },
  }, async ({ app_id, version }) => {
    const result = await validateAppSubmission(app_id, version);
    return {
      content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
    };
  });

  server.registerTool("set_version_metadata", {
    description:
      "Update App Store version localization metadata — What's New text, description, keywords, and more. " +
      "What's New is required for every release before submitting for review. " +
      "Call once per locale — en-US is the required default; add other locales if the app supports them. " +
      "Use validate_app_submission afterward to confirm the update resolved the blocker.",
    annotations: {
      readOnlyHint: false,
      destructiveHint: false,
    },
    inputSchema: {
      app_id: z.string().describe("The App Store Connect app ID (from list_asc_apps)"),
      version: z.string().describe("App Store version string e.g. '1.2.3'"),
      locale: z.string().default("en-US").describe("BCP-47 locale e.g. 'en-US', 'de-DE', 'zh-Hans' (default: en-US)"),
      whats_new: z.string().optional().describe("What's New in this version (required by Apple for every release)"),
      description: z.string().optional().describe("Full app description"),
      keywords: z.string().optional().describe("Comma-separated search keywords"),
      promotional_text: z.string().optional().describe("Promotional text shown above the description"),
      support_url: z.string().optional().describe("Support URL"),
      marketing_url: z.string().optional().describe("Marketing URL"),
    },
  }, async ({ app_id, version, locale, whats_new, description, keywords, promotional_text, support_url, marketing_url }) => {
    const result = await setVersionMetadata(app_id, version, locale, {
      whatsNew: whats_new,
      description,
      keywords,
      promotionalText: promotional_text,
      supportUrl: support_url,
      marketingUrl: marketing_url,
    });
    return {
      content: [{ type: "text", text: `Metadata updated for ${version} (${locale}).\n${JSON.stringify(result, null, 2)}` }],
    };
  });

  server.registerTool("set_export_compliance", {
    description:
      "Set the export compliance declaration for an iOS build. " +
      "Required before App Store submission and for TestFlight external distribution. " +
      "Most apps only use standard HTTPS/TLS — set uses_non_exempt_encryption to false. " +
      "Only set it to true if the app implements custom or proprietary encryption beyond standard protocols. " +
      "Defaults to the latest build for the app; pass build_id to target a specific build.",
    annotations: {
      readOnlyHint: false,
      destructiveHint: false,
    },
    inputSchema: {
      app_id: z.string().describe("The App Store Connect app ID (from list_asc_apps)"),
      uses_non_exempt_encryption: z.boolean().describe("Set to false for apps that only use HTTPS/TLS (most apps). Set to true only for apps with custom proprietary encryption."),
      build_id: z.string().optional().describe("Specific build ID to update — defaults to the latest build"),
    },
  }, async ({ app_id, uses_non_exempt_encryption, build_id }) => {
    const result = await setExportCompliance(app_id, uses_non_exempt_encryption, build_id);
    return {
      content: [{
        type: "text",
        text: `Export compliance set: uses_non_exempt_encryption=${uses_non_exempt_encryption}.\n${JSON.stringify(result, null, 2)}`,
      }],
    };
  });

  server.registerTool("release_version", {
    description:
      "Release an App Store version that has been approved and is waiting in 'Pending Developer Release' state. " +
      "This immediately makes the update available to all users (or starts the phased rollout if one was configured). " +
      "Use set_phased_release with action=create before submission if you want a gradual rollout instead of an instant release.",
    annotations: {
      readOnlyHint: false,
      destructiveHint: true,
    },
    inputSchema: {
      app_id: z.string().describe("The App Store Connect app ID (from list_asc_apps)"),
      version: z.string().describe("App Store version string e.g. '1.2.3'"),
    },
  }, async ({ app_id, version }) => {
    const result = await releaseVersion(app_id, version);
    return {
      content: [{ type: "text", text: `Version ${version} released.\n${JSON.stringify(result, null, 2)}` }],
    };
  });
  
  server.registerTool("set_phased_release", {
    description:
      "Manage a phased rollout for an App Store version. " +
      "Phased rollout gradually releases the update over 7 days: 1% → 2% → 5% → 10% → 20% → 50% → 100%. " +
      "Actions: 'create' — configure phased rollout before submitting for review. " +
      "'pause' — pause an in-progress rollout (use if a critical bug is found after release). " +
      "'resume' — resume a paused rollout. " +
      "'complete' — immediately release to all remaining users.",
    annotations: {
      readOnlyHint: false,
      destructiveHint: false,
    },
    inputSchema: {
      app_id: z.string().describe("The App Store Connect app ID (from list_asc_apps)"),
      version: z.string().describe("App Store version string e.g. '1.2.3'"),
      action: z.enum(["create", "pause", "resume", "complete"]).describe(
        "create: set up phased rollout before submission | pause: halt rollout | resume: continue after pause | complete: release to all users now"
      ),
    },
  }, async ({ app_id, version, action }) => {
    const result = await setPhasedRelease(app_id, version, action);
    const messages: Record<string, string> = {
      create: `Phased rollout configured for version ${version}. It will start automatically after the version is approved and released.`,
      pause: `Phased rollout paused for version ${version}.`,
      resume: `Phased rollout resumed for version ${version}.`,
      complete: `Phased rollout completed — version ${version} is now available to all users.`,
    };
    return {
      content: [{ type: "text", text: `${messages[action]}\n${JSON.stringify(result, null, 2)}` }],
    };
  });

  server.registerTool("submit_beta_review", {
    description:
      "Submit a build for TestFlight beta app review. " +
      "Required before external beta groups can install the build — Apple reviews it once, then all external groups can access it. " +
      "Internal groups (Apple employees / org members) do not require beta review. " +
      "Get the build ID from list_asc_builds.",
    annotations: {
      readOnlyHint: false,
      destructiveHint: false,
    },
    inputSchema: {
      build_id: z.string().describe("The App Store Connect build ID (from list_asc_builds)"),
    },
  }, async ({ build_id }) => {
    const result = await submitBetaReview(build_id);
    return {
      content: [{ type: "text", text: `Build submitted for beta review.\n${JSON.stringify(result, null, 2)}` }],
    };
  });
  
  server.registerTool("add_testflight_tester", {
    description:
      "Add a tester to TestFlight by email address. " +
      "Optionally assign them to a specific beta group — use list_testflight_groups to get group names. " +
      "The tester receives an invitation email from Apple.",
    annotations: {
      readOnlyHint: false,
      destructiveHint: false,
    },
    inputSchema: {
      app_id: z.string().describe("The App Store Connect app ID (from list_asc_apps)"),
      email: z.string().email().describe("Tester email address"),
      group: z.string().optional().describe("Beta group name or ID to add the tester to (from list_testflight_groups)"),
    },
  }, async ({ app_id, email, group }) => {
    const result = await addTestFlightTester(app_id, email, group);
    return {
      content: [{ type: "text", text: `Tester ${email} added.\n${JSON.stringify(result, null, 2)}` }],
    };
  });
  
  server.registerTool("create_testflight_group", {
    description:
      "Create a new TestFlight beta group for an app. " +
      "External groups require beta app review before testers can install builds. " +
      "Internal groups (Apple org members) do not require review — useful for fast internal QA.",
    annotations: {
      readOnlyHint: false,
      destructiveHint: false,
    },
    inputSchema: {
      app_id: z.string().describe("The App Store Connect app ID (from list_asc_apps)"),
      name: z.string().describe("Display name for the group e.g. 'External Beta Testers'"),
      internal: z.boolean().optional().describe("Create an internal group (Apple org members only, no beta review required). Default: false (external group)."),
    },
  }, async ({ app_id, name, internal }) => {
    const result = await createTestFlightGroup(app_id, name, internal ?? false);
    return {
      content: [{ type: "text", text: `Group '${name}' created.\n${JSON.stringify(result, null, 2)}` }],
    };
  });

  server.registerTool("upload_to_testflight", {
    description: "Download an IPA artifact from Codemagic and upload it to TestFlight via App Store Connect. Optionally distribute to a beta group after upload.",
    annotations: {
      readOnlyHint: false,
      destructiveHint: false,
    },
    inputSchema: {
      app_id: z.string().describe("The App Store Connect app ID"),
      ipa_url: z.string().describe("The IPA download URL from a Codemagic build artifact"),
      beta_group: z.string().optional().describe("TestFlight beta group name to distribute to after upload"),
    },
  }, async ({ app_id, ipa_url, beta_group }) => {
    const result = await uploadToTestFlight(app_id, ipa_url, beta_group, apiToken);
    return {
      content: [{ type: "text", text: `Upload complete.\n${result}` }],
    };
  });

  server.registerTool("upload_build_to_asc", {
    description:
      "Download an IPA from a Codemagic artifact URL and upload it to App Store Connect. " +
      "Returns immediately once the upload commits — does NOT wait for Apple's processing pipeline. " +
      "After calling this, poll list_asc_builds until the build's processingState is VALID, " +
      "then call submit_for_app_store_review with the build ID.",
    annotations: { readOnlyHint: false, destructiveHint: false },
    inputSchema: {
      app_id: z.string().describe("The App Store Connect app ID (from list_asc_apps)"),
      ipa_url: z.string().describe("The IPA download URL from a Codemagic build artifact"),
    },
  }, async ({ app_id, ipa_url }) => {
    const build = await uploadBuildToAsc(app_id, ipa_url, apiToken);
    return {
      content: [{
        type: "text",
        text: [
          "IPA uploaded successfully. Apple is now processing the build.",
          `Build ID: ${build.id}`,
          `Build number: ${build.buildNumber}`,
          `Version: ${build.version}`,
          "",
          "Next: poll list_asc_builds until processingState is VALID, then call submit_for_app_store_review.",
        ].join("\n"),
      }],
    };
  });

  server.registerTool("submit_for_app_store_review", {
    description:
      "Attach a processed build to an App Store version and submit it for review. " +
      "The build must have processingState VALID — confirm with list_asc_builds before calling. " +
      "Requires version metadata (What's New) and export compliance to be set first. " +
      "Use validate_app_submission to catch blockers before submitting.",
    annotations: { readOnlyHint: false, destructiveHint: false },
    inputSchema: {
      app_id: z.string().describe("The App Store Connect app ID (from list_asc_apps)"),
      version: z.string().describe("App Store version string e.g. '1.2.3'"),
      build_id: z.string().describe("Build UUID from upload_build_to_asc or list_asc_builds"),
    },
  }, async ({ app_id, version, build_id }) => {
    await submitForAppStoreReview(app_id, version, build_id);
    return {
      content: [{
        type: "text",
        text: "Submitted for App Store review. Track progress with get_asc_review_status.",
      }],
    };
  });

  server.registerTool("get_ios_store_listing", {
    description:
      "Pull the current App Store listing text for all locales of an app version. " +
      "Returns app-info fields (name, subtitle, privacy URLs) and version fields " +
      "(description, keywords, promotional text, support URL, what's new) grouped by locale. " +
      "Use before set_ios_store_listing to review what is currently live.",
    inputSchema: {
      app_id: z.string().describe("The App Store Connect app ID (from list_asc_apps)"),
      version: z.string().describe("App Store version string e.g. '1.2.3'"),
    },
  }, async ({ app_id, version }) => {
    const listing = await getIosStoreListing(app_id, version);
    return {
      content: [{ type: "text", text: JSON.stringify(listing, null, 2) }],
    };
  });

  server.registerTool("set_ios_store_listing", {
    description:
      "Update App Store listing text for a single locale. " +
      "Only the fields you provide are changed — omitted fields are left as-is. " +
      "App-info fields (name, subtitle) apply to all versions of the app. " +
      "Version fields (description, keywords, whatsNew, etc.) apply to the specified version only. " +
      "Changes are staged through the asc CLI and validated before being applied.",
    annotations: { readOnlyHint: false, destructiveHint: false },
    inputSchema: {
      app_id: z.string().describe("The App Store Connect app ID (from list_asc_apps)"),
      version: z.string().describe("App Store version string e.g. '1.2.3'"),
      locale: z.string().default("en-US").describe("BCP-47 locale code e.g. en-US, fr-FR"),
      name: z.string().optional().describe("App name (app-info, max 30 characters)"),
      subtitle: z.string().optional().describe("App subtitle shown below the name (app-info, max 30 characters)"),
      privacy_policy_url: z.string().optional().describe("URL to the app's privacy policy (app-info)"),
      description: z.string().optional().describe("Full app description (version, max 4000 characters)"),
      keywords: z.string().optional().describe("Comma-separated keywords for App Store search (version, max 100 characters)"),
      promotional_text: z.string().optional().describe("Promotional text shown above the description (version, max 170 characters)"),
      marketing_url: z.string().optional().describe("URL to a marketing page for this version (version)"),
      support_url: z.string().optional().describe("URL to the app's support page (version)"),
      whats_new: z.string().optional().describe("What's new text for this version (version, max 4000 characters)"),
    },
  }, async ({ app_id, version, locale, name, subtitle, privacy_policy_url, description, keywords, promotional_text, marketing_url, support_url, whats_new }) => {
    const fields = Object.fromEntries(
      Object.entries({
        name, subtitle, privacyPolicyUrl: privacy_policy_url,
        description, keywords, promotionalText: promotional_text,
        marketingUrl: marketing_url, supportUrl: support_url, whatsNew: whats_new,
      }).filter(([, v]) => v !== undefined)
    );
    if (Object.keys(fields).length === 0) {
      return { content: [{ type: "text", text: "No fields provided — nothing to update." }] };
    }
    await setIosStoreListing(app_id, version, locale, fields);
    const updated = Object.keys(fields).join(", ");
    return {
      content: [{ type: "text", text: `Store listing updated for ${locale}: ${updated}` }],
    };
  });

  server.registerTool("list_ios_screenshot_types", {
    description:
      "List the supported screenshot device types for the App Store and their required pixel dimensions. " +
      "By default returns the two most-required types: IPHONE_65 and IPAD_PRO_3GEN_129. " +
      "Pass all=true to get the full matrix of all supported device types. " +
      "Use the deviceType values returned here as the device_type parameter for upload_ios_screenshots.",
    inputSchema: {
      all: z.boolean().default(false).describe("If true, return all supported device types instead of just the common ones"),
    },
  }, async ({ all }) => {
    const types = await listIosScreenshotTypes(all);
    return {
      content: [{ type: "text", text: JSON.stringify(types, null, 2) }],
    };
  });

  server.registerTool("upload_ios_screenshots", {
    description:
      "Download screenshot images from URLs and upload them to App Store Connect for a specific device type and locale. " +
      "Apple allows up to 10 screenshots per set. Supported formats: PNG (no alpha) and JPEG. Max 10 MB per file. " +
      "Call list_ios_screenshot_types first to get valid device_type values and required dimensions. " +
      "Set replace=true to delete existing screenshots before uploading (recommended when refreshing a set).",
    annotations: { readOnlyHint: false, destructiveHint: false },
    inputSchema: {
      app_id: z.string().describe("The App Store Connect app ID (from list_asc_apps)"),
      version: z.string().describe("App Store version string e.g. '1.2.3'"),
      locale: z.string().default("en-US").describe("BCP-47 locale code e.g. en-US, fr-FR"),
      device_type: z.string().describe("Device type string e.g. IPHONE_65, IPAD_PRO_3GEN_129 (from list_ios_screenshot_types)"),
      screenshot_urls: z.array(z.string()).min(1).max(10).describe("URLs of screenshot images to upload, in display order"),
      replace: z.boolean().default(false).describe("If true, delete all existing screenshots for this device type before uploading"),
    },
  }, async ({ app_id, version, locale, device_type, screenshot_urls, replace }) => {
    const result = await uploadIosScreenshots(app_id, version, locale, device_type, screenshot_urls, replace);
    return {
      content: [{ type: "text", text: `Uploaded ${screenshot_urls.length} screenshot(s) for ${device_type} / ${locale}.\n${JSON.stringify(result, null, 2)}` }],
    };
  });

}
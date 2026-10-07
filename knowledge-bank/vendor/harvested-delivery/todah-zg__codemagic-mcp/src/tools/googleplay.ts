import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { listTracks, listBundles, uploadToGooglePlay, promoteRelease, setRolloutFraction, shareAppInternally, getLatestBuildNumber } from "../googleplay.js";
import { getAndroidStoreListing, setAndroidStoreListing, uploadAndroidScreenshots, setAndroidDataSafety, listGooglePlayReviews, replyToGooglePlayReview } from "../androidpublisher.js";

export function registerGooglePlayTools(server: McpServer, apiToken: string): void {

  server.registerTool("list_google_play_tracks", {
    description: "List Google Play tracks (internal, alpha, beta, production) with current release info and version codes. Find the highest versionCode across all tracks, increment by 1, and pass that as BUILD_NUMBER in trigger_build variables before triggering a release build.",
    inputSchema: {
      package_name: z.string().describe("The Android package name, e.g. com.example.myapp"),
    },
  }, async ({ package_name }) => {
    const tracks = await listTracks(package_name);
    const lines = tracks.map(t => {
      if (!t.releases || t.releases.length === 0) return `${t.track}: no releases`;
      const releases = t.releases.map(r =>
        `  - ${r.name} (${r.status}) — versions: ${r.versionCodes.join(", ")}`
      ).join("\n");
      return `${t.track}:\n${releases}`;
    });
    return {
      content: [{ type: "text", text: lines.join("\n") }],
    };
  });

  server.registerTool("list_google_play_bundles", {
    description: "List all uploaded App Bundles (AAB) for an app on Google Play, with their version codes. Use this to audit what has already been uploaded before triggering a new build.",
    inputSchema: {
      package_name: z.string().describe("The Android package name, e.g. com.example.myapp"),
    },
  }, async ({ package_name }) => {
    const bundles = await listBundles(package_name);
    const text = bundles.map(b => `Version code ${b.versionCode}`).join("\n");
    return {
      content: [{ type: "text", text: text || "No bundles found." }],
    };
  });

  server.registerTool("upload_to_google_play", {
    description: "Download an AAB artifact from Codemagic and publish it to a Google Play track. Use the AAB artifact URL returned by wait_for_build. Start with the internal track — it is safest for first uploads and can be promoted to alpha/beta/production manually in the Play Console.",
    annotations: {
      readOnlyHint: false,
      destructiveHint: false,
    },
    inputSchema: {
      aab_url: z.string().describe("The AAB download URL from a Codemagic build artifact"),
      track: z.enum(["internal", "alpha", "beta", "production"]).describe("The Google Play track to publish to"),
      release_name: z.string().optional().describe("Name of the release. If omitted, generated from the AAB version name."),
      release_notes: z.string().optional().describe("What's new in this release, as plain text"),
      release_notes_language: z.string().optional().describe("BCP-47 language tag for the release notes (default: en-US)"),
      draft: z.boolean().optional().describe("Upload as a draft release instead of publishing immediately"),
    },
  }, async ({ aab_url, track, release_name, release_notes, release_notes_language, draft }) => {
    const result = await uploadToGooglePlay(aab_url, track, release_name, release_notes, release_notes_language, draft, apiToken);
    return {
      content: [{ type: "text", text: `Published to Google Play (${track} track).\n${result}` }],
    };
  });

  server.registerTool("promote_google_play_release", {
    description:
      "Promote a release between Google Play tracks (e.g. internal → alpha → beta → production) without re-uploading. " +
      "Set user_fraction to enable staged rollout on the target track (0.1 = 10% of users). " +
      "To halt an in-progress staged rollout: set source_track=target_track='production' and release_status='halted'. " +
      "To resume a halted rollout: same tracks with release_status='inProgress' and a user_fraction.",
    annotations: {
      readOnlyHint: false,
      destructiveHint: false,
    },
    inputSchema: {
      package_name: z.string().describe("The Android package name e.g. com.example.myapp"),
      source_track: z.enum(["internal", "alpha", "beta", "production"]).describe("Track to promote from"),
      target_track: z.enum(["alpha", "beta", "production"]).describe("Track to promote to"),
      user_fraction: z.number().min(0).max(1).optional().describe("Staged rollout fraction 0.0–1.0 (e.g. 0.1 = 10%). Omit for full rollout."),
      release_status: z.enum(["completed", "inProgress", "halted", "draft"]).optional().describe("Override release status. Default: completed (full rollout) or inProgress (staged)."),
    },
  }, async ({ package_name, source_track, target_track, user_fraction, release_status }) => {
    const result = await promoteRelease(package_name, source_track, target_track, user_fraction, release_status);
    return {
      content: [{ type: "text", text: `Release promoted from ${source_track} to ${target_track}.\n${JSON.stringify(result, null, 2)}` }],
    };
  });

  server.registerTool("set_rollout_fraction", {
    description:
      "Adjust the staged rollout percentage for an existing release on a Google Play track. " +
      "Use this to gradually expand a rollout (e.g. 10% → 25% → 50% → 100%). " +
      "Requires the version code of the release currently in the staged rollout.",
    annotations: {
      readOnlyHint: false,
      destructiveHint: false,
    },
    inputSchema: {
      package_name: z.string().describe("The Android package name"),
      track: z.enum(["alpha", "beta", "production"]).describe("The track with the staged rollout"),
      version_code: z.number().int().describe("Version code of the release to update (from list_google_play_tracks)"),
      rollout_fraction: z.number().min(0).max(1).describe("New rollout fraction 0.0–1.0 (e.g. 0.5 = 50%)"),
    },
  }, async ({ package_name, track, version_code, rollout_fraction }) => {
    const result = await setRolloutFraction(package_name, track, version_code, rollout_fraction);
    return {
      content: [{ type: "text", text: `Rollout fraction set to ${rollout_fraction * 100}% on ${track} track.\n${JSON.stringify(result, null, 2)}` }],
    };
  });

  server.registerTool("share_app_internally", {
    description:
      "Upload an AAB from Codemagic as a Google Play internal app sharing link. " +
      "Returns an install URL that can be shared with testers instantly — no track, no review, no version code ceremony. " +
      "Testers need the internal app sharing feature enabled on their device. " +
      "Ideal for quick QA before promoting to a track.",
    annotations: {
      readOnlyHint: false,
      destructiveHint: false,
    },
    inputSchema: {
      aab_url: z.string().describe("The AAB download URL from a Codemagic build artifact"),
    },
  }, async ({ aab_url }) => {
    const result = await shareAppInternally(aab_url, apiToken);
    return {
      content: [{ type: "text", text: `Internal sharing link created.\n${JSON.stringify(result, null, 2)}` }],
    };
  });

  server.registerTool("get_latest_build_number", {
    description:
      "Get the highest versionCode currently on Google Play across all tracks (or specific tracks). " +
      "Use this before triggering a release build to determine the next BUILD_NUMBER — increment the result by 1.",
    inputSchema: {
      package_name: z.string().describe("The Android package name e.g. com.example.myapp"),
      tracks: z.string().optional().describe("Comma-separated track names to check e.g. 'production,beta'. Defaults to all tracks."),
    },
  }, async ({ package_name, tracks }) => {
    const result = await getLatestBuildNumber(package_name, tracks);
    return {
      content: [{ type: "text", text: `Latest build number: ${JSON.stringify(result, null, 2)}` }],
    };
  });

  server.registerTool("get_android_store_listing", {
    description:
      "Fetch the current Google Play store listing for a specific language. " +
      "Returns title, short description, and full description. " +
      "Use before set_android_store_listing to review existing text.",
    inputSchema: {
      package_name: z.string().describe("The Android package name e.g. com.example.myapp"),
      language: z.string().default("en-US").describe("BCP-47 language tag e.g. en-US, fr-FR"),
    },
  }, async ({ package_name, language }) => {
    const listing = await getAndroidStoreListing(package_name, language);
    return {
      content: [{ type: "text", text: JSON.stringify(listing, null, 2) }],
    };
  });

  server.registerTool("set_android_store_listing", {
    description:
      "Update the Google Play store listing for a specific language. " +
      "Only the fields you provide are updated — omitted fields are left unchanged. " +
      "Changes go live immediately on commit; there is no staging step on Google Play.",
    annotations: {
      readOnlyHint: false,
      destructiveHint: false,
    },
    inputSchema: {
      package_name: z.string().describe("The Android package name e.g. com.example.myapp"),
      language: z.string().default("en-US").describe("BCP-47 language tag e.g. en-US, fr-FR"),
      title: z.string().optional().describe("App title (max 50 characters)"),
      short_description: z.string().optional().describe("Short description shown in search results (max 80 characters)"),
      full_description: z.string().optional().describe("Full description shown on the store listing page (max 4000 characters)"),
    },
  }, async ({ package_name, language, title, short_description, full_description }) => {
    const listing = Object.fromEntries(
      Object.entries({ title, shortDescription: short_description, fullDescription: full_description })
        .filter(([, v]) => v !== undefined)
    );
    if (Object.keys(listing).length === 0) {
      return { content: [{ type: "text", text: "No fields provided — nothing to update." }] };
    }
    await setAndroidStoreListing(package_name, language, listing);
    const updated = Object.keys(listing).join(", ");
    return {
      content: [{ type: "text", text: `Store listing updated for ${language}: ${updated}` }],
    };
  });

  server.registerTool("upload_android_screenshots", {
    description:
      "Download screenshot images from URLs and upload them to Google Play for a specific language and device type. " +
      "Google allows up to 8 screenshots per device type. Supported formats: JPEG and 24-bit PNG (no alpha). Max 8 MB per file. " +
      "Common image types: phoneScreenshots, sevenInchScreenshots, tenInchScreenshots, tvScreenshots, wearScreenshots. " +
      "Set replace=true to delete all existing screenshots of this type before uploading (recommended when refreshing a set). " +
      "All uploads are committed atomically — if any upload fails, no changes go live.",
    annotations: { readOnlyHint: false, destructiveHint: false },
    inputSchema: {
      package_name: z.string().describe("The Android package name e.g. com.example.myapp"),
      language: z.string().default("en-US").describe("BCP-47 language tag e.g. en-US, fr-FR"),
      image_type: z.string().default("phoneScreenshots").describe("Image type: phoneScreenshots, sevenInchScreenshots, tenInchScreenshots, tvScreenshots, wearScreenshots"),
      screenshot_urls: z.array(z.string()).min(1).max(8).describe("URLs of screenshot images to upload, in display order"),
      replace: z.boolean().default(false).describe("If true, delete all existing screenshots of this type before uploading"),
    },
  }, async ({ package_name, language, image_type, screenshot_urls, replace }) => {
    await uploadAndroidScreenshots(package_name, language, image_type, screenshot_urls, replace);
    return {
      content: [{ type: "text", text: `Uploaded ${screenshot_urls.length} screenshot(s) for ${image_type} / ${language}.` }],
    };
  });

  server.registerTool("list_google_play_reviews", {
    description:
      "List recent Google Play user reviews for an app. " +
      "Only reviews that contain text are returned — star-only ratings are excluded by the API. " +
      "Use max_star_rating to focus on negative reviews (e.g. max_star_rating=2 for 1–2 star reviews). " +
      "Each review includes the review ID needed for reply_to_google_play_review. " +
      "Reviews are ordered by last modified date, most recent first.",
    inputSchema: {
      package_name: z.string().describe("The Android package name e.g. com.example.myapp"),
      max_results: z.number().int().min(1).default(50).describe("Maximum number of reviews to return (default 50). Pages of 100 are fetched transparently until the limit is reached."),
      max_star_rating: z.number().int().min(1).max(5).optional().describe("Filter to reviews at or below this star rating — e.g. 2 returns only 1 and 2 star reviews"),
      translation_language: z.string().optional().describe("BCP-47 language code to translate review text into (e.g. en-US). Useful for apps with non-English reviews."),
    },
  }, async ({ package_name, max_results, max_star_rating, translation_language }) => {
    let reviews = await listGooglePlayReviews(package_name, max_results, translation_language);
    if (max_star_rating !== undefined) {
      reviews = reviews.filter(r => r.userComment.starRating <= max_star_rating);
    }
    if (reviews.length === 0) {
      return { content: [{ type: "text", text: "No reviews found matching the filter." }] };
    }
    const stars = (n: number) => "★".repeat(n) + "☆".repeat(5 - n);
    const lines = reviews.flatMap(r => {
      const header = `${stars(r.userComment.starRating)}  ${r.authorName}  —  ${r.userComment.lastModified}`;
      const body   = `  ${r.userComment.text}`;
      const reply  = r.developerComment
        ? `  Developer replied: ${r.developerComment.text}`
        : `  [no developer reply]`;
      const id = `  ID: ${r.reviewId}`;
      return [header, body, reply, id, ""];
    });
    return { content: [{ type: "text", text: lines.join("\n").trimEnd() }] };
  });

  server.registerTool("reply_to_google_play_review", {
    description:
      "Post or update a developer reply to a Google Play user review. " +
      "Replies are limited to 350 characters. " +
      "If the review already has a developer reply, this call replaces it. " +
      "Get the review_id from list_google_play_reviews. " +
      "Write a personal, helpful reply — responding to negative reviews improves store ratings and user trust.",
    annotations: { readOnlyHint: false, destructiveHint: false },
    inputSchema: {
      package_name: z.string().describe("The Android package name e.g. com.example.myapp"),
      review_id: z.string().describe("Review ID from list_google_play_reviews"),
      reply_text: z.string().max(350).describe("Developer reply text — max 350 characters"),
    },
  }, async ({ package_name, review_id, reply_text }) => {
    await replyToGooglePlayReview(package_name, review_id, reply_text);
    return { content: [{ type: "text", text: `Reply posted to review ${review_id}.` }] };
  });

  server.registerTool("set_android_data_safety", {
    description:
      "Submit the data safety declaration for a Google Play app. " +
      "The declaration describes what data the app collects, how it is used, and whether it is shared. " +
      "Accepts the raw CSV exported from Play Console → App content → Data safety → Export CSV. " +
      "Re-upload whenever data practices change (new data type, updated retention policy, etc.). " +
      "Takes effect immediately — there is no staging step and no GET endpoint to retrieve current labels.",
    annotations: { readOnlyHint: false, destructiveHint: false },
    inputSchema: {
      package_name: z.string().describe("The Android package name e.g. com.example.myapp"),
      csv: z.string().describe("Raw CSV string from Play Console data safety export (5 columns: question ID, response ID, TRUE/FALSE value, requirement type, human-readable label)"),
    },
  }, async ({ package_name, csv }) => {
    await setAndroidDataSafety(package_name, csv);
    return {
      content: [{ type: "text", text: "Data safety declaration submitted successfully." }],
    };
  });

}
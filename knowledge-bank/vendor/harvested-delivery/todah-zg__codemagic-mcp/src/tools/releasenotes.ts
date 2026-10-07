import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";

const CHAR_LIMITS = {
  android: 500,
  ios: 4000,
};

// BCP-47: language (2-3 chars), optional script (4 chars), optional region (2 uppercase / 3 digits)
const BCP47 = /^[a-z]{2,3}(-[A-Z][a-z]{3})?(-([A-Z]{2}|\d{3}))?$/;

export function registerReleaseNotesTools(server: McpServer): void {

  server.registerTool("prepare_release_notes", {
    description:
      "Validate localized release notes before submitting to the App Store or Google Play. " +
      "Checks that each locale is a valid BCP-47 code (e.g. en-US, fr-FR, zh-Hans) and that " +
      "text fits within platform char limits (Android: 500, iOS: 4000). " +
      "Pass platform='both' to validate against the stricter Android limit for notes that will go to both stores.",
    inputSchema: {
      notes: z.record(z.string(), z.string()).describe("Map of BCP-47 locale code to release note text, e.g. { 'en-US': 'Bug fixes and performance improvements.' }"),
      platform: z.enum(["ios", "android", "both"]).describe("Target platform — determines which char limit applies. 'both' uses the stricter Android limit of 500."),
    },
  }, async ({ notes, platform }) => {
    const limit = platform === "ios" ? CHAR_LIMITS.ios : CHAR_LIMITS.android;
    const entries = Object.entries(notes);

    if (entries.length === 0) {
      return {
        content: [{ type: "text", text: "Error: no notes provided." }],
        isError: true,
      };
    }

    const results = entries.map(([locale, text]) => {
      const errors: string[] = [];
      if (!BCP47.test(locale)) errors.push(`invalid BCP-47 code`);
      if (text.length > limit) errors.push(`exceeds limit by ${text.length - limit} chars`);
      return { locale, chars: text.length, limit, errors };
    });

    const lines = results.map(r =>
      r.errors.length === 0
        ? `  ${r.locale}: ✓ ${r.chars}/${r.limit} chars`
        : `  ${r.locale}: ✗ ${r.chars}/${r.limit} chars — ${r.errors.join(", ")}`
    );

    const errorCount = results.filter(r => r.errors.length > 0).length;
    const verdict = errorCount === 0
      ? `All ${results.length} locale(s) valid. Ready to submit.`
      : `${errorCount} error(s) — fix before submitting.`;

    const text = [
      `Validation results (platform: ${platform}, limit: ${limit} chars):`,
      "",
      ...lines,
      "",
      verdict,
    ].join("\n");

    return { content: [{ type: "text", text }] };
  });

}
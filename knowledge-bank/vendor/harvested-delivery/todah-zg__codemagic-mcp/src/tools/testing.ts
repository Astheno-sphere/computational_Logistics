import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { getBuild } from "../codemagic.js";
import { parseJUnitXml, type TestResults } from "../testing.js";

/** Heuristic: name ends with .xml AND contains "test", "junit", or "result". */
function isJUnitArtifact(name: string): boolean {
  const lower = name.toLowerCase();
  return lower.endsWith(".xml") && /test|junit|result/.test(lower);
}

function formatResults(results: TestResults): string {
  const lines: string[] = [];

  if (results.totalTests === 0) {
    lines.push("No test cases found in the XML artifact.");
  } else {
    lines.push(
      `${results.totalTests} tests — ` +
      `${results.passed} passed, ${results.failed} failed, ` +
      `${results.errors} errored, ${results.skipped} skipped — ` +
      `${results.totalTime.toFixed(2)}s`
    );
  }

  if (results.failedCases.length > 0) {
    lines.push("", "FAILURES");
    for (const c of results.failedCases) {
      const label = c.classname ? `${c.classname}.${c.name}` : c.name;
      lines.push(`  ✗  ${label}  [${c.status}]`);
      if (c.failureMessage) lines.push(`     ${c.failureMessage}`);
      if (c.failureDetail) lines.push(`     ${c.failureDetail}`);
    }
  }

  if (results.suites.length > 1) {
    lines.push("", "BY SUITE");
    for (const s of results.suites) {
      const ok = s.failures === 0 && s.errors === 0;
      lines.push(
        `  ${ok ? "✓" : "✗"}  ${s.name || "(unnamed)"}: ` +
        `${s.tests} tests, ${s.failures} failed, ${s.errors} errors — ${s.time.toFixed(2)}s`
      );
    }
  }

  return lines.join("\n");
}

function mergeResults(all: TestResults[]): TestResults {
  return {
    totalTests: all.reduce((n, r) => n + r.totalTests, 0),
    passed:     all.reduce((n, r) => n + r.passed, 0),
    failed:     all.reduce((n, r) => n + r.failed, 0),
    errors:     all.reduce((n, r) => n + r.errors, 0),
    skipped:    all.reduce((n, r) => n + r.skipped, 0),
    totalTime:  all.reduce((n, r) => n + r.totalTime, 0),
    suites:     all.flatMap(r => r.suites),
    failedCases: all.flatMap(r => r.failedCases),
  };
}

export function registerTestingTools(server: McpServer, apiToken: string): void {

  server.registerTool("get_test_results", {
    description:
      "Fetch and parse test results from a Codemagic build. " +
      "Searches the build's artifact list for JUnit XML files and returns a structured " +
      "pass/fail/error/skip summary with per-failure details (message + stack trace excerpt). " +
      "Covers Flutter, Android instrumented tests, and iOS (xcresult converted by Codemagic's CLI tools). " +
      "Pass artifact_url directly if you already have it from wait_for_build — skips the artifact search. " +
      "The build must be in a terminal state (finished or failed) for artifacts to be available. " +
      "Requires the codemagic.yaml workflow to include a test_report glob pointing at the JUnit XML output.",
    inputSchema: {
      build_id: z.string().describe("Codemagic build ID"),
      artifact_url: z.string().optional().describe(
        "Direct URL to a JUnit XML artifact — if provided, skips artifact search. " +
        "Use the short_lived_download_url from get_build or wait_for_build."
      ),
    },
  }, async ({ build_id, artifact_url }) => {

    let xmlUrls: string[];

    if (artifact_url) {
      xmlUrls = [artifact_url];
    } else {
      const build = await getBuild(apiToken, build_id);

      if (build.status !== "finished" && build.status !== "failed") {
        return {
          content: [{
            type: "text",
            text: `Build is ${build.status} — artifacts are only available after the build finishes. ` +
              "Call wait_for_build until status is finished or failed, then retry.",
          }],
        };
      }

      const testArtifacts = build.artifacts.filter(a => isJUnitArtifact(a.name));

      if (testArtifacts.length === 0) {
        // Fallback: show all XML files so the user can identify the right one
        const allXml = build.artifacts.filter(a => a.name.toLowerCase().endsWith(".xml"));
        const artifactList = build.artifacts.map(a => `  ${a.name} (${a.type})`).join("\n");

        if (allXml.length > 0) {
          // Found XML files but none matched the test heuristic — try them anyway
          xmlUrls = allXml.map(a => a.url);
        } else {
          return {
            content: [{
              type: "text",
              text: [
                "No JUnit XML test report artifacts found for this build.",
                "",
                "To enable test result reporting, add a test_report field to your codemagic.yaml workflow:",
                "  test_report: build/app/outputs/androidTest-results/**/*.xml   # Android",
                "  test_report: test-results.xml                                  # Flutter",
                "  test_report: build/reports/tests/**/*.xml                      # JVM / Gradle",
                "",
                `Build artifacts (${build.artifacts.length} total):`,
                artifactList || "  (none)",
              ].join("\n"),
            }],
          };
        }
      } else {
        xmlUrls = testArtifacts.map(a => a.url);
      }
    }

    // Download and parse each XML file
    const parsed: TestResults[] = [];
    const parseErrors: string[] = [];

    for (const url of xmlUrls) {
      let response: Response;
      try {
        response = await fetch(url, { signal: AbortSignal.timeout(30_000) });
      } catch (e) {
        parseErrors.push(`Download failed: ${e instanceof Error ? e.message : String(e)}`);
        continue;
      }
      if (!response.ok) {
        parseErrors.push(`HTTP ${response.status} downloading artifact`);
        continue;
      }
      const xml = await response.text();
      try {
        parsed.push(parseJUnitXml(xml));
      } catch (e) {
        parseErrors.push(`XML parse error: ${e instanceof Error ? e.message : String(e)}`);
      }
    }

    if (parsed.length === 0) {
      return {
        content: [{
          type: "text",
          text: `Could not read test results.\n${parseErrors.join("\n")}`,
        }],
      };
    }

    const merged = mergeResults(parsed);
    const output = [
      formatResults(merged),
      ...(parseErrors.length > 0 ? ["", `Warnings: ${parseErrors.join("; ")}`] : []),
    ].join("\n");

    return { content: [{ type: "text", text: output }] };
  });

}

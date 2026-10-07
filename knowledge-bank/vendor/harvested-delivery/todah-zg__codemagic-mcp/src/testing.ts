/**
 * Lightweight JUnit XML parser — no external dependencies.
 *
 * Covers the standard format emitted by:
 *   - Flutter test runner (via Codemagic's machine-format conversion)
 *   - Android instrumentation tests (build/app/outputs/androidTest-results)
 *   - iOS xcresult bundles (via codemagic-cli-tools xcode-project junit-test-results)
 *   - Any JUnit-compatible runner
 *
 * The format is shallow (testsuites → testsuite → testcase) so a full XML parser
 * is not needed. Two helpers — attr() and extractBlocks() — cover the whole spec.
 */

export interface TestCase {
  name: string;
  classname: string;
  time: number;
  status: "passed" | "failed" | "error" | "skipped";
  failureMessage?: string;
  failureType?: string;
  /** First 500 chars of the failure body (stack trace / diff). */
  failureDetail?: string;
}

export interface TestSuite {
  name: string;
  tests: number;
  failures: number;
  errors: number;
  skipped: number;
  time: number;
  cases: TestCase[];
}

export interface TestResults {
  totalTests: number;
  passed: number;
  /** Assertion failures — test ran but expectation was wrong. */
  failed: number;
  /** Hard errors — test crashed, timeout, setup failure. */
  errors: number;
  skipped: number;
  totalTime: number;
  suites: TestSuite[];
  /** All failed + errored cases flattened — the first thing an agent should read. */
  failedCases: TestCase[];
}

// ---------------------------------------------------------------------------
// Parsing helpers
// ---------------------------------------------------------------------------

/** Extract a single XML attribute value from a tag opening string. */
function attr(tag: string, name: string): string {
  for (const q of ['"', "'"]) {
    const needle = `${name}=${q}`;
    const i = tag.indexOf(needle);
    if (i !== -1) {
      const start = i + needle.length;
      const end = tag.indexOf(q, start);
      if (end !== -1) return tag.slice(start, end);
    }
  }
  return "";
}

function numAttr(tag: string, name: string): number {
  const n = parseFloat(attr(tag, name));
  return isNaN(n) ? 0 : n;
}

/**
 * Find all occurrences of <tagName …>…</tagName> (or self-closing <tagName … />)
 * in xml. Does NOT recurse through nested same-named elements — safe for JUnit
 * because testcase elements never nest inside each other.
 */
function extractBlocks(xml: string, tagName: string): string[] {
  const results: string[] = [];
  const open = `<${tagName}`;
  const close = `</${tagName}>`;
  let pos = 0;

  while (pos < xml.length) {
    const start = xml.indexOf(open, pos);
    if (start === -1) break;

    // Reject <tagNameExtra> — character after the tag name must be whitespace, / or >
    const charAfter = xml[start + open.length];
    if (charAfter !== " " && charAfter !== "\t" && charAfter !== "\n" &&
        charAfter !== "\r" && charAfter !== "/" && charAfter !== ">") {
      pos = start + 1;
      continue;
    }

    const tagEnd = xml.indexOf(">", start);
    if (tagEnd === -1) break;

    if (xml[tagEnd - 1] === "/") {
      // Self-closing: <testcase … />
      results.push(xml.slice(start, tagEnd + 1));
      pos = tagEnd + 1;
    } else {
      const closePos = xml.indexOf(close, tagEnd);
      if (closePos === -1) { pos = tagEnd + 1; continue; }
      results.push(xml.slice(start, closePos + close.length));
      pos = closePos + close.length;
    }
  }

  return results;
}

// ---------------------------------------------------------------------------
// Case / suite parsers
// ---------------------------------------------------------------------------

function parseTestCase(block: string): TestCase {
  const tagEnd = block.indexOf(">");
  const openTag = block.slice(0, tagEnd + 1);
  const name = attr(openTag, "name");
  const classname = attr(openTag, "classname");
  const time = numAttr(openTag, "time");
  const lower = block.toLowerCase();

  if (lower.includes("<skipped")) {
    return { name, classname, time, status: "skipped" };
  }

  for (const kind of ["failure", "error"] as const) {
    if (lower.includes(`<${kind}`)) {
      const inner = extractBlocks(block, kind)[0] ?? "";
      const innerTagEnd = inner.indexOf(">");
      const innerTag = inner.slice(0, innerTagEnd + 1);
      const bodyStart = innerTagEnd + 1;
      const bodyEnd = inner.lastIndexOf(`</${kind}>`);
      const body = bodyEnd > bodyStart ? inner.slice(bodyStart, bodyEnd).trim() : "";
      return {
        name, classname, time,
        status: kind === "failure" ? "failed" : "error",
        failureMessage: attr(innerTag, "message"),
        failureType: attr(innerTag, "type"),
        failureDetail: body.slice(0, 500),
      };
    }
  }

  return { name, classname, time, status: "passed" };
}

function parseTestSuite(block: string): TestSuite {
  const tagEnd = block.indexOf(">");
  const openTag = block.slice(0, tagEnd + 1);
  const cases = extractBlocks(block, "testcase").map(parseTestCase);

  // Prefer attribute counts; fall back to recomputing from cases
  // (some runners omit or misreport these attributes).
  const attrFailures = numAttr(openTag, "failures");
  const attrErrors = numAttr(openTag, "errors");
  const attrSkipped = numAttr(openTag, "skipped");
  const computedFailures = cases.filter(c => c.status === "failed").length;
  const computedErrors = cases.filter(c => c.status === "error").length;
  const computedSkipped = cases.filter(c => c.status === "skipped").length;

  return {
    name: attr(openTag, "name"),
    tests: numAttr(openTag, "tests") || cases.length,
    failures: attrFailures || computedFailures,
    errors: attrErrors || computedErrors,
    skipped: attrSkipped || computedSkipped,
    time: numAttr(openTag, "time"),
    cases,
  };
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Parse a JUnit XML string into structured test result data.
 * Handles both <testsuites> wrapper and bare <testsuite> root elements.
 */
export function parseJUnitXml(xml: string): TestResults {
  const suites = extractBlocks(xml, "testsuite").map(parseTestSuite);

  const totalTests = suites.reduce((n, s) => n + s.tests, 0);
  const failed = suites.reduce((n, s) => n + s.failures, 0);
  const errors = suites.reduce((n, s) => n + s.errors, 0);
  const skipped = suites.reduce((n, s) => n + s.skipped, 0);
  const passed = totalTests - failed - errors - skipped;
  const totalTime = suites.reduce((n, s) => n + s.time, 0);
  const failedCases = suites.flatMap(s => s.cases).filter(c => c.status === "failed" || c.status === "error");

  return { totalTests, passed, failed, errors, skipped, totalTime, suites, failedCases };
}

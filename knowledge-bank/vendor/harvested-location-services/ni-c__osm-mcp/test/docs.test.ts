import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { afterEach, describe, expect, it, vi } from 'vitest';

import { ALL_TOOLS, ESSENTIAL_TOOLS } from '../src/tools/catalogue.js';

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

/**
 * The tool reference is written by hand, so this is what stops it drifting from
 * the catalogue.
 *
 * The alternative — generating the page — buys the same guarantee at the cost of
 * a generator nobody reads and prose nobody can edit, and the prose is most of
 * the value: what the endpoint behind a tool does that its name does not
 * promise, which parameter combination it silently resolves its own way, which
 * default would be dangerous. A test that fails by name when a tool is added,
 * renamed, moved into the preset or loses its confirmation guard is the cheaper
 * half of it, and it fails in the same run as everything else.
 */
function read(relative: string): string {
  return readFileSync(
    fileURLToPath(new URL(`../${relative}`, import.meta.url)),
    'utf8'
  );
}

const reference = read('docs/reference/tools.md');

/**
 * Markers and the kind word some servers put after the name. Both decorate the
 * heading; neither is part of it.
 */
const MARKERS =
  /[\u{1F464}\u{1F511}\u{1F194}\u2605]|<Badge[^>]*\/?>|<\/Badge>|\b(?:read-only|read|write|destructive)\b/gu;

/**
 * The tools a heading names — none, if the heading is prose.
 *
 * The family writes this page in more than one shape: `### \`tool\``, plain
 * `## tool`, and one heading for a pair (`### \`enable_x\` / \`disable_x\``).
 * What they have in common is that a tool heading carries *nothing but* the
 * names, so `## The \`essential\` preset` drops out on its own rather than
 * being read as a tool called `essential`.
 */
function headingTools(heading: string): string[] {
  const clean = heading.replace(MARKERS, '').trim();
  const spans = [...clean.matchAll(/`([a-z][a-z0-9_]*)`/g)].map(
    (match) => match[1] as string
  );
  if (spans.length > 0) {
    const rest = clean.replace(/`[a-z][a-z0-9_]*`/g, '').replace(/[\s/,]/g, '');
    return rest === '' ? spans : [];
  }
  const bare = clean.split('/').map((part) => part.trim());
  return bare.every((part) => /^[a-z][a-z0-9_]*$/.test(part)) ? bare : [];
}

/**
 * Tools listed in a table rather than in sections.
 *
 * Keyed on a first column headed `Tool`, which is what separates the tool table
 * from the parameter tables further down — those are headed `Parameter`.
 */
function tableTools(markdown: string): string[] {
  const names: string[] = [];
  let inToolTable = false;
  for (const line of markdown.split('\n')) {
    if (/^\|\s*Tool\s*\|/.test(line)) {
      inToolTable = true;
      continue;
    }
    if (!line.startsWith('|')) {
      inToolTable = false;
      continue;
    }
    if (!inToolTable || /^\|[\s|:-]+\|$/.test(line)) continue;
    const match = /`([a-z][a-z0-9_]*)`/.exec(line.split('|')[1] ?? '');
    if (match) names.push(match[1] as string);
  }
  return names;
}

/**
 * Every tool the page documents, in the order it lists them.
 *
 * De-duplicated: several servers list their tools in an overview table *and*
 * give each one a section, and a tool named twice is documented once.
 */
function documentedTools(markdown: string): string[] {
  const headings = [...markdown.matchAll(/^#{2,4} +(.+)$/gm)].flatMap(
    ([, heading]) => headingTools(heading as string)
  );
  return [...new Set([...headings, ...tableTools(markdown)])];
}

/** What the page says about each tool: its section, or its row in the table. */
function bodyByTool(markdown: string): Map<string, string> {
  const bodies = new Map<string, string>();
  const headings = [...markdown.matchAll(/^#{2,4} +(.+)$/gm)];
  for (const [index, match] of headings.entries()) {
    // From the heading itself, not after it: several servers put the markers on
    // the heading line (`### \`delete_link\` 👤`) rather than in the body.
    const start = match.index as number;
    const end =
      (headings[index + 1]?.index as number | undefined) ?? markdown.length;
    const body = markdown.slice(start, end);
    for (const name of headingTools(match[1] as string)) {
      bodies.set(name, (bodies.get(name) ?? '') + body);
    }
  }
  // A marker may sit in the overview row rather than in the section, so the row
  // counts as part of what the page says about that tool.
  const fromTable = new Set(tableTools(markdown));
  for (const line of markdown.split('\n')) {
    if (!line.startsWith('|')) continue;
    const match = /`([a-z][a-z0-9_]*)`/.exec(line.split('|')[1] ?? '');
    if (match && fromTable.has(match[1] as string)) {
      const name = match[1] as string;
      bodies.set(name, (bodies.get(name) ?? '') + line);
    }
  }
  return bodies;
}

function marked(markdown: string, marker: RegExp): string[] {
  return [...bodyByTool(markdown)]
    .filter(([, body]) => marker.test(body))
    .map(([name]) => name);
}

/**
 * The confirmation-marker check is absent here on purpose: it needs a client,
 * and this repository has no importable one — its `connect` lives inside
 * another test file, where importing it would re-register that file's suites.
 * When a `test/harness.ts` appears, the check from the rest of the family
 * belongs back in.
 */

describe('the tool reference', () => {
  it('documents every tool and no tool that does not exist', () => {
    expect(documentedTools(reference).toSorted()).toEqual(
      [...ALL_TOOLS].toSorted()
    );
  });

  it('marks exactly the essential preset', () => {
    expect(marked(reference, /\*\*essential\*\*/).toSorted()).toEqual(
      [...ESSENTIAL_TOOLS].toSorted()
    );
  });
});

describe('the fixed cross-document anchors', () => {
  // These headings are linked from several places and are spelled identically in
  // every server of this family, so a rename here quietly breaks links there.
  it('keeps the README anchor for the tool filter', () => {
    expect(read('README.md')).toContain('### Choosing which tools load');
    expect(read('README.md')).toContain('(#choosing-which-tools-load)');
  });

  it('keeps the docs anchor for the tool filter', () => {
    expect(read('docs/guide/configuration.md')).toContain(
      '## Choosing the tools that load'
    );
    // faq.md links it in all nineteen servers. environment.md does so in three,
    // which makes it a good idea rather than the convention — asserting it here
    // would fail sixteen repositories over a link nobody agreed on.
    expect(read('docs/guide/faq.md')).toContain(
      '#choosing-the-tools-that-load'
    );
  });

  it('keeps the changelog include by region, never by line range', () => {
    // A line range depends on how long the file's header happens to be and fails
    // silently when it grows — the newest release simply stops appearing.
    expect(read('docs/reference/changelog.md')).toContain(
      '<!--@include: ../../CHANGELOG.md#changelog-->'
    );
    const changelog = read('CHANGELOG.md');
    expect(changelog).toContain('<!-- #region changelog -->');
    expect(changelog.trimEnd().endsWith('<!-- #endregion changelog -->')).toBe(
      true
    );
  });
});

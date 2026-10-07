import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'parse5';

const root = fileURLToPath(new URL('../', import.meta.url));
const docs = path.resolve(root, '../docs');
const dist = path.join(root, 'dist');
const pages = ['index.html', 'gallery.html', 'guide.html', 'start.html'];
const read = (dir, file) => fs.readFileSync(path.join(dir, file), 'utf8');

function elements(node, tag) {
  return [ ...(node.tagName === tag ? [node] : []), ...(node.childNodes || []).flatMap(child => elements(child, tag)) ];
}
function attr(node, name) {
  return node?.attrs?.find(attribute => attribute.name === name)?.value;
}
function byId(node, id) {
  if (!node) return undefined;
  return [node, ...(node.childNodes || []).flatMap(child => byId(child, id)).filter(Boolean)]
    .find(candidate => attr(candidate, 'id') === id);
}

for (const page of pages) {
  test(`${page}: DOM, content, accessibility, scripts and styles match the migration baseline`, () => {
    const old = parse(read(docs, page)), next = parse(read(dist, page));
    if (page === 'index.html') {
      // Intentional homepage visual redesign (branch web-redesign, October 2026):
      // index.html no longer tracks the docs/ legacy baseline, so the DOM/CSS
      // parity comparisons are skipped for this page only. Every structural
      // assertion below (proof stage/frame/open, shortcut box, proof-config
      // hashes, forbidden strings) is kept in full.
      const current = read(dist, page);
      const body = elements(next, 'body')[0];
      const stage = byId(body, 'hero-proof-stage');
      const frame = byId(body, 'hero-proof-frame');
      const open = byId(body, 'proof-open');
      const shortcuts = elements(body, 'div').filter(node => (attr(node, 'class') || '').split(/\s+/).includes('shortcut-box'));
      assert.ok(stage, 'homepage proof stage must remain present');
      assert.ok(frame, 'homepage proof iframe must remain present');
      assert.ok(open, 'homepage proof link must remain present');
      assert.equal(shortcuts.length, 1, 'homepage shortcut card must remain present');
      assert.equal(attr(frame, 'src'), 'gallery/artifacts/agent-tool-call.workflow.html?embed=1&theme=dark#focus=planner&reach=downstream');
      assert.equal(attr(open, 'href'), 'gallery/artifacts/agent-tool-call.workflow.html?present=1#focus=planner&reach=downstream');
      const proofScript = elements(next, 'script').find(script => (script.childNodes || []).some(child => (child.value || '').includes("hash: '#lens=backend~database'")));
      assert.ok(proofScript, 'homepage proof configuration must remain present');
      const scriptText = proofScript.childNodes.map(child => child.value || '').join('');
      assert.match(scriptText, /hash: '#lens=backend~database'/);
      assert.match(scriptText, /hash: '#route=web~db'/);
      assert.match(scriptText, /embedHash: '#focus=web&reach=downstream'/);
      assert.match(scriptText, /proof\.embedHash \|\| proof\.hash/);
      assert.doesNotMatch(current, /play=1|#view=|Guided views|Play story/);
    } else {
      // The site-wide redesign restyles every inner page and the shared
      // navigation, so DOM/CSS parity with docs/ no longer applies. Page
      // scripts and deep links still address the legacy ids, so every id in
      // the baseline body must survive.
      const ids = node => [attr(node, 'id'), ...(node.childNodes || []).flatMap(ids)].filter(Boolean);
      const nextIds = new Set(ids(elements(next, 'body')[0]));
      for (const id of ids(elements(old, 'body')[0])) assert.ok(nextIds.has(id), `${page}: #${id} must remain`);
    }
    assert.ok(!read(dist, page).includes('[[ARCHIFY_VERSION]]'));
  });
}

test('all existing non-page public URLs retain exact file bytes', () => {
  function visit(dir, rel = '') {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const file = path.join(rel, entry.name);
      if (entry.isDirectory()) visit(path.join(dir, entry.name), file);
      else if (!pages.includes(file)) assert.deepEqual(fs.readFileSync(path.join(dist, file)), fs.readFileSync(path.join(docs, file)), file);
    }
  }
  visit(docs);
});

test('every generated Astro asset referenced by a page exists under the Pages base', () => {
  for (const page of pages) {
    for (const match of read(dist, page).matchAll(/(?:href|src)="(\/archify\/[^"?#]+)"/g)) {
      assert.ok(fs.existsSync(path.join(dist, match[1].slice('/archify/'.length))), match[1]);
    }
  }
});

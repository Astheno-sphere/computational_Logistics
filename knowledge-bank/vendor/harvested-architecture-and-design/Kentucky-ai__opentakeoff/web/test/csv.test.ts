// Shared CSV cell escaping (csv.js): the formula-injection guard is
// string-only (typeof before coercion — numbers like the -12.5 deduct cell
// must never grow an apostrophe), the `'` prefix lands before the quote test,
// and \r joins the quote triggers. Exact-equality assertions throughout —
// includes() can't catch a type-blind guard.
import { test } from "node:test";
import assert from "node:assert/strict";
import { csvEsc } from "../src/lib/csv.js";
import { conditionTotals, totalsToCsv } from "../src/lib/totals.js";

test("csvEsc: numbers pass through untouched — the formula guard is string-only", () => {
  assert.equal(csvEsc(-12.5), "-12.5");   // a negative deduct cell, NOT '-12.5
  assert.equal(csvEsc(0), "0");
  assert.equal(csvEsc(null), "");
  assert.equal(csvEsc(undefined), "");
});

test("csvEsc: strings starting = + - @ or tab get a leading apostrophe", () => {
  assert.equal(csvEsc("=SUM(A1)"), "'=SUM(A1)");
  assert.equal(csvEsc("+1234"), "'+1234");
  assert.equal(csvEsc("-cmd"), "'-cmd");
  assert.equal(csvEsc("@import"), "'@import");
  assert.equal(csvEsc("\ttabbed"), "'\ttabbed");
  assert.equal(csvEsc("plain text"), "plain text");
});

test("csvEsc: the prefix applies before the quote test — the whole prefixed cell quotes", () => {
  assert.equal(csvEsc("=1,2"), "\"'=1,2\"");
});

test("csvEsc: \\r triggers quoting like \\n; embedded quotes double", () => {
  assert.equal(csvEsc("a\rb"), '"a\rb"');
  assert.equal(csvEsc("a\nb"), '"a\nb"');
  assert.equal(csvEsc('say "hi"'), '"say ""hi"""');
});

test("a formula-shaped finish tag exports inert end-to-end through totalsToCsv", () => {
  const conds = [{ id: "c", finish_tag: "=SUM(A1)" }];
  const shapes = [{ condition_id: "c", measure_role: "floor_area", computed: { area_sf: 10 } }];
  const rows = conditionTotals(conds, shapes);
  const line = totalsToCsv(rows).split("\n")[1];   // first data row (no title line)
  assert.ok(line.startsWith("'=SUM(A1),"), line);
});

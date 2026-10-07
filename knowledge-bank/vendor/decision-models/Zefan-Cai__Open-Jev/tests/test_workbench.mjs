import test from 'node:test';
import assert from 'node:assert/strict';
import {parseCSV, parseCategories, makeRequest, readAnswer, resultsCSV, presets} from '../examples/workbench/logic.mjs';

test('CSV preserves quoted commas, newlines, quotes, BOM and empty text rows', () => {
  assert.deepEqual(parseCSV('\uFEFFid,text\r\n1,"Hello, world"\r\n2,"line one\nline ""two"""\r\n3,\r\n'), {
    headers: ['id', 'text'], rows: [['1', 'Hello, world'], ['2', 'line one\nline "two"'], ['3', '']],
  });
});
test('CSV fails visibly for ambiguous input and too many rows', () => {
  for (const source of ['text,text\na,b', ',text\na,b', 'text\n"unterminated', 'text\n"a"x', 'a,b\n1', 'text\na"b']) {
    assert.throws(() => parseCSV(source));
  }
  assert.throws(() => parseCSV('text\n' + 'a\n'.repeat(201)));
  assert.equal(parseCSV('text\n' + 'a\n'.repeat(200)).rows.length, 200);
});
test('Category names are explicit, distinct, and prototype-safe', () => {
  const categories = parseCategories('__proto__: normal category\nOther：anything else');
  assert.equal(Object.getPrototypeOf(categories), Object.prototype);
  assert.equal(Object.hasOwn(categories, '__proto__'), true);
  assert.equal(JSON.parse(JSON.stringify(categories)).__proto__, 'normal category');
  assert.throws(() => parseCategories('a\n a: duplicate'));
  assert.throws(() => parseCategories(': unnamed\nOther'));
  assert.throws(() => parseCategories('a'));
  Object.values(presets).forEach(preset => assert.ok(makeRequest(preset.text, preset.instructions, parseCategories(preset.categories))));
});
test('Responses must match the exact requested categories and normalized finite probabilities', () => {
  const categories = {A: 'one', B: 'two'};
  const response = {answers: {category: {type: 'choice', choice: 'A', probabilities: {A: .8, B: .2}, confidence: .6}}, model: 'test'};
  assert.equal(readAnswer(response, categories).probability, .8);
  for (const update of [{choice: 'C'}, {choice: 'B'}, {probabilities: {A: .8, C: .2}}, {probabilities: {A: .8, B: .3}}, {probabilities: {A: NaN, B: .2}}, {probabilities: {A: '0.8', B: .2}}, {type: 'score'}]) {
    assert.throws(() => readAnswer({answers: {category: {...response.answers.category, ...update}}}, categories));
  }
  assert.throws(() => readAnswer({answers: {category: response.answers.category, stale: {}}}, categories));
});
test('Export preserves failed and unprocessed rows and neutralizes spreadsheet formulas', () => {
  const rows = [{index: 1, text: ' =HYPERLINK("bad")', label: '+command', status: 'complete', probability: .8, probabilities: {A: .8, B: .2}},
    {index: 2, text: '', status: 'error', error: 'empty'}, {index: 3, text: 'hello\nworld', status: 'stopped'}];
  const parsed = parseCSV(resultsCSV(rows));
  assert.equal(parsed.rows.length, 3);
  assert.equal(parsed.rows[0][1], "' =HYPERLINK(\"bad\")");
  assert.equal(parsed.rows[0][2], "'+command");
  assert.equal(parsed.rows[1][4], 'error');
  assert.equal(parsed.rows[2][4], 'stopped');
  assert.equal(parsed.rows[2][1], 'hello\nworld');
});
test('CSV export retains every original column without colliding with result columns', () => {
  const exported = resultsCSV([{index: 1, text: 'hello', original: ['id-7', 'hello', 'original'], status: 'complete', label: 'A', probability: .8}], ['id', 'text', 'open_jev_status']);
  const parsed = parseCSV(exported);
  assert.deepEqual(parsed.rows[0].slice(0, 3), ['id-7', 'hello', 'original']);
  assert.equal(new Set(parsed.headers).size, parsed.headers.length);
  assert.equal(parsed.headers[6], 'open_jev_status_result');
});

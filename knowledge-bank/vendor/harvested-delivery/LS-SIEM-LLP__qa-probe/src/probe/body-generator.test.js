'use strict';

const { test, describe } = require('node:test');
const assert = require('node:assert/strict');

const { generateBody, resolvePostBodyMode } = require('./body-generator');

const schema = {
  type: 'object',
  required: ['email', 'age'],
  properties: {
    email: { type: 'string' },
    age: { type: 'number' },
    display_name: { type: 'string' },
  },
};

describe('body generator', () => {
  test('minimal strategy emits required fields with type defaults', () => {
    assert.deepEqual(generateBody({ path: '/users' }, schema, 'minimal'), { email: '', age: 0 });
  });

  test('realistic strategy emits non-empty values for recognized fields', () => {
    const body = generateBody({ path: '/users' }, schema, 'realistic');
    assert.match(body.email, /@/);
    assert.equal(typeof body.age, 'number');
  });

  test('example strategy uses schema examples before minimal fallback', () => {
    assert.deepEqual(
      generateBody({ path: '/users' }, { example: { email: 'a@example.com', age: 42 } }, 'example'),
      { email: 'a@example.com', age: 42 },
    );
  });

  test('empty strategy remains available', () => {
    assert.equal(generateBody({ path: '/users' }, schema, 'empty'), undefined);
  });

  test('per-route overrides win over global postBodyMode', () => {
    const mode = resolvePostBodyMode(
      { path: '/api/admin/users' },
      { probe: { postBodyMode: 'minimal', postBodyOverrides: { '/api/admin/*': 'empty' } } },
    );
    assert.equal(mode, 'empty');
  });
});

// Deterministic token accounting for the repair-rounds benchmark.
// Dependency-free lexical estimate: word/number runs, individual punctuation,
// and whitespace runs. Not a model tokenizer; it is a stable comparison unit.

import fs from 'node:fs';
import path from 'node:path';

export function estimateTokens(text) {
  const matches = String(text).match(/[\p{L}\p{N}_]+|[^\s\p{L}\p{N}_]|\s+/gu);
  return matches ? matches.length : 0;
}

// Required reading per SKILL.md step 2 and the Type router:
// every type reads SKILL.md, authoring defaults, its schema, and its example;
// sequence/dataflow/lifecycle additionally read the common schema.
// On failure the agent reads the delivery contract; measured field or
// geometry failures also pull in the authoring contract.
const COMMON_READS = ['SKILL.md', 'references/authoring-defaults.md'];
const MODE_SCHEMA = (type) => `schemas/${type === 'dataflow' ? 'dataflow' : type}.schema.json`;
const MODE_EXAMPLE = {
  architecture: 'examples/web-app.architecture.json',
  workflow: 'examples/agent-tool-call.workflow.json',
  sequence: 'examples/cache-miss-request.sequence.json',
  dataflow: 'examples/product-analytics.dataflow.json',
  lifecycle: 'examples/deployment-release.lifecycle.json',
};
const NEEDS_COMMON_SCHEMA = new Set(['sequence', 'dataflow', 'lifecycle']);
const FAILURE_READS = ['references/delivery-contract.md', 'references/authoring-contract.md'];

export function initialReadingPaths(type) {
  const paths = [...COMMON_READS, MODE_SCHEMA(type), MODE_EXAMPLE[type]];
  if (NEEDS_COMMON_SCHEMA.has(type)) paths.splice(2, 0, 'schemas/common.schema.json');
  return paths;
}

export function failureReadingPaths() {
  return [...FAILURE_READS];
}

export function measureFiles(skillRoot, relativePaths) {
  const files = [];
  let bytes = 0;
  let tokens = 0;
  for (const relative of relativePaths) {
    const file = path.join(skillRoot, relative);
    const source = fs.readFileSync(file, 'utf8');
    const entry = { path: relative, bytes: Buffer.byteLength(source), tokens: estimateTokens(source) };
    bytes += entry.bytes;
    tokens += entry.tokens;
    files.push(entry);
  }
  return { files, bytes, tokens };
}

'use strict';

const fs = require('fs');
const path = require('path');
const { parse } = require('@babel/parser');
const traverse = require('@babel/traverse').default;
const { makeParseWarning } = require('./parse-cache');

const PARSE_OPTS = {
  sourceType: 'module',
  plugins: [
    'typescript',
    'jsx',
    'decorators-legacy',
    'classProperties',
    'optionalChaining',
    'nullishCoalescingOperator',
    'dynamicImport',
  ],
  errorRecovery: true,
};

const EXTENSIONS = ['', '.tsx', '.ts', '.jsx', '.js', '/index.tsx', '/index.ts', '/index.jsx', '/index.js'];

function findLazyImports(filePath, options = {}) {
  const warnings = options.warnings || [];
  if (!fs.existsSync(filePath)) return [];

  const src = fs.readFileSync(filePath, 'utf8');
  let ast;
  try {
    ast = parse(src, PARSE_OPTS);
  } catch (err) {
    warnings.push(makeParseWarning(filePath, err, { phase: 'lazy' }));
    return [];
  }

  const imports = [];
  traverse(ast, {
    CallExpression(nodePath) {
      const node = nodePath.node;
      if (!isLazyCall(node)) return;
      const importPath = getDynamicImportPath(node.arguments[0]);
      if (importPath && importPath.startsWith('.')) {
        imports.push(importPath);
      }
    },
  });
  return imports;
}

function resolveLazyFiles(filePath, options = {}) {
  const maxDepth = options.maxDepth || 5;
  const visited = options.visited || new Set();
  const warnings = options.warnings || [];
  const found = [];

  function visit(currentFile, depth) {
    const resolvedCurrent = path.resolve(currentFile);
    if (visited.has(resolvedCurrent) || depth > maxDepth) return;
    visited.add(resolvedCurrent);

    for (const importPath of findLazyImports(resolvedCurrent, { warnings })) {
      const resolved = resolveImport(resolvedCurrent, importPath, options.frontendSrc);
      if (!resolved) continue;
      found.push(resolved);
      visit(resolved, depth + 1);
    }
  }

  visit(filePath, 0);
  return found;
}

function isLazyCall(node) {
  const callee = node.callee;
  if (callee.type === 'Identifier' && callee.name === 'lazy') return true;
  return callee.type === 'MemberExpression' &&
    callee.object.type === 'Identifier' &&
    callee.object.name === 'React' &&
    callee.property.type === 'Identifier' &&
    callee.property.name === 'lazy';
}

function getDynamicImportPath(fnNode) {
  if (!fnNode || (fnNode.type !== 'ArrowFunctionExpression' && fnNode.type !== 'FunctionExpression')) {
    return null;
  }
  const body = fnNode.body.type === 'BlockStatement'
    ? findReturnedExpression(fnNode.body)
    : fnNode.body;
  if (!body || body.type !== 'CallExpression') return null;
  if (body.callee.type !== 'Import' || body.arguments.length === 0) return null;
  const arg = body.arguments[0];
  return arg.type === 'StringLiteral' ? arg.value : null;
}

function findReturnedExpression(block) {
  const statement = block.body.find(stmt => stmt.type === 'ReturnStatement');
  return statement ? statement.argument : null;
}

function resolveImport(fromFile, importPath, frontendSrc) {
  const base = path.resolve(path.dirname(fromFile), importPath);
  for (const ext of EXTENSIONS) {
    const candidate = base + ext;
    if (!frontendSrc || path.resolve(candidate).startsWith(path.resolve(frontendSrc))) {
      if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) return candidate;
    }
  }
  return null;
}

module.exports = { findLazyImports, resolveLazyFiles, resolveImport };

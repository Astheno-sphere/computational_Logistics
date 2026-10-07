'use strict';

const fs = require('fs');
const path = require('path');
const { parse } = require('@babel/parser');
const traverse = require('@babel/traverse').default;
const { makeParseWarning } = require('./parse-cache');
const { repairSource } = require('./llm-repair');

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

/**
 * Normalize a path string — handle template literals by replacing ${...} with {param}.
 * Strips trailing slashes (except root "/").
 */
function normalizePath(raw) {
  if (!raw) return null;
  // Template literal interpolations → {param}
  let p = raw.replace(/\$\{[^}]+\}/g, '{param}');
  // Remove leading api prefix in case it slipped in
  p = p.replace(/^\/api/, '');
  // Normalize double slashes
  p = p.replace(/\/+/g, '/');
  // Strip trailing slash
  if (p.length > 1 && p.endsWith('/')) p = p.slice(0, -1);
  return p || '/';
}

/**
 * Extract string value from an AST node (StringLiteral or TemplateLiteral).
 */
function extractStringValue(node) {
  if (!node) return null;
  if (node.type === 'StringLiteral') return node.value;
  if (node.type === 'TemplateLiteral') {
    // Build a path with placeholders for each expression
    const parts = [];
    node.quasis.forEach((quasi, i) => {
      parts.push(quasi.value.raw);
      if (node.expressions[i]) {
        parts.push(`\${${getExpressionName(node.expressions[i])}}`);
      }
    });
    return parts.join('');
  }
  // Binary concat: '/users/' + id → '/users/{id}'
  if (node.type === 'BinaryExpression' && node.operator === '+') {
    const left = extractStringValue(node.left);
    const right = extractStringValue(node.right);
    if (left !== null || right !== null) {
      return `${left || '{param}'}${right || '{param}'}`;
    }
  }
  return null;
}

function getExpressionName(node) {
  if (!node) return 'param';
  if (node.type === 'Identifier') return node.name;
  if (node.type === 'MemberExpression') {
    return `${getExpressionName(node.object)}.${getExpressionName(node.property)}`;
  }
  return 'param';
}

// Default seed list — common conventions. Augmented per-project by scanning
// for `const X = axios.create(...)` and imports from the configured apiClientFile.
const DEFAULT_API_CLIENTS = new Set([
  'api', 'apiClient', 'axios', 'client', 'http', 'axiosInstance', 'instance',
  'httpClient', 'request', 'fetcher', 'apiV1', 'apiV2',
]);

/**
 * Detect if this call expression is an API call.
 * Patterns:
 *   api.get('/path')
 *   api.post('/path', data)
 *   axios.get('/path')
 *   apiClient.delete('/path')
 *
 * `clientNames` is a Set of identifier names recognised as API clients in the
 * current project (defaults + auto-discovered from axios.create assignments).
 */
function detectDirectApiCall(node, clientNames) {
  if (node.type !== 'CallExpression') return null;
  const { callee, arguments: args } = node;

  const HTTP_METHODS = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options'];

  if (
    callee.type === 'MemberExpression' &&
    callee.property.type === 'Identifier' &&
    HTTP_METHODS.includes(callee.property.name.toLowerCase()) &&
    args.length > 0
  ) {
    const objName = callee.object.type === 'Identifier' ? callee.object.name : null;
    if (objName && clientNames.has(objName)) {
      const pathVal = extractStringValue(args[0]);
      if (pathVal && pathVal.startsWith('/')) {
        return { method: callee.property.name.toUpperCase(), path: pathVal };
      }
    }
  }
  return null;
}

/**
 * Discover project-specific API client variable names by scanning for
 *   const X = axios.create(...)
 *   export const X = axios.create(...)
 * across the source tree. Returns a Set of names to merge with DEFAULT_API_CLIENTS.
 *
 * Also picks up the default-export name from the configured apiClientFile
 * and the names of imports that resolve to that file.
 */
function discoverApiClientNames(srcDir, apiClientFile, options = {}) {
  const names = new Set();
  const files = walkDir(srcDir, /\.(j|t)sx?$/);
  const warnings = options.warnings || [];

  for (const file of files) {
    let src;
    try { src = fs.readFileSync(file, 'utf8'); } catch { continue; }
    if (!src.includes('axios.create') && !src.includes('createApi')) continue;

    let ast;
    try {
      ast = parseWithCache(file, src, { parseCache: options.parseCache, warnings });
    } catch {
      continue;
    }

    traverse(ast, {
      VariableDeclarator(p) {
        const init = p.node.init;
        if (!init || init.type !== 'CallExpression') return;
        const callee = init.callee;
        // axios.create(...) or createApi(...) or createClient(...)
        const isAxiosCreate =
          callee.type === 'MemberExpression' &&
          callee.object.type === 'Identifier' &&
          callee.object.name === 'axios' &&
          callee.property.type === 'Identifier' &&
          callee.property.name === 'create';
        const isFactory =
          callee.type === 'Identifier' &&
          /^(createApi|createClient|createHttpClient)$/i.test(callee.name);
        if ((isAxiosCreate || isFactory) && p.node.id.type === 'Identifier') {
          names.add(p.node.id.name);
        }
      },
    });
  }

  return names;
}

/**
 * Detect useApiData('/path', opts) — first argument is path.
 */
function detectUseApiData(node) {
  if (node.type !== 'CallExpression') return null;
  const { callee, arguments: args } = node;

  const HOOKS = ['useApiData', 'useFetch', 'useData'];
  if (
    callee.type === 'Identifier' &&
    HOOKS.includes(callee.name) &&
    args.length >= 1
  ) {
    const pathVal = extractStringValue(args[0]);
    if (pathVal && pathVal.startsWith('/')) {
      return { method: 'GET', path: pathVal };
    }
  }
  return null;
}

/**
 * Detect useApiQuery(['key'], '/path', opts) — second argument is path.
 */
function detectUseApiQuery(node) {
  if (node.type !== 'CallExpression') return null;
  const { callee, arguments: args } = node;

  const QUERY_HOOKS = ['useApiQuery', 'useQuery', 'useInfiniteQuery'];
  if (
    callee.type === 'Identifier' &&
    QUERY_HOOKS.includes(callee.name) &&
    args.length >= 2
  ) {
    const pathVal = extractStringValue(args[1]);
    if (pathVal && pathVal.startsWith('/')) {
      return { method: 'GET', path: pathVal };
    }
    // Some hooks: useApiQuery(key, fn, opts) where fn is arrow returning path
    if (args[1].type === 'ArrowFunctionExpression' || args[1].type === 'FunctionExpression') {
      // Not extractable statically — skip
    }
  }
  return null;
}

/**
 * Parse a single source file and return all API calls found.
 * Returns: [{ method, path, callSite, rawPath }]
 */
function parseFile(filePath, options = {}) {
  const src = fs.readFileSync(filePath, 'utf8');
  const results = [];
  const seenPaths = new Set();
  const clientNames = options.clientNames || DEFAULT_API_CLIENTS;
  let staleParse = false;
  let parsedVia = null;
  let llmProvider = null;

  let ast;
  try {
    ast = parseWithCache(filePath, src, options);
    staleParse = !!(ast && ast.__qaProbeStaleParse);
    if (staleParse) delete ast.__qaProbeStaleParse;
    parsedVia = ast && ast.__qaProbeParsedVia;
    llmProvider = ast && ast.__qaProbeLlmProvider;
  } catch {
    return results;
  }

  const relPath = options.relBase
    ? path.relative(options.relBase, filePath).replace(/\\/g, '/')
    : filePath;

  traverse(ast, {
    CallExpression(nodePath) {
      const node = nodePath.node;

      for (const detector of [
        (n) => detectDirectApiCall(n, clientNames),
        detectUseApiData,
        detectUseApiQuery,
      ]) {
        const hit = detector(node);
        if (hit) {
          const normalized = normalizePath(hit.path);
          if (!normalized) break;

          const callSite = `${relPath}:${node.loc ? node.loc.start.line : '?'}`;
          const dedupKey = `${hit.method}:${normalized}`;

          if (!seenPaths.has(dedupKey)) {
            seenPaths.add(dedupKey);
            results.push({
              method: hit.method,
              path: normalized,
              rawPath: hit.path,
              callSite,
              staleParse,
              parsedVia,
              llmProvider,
            });
          }
          break;
        }
      }
    },
  });

  return results;
}

/**
 * Scan all .js, .jsx, .ts, .tsx files under srcDir and return every API call found.
 * Returns: Map<file, [{ method, path, rawPath, callSite }]>
 */
function parseFrontendSrc(srcDir, options = {}) {
  const allFiles = walkDir(srcDir, /\.(j|t)sx?$/);
  const byFile = new Map();
  const allCalls = [];
  const warnings = options.warnings || [];

  // Pre-pass: discover project-specific API client variable names by scanning
  // for axios.create() / createApi() / createClient() factory calls. This means
  // codebases that name their client `apiV2` or `siteApi` get detected without
  // the user having to configure anything.
  const discovered = discoverApiClientNames(srcDir, options.apiClientFile, {
    parseCache: options.parseCache,
    warnings,
  });
  const clientNames = new Set([...DEFAULT_API_CLIENTS, ...discovered]);

  for (const file of allFiles) {
    const calls = parseFile(file, {
      relBase: path.resolve(srcDir, '..', '..'),
      clientNames,
      parseCache: options.parseCache,
      warnings,
    });
    if (calls.length > 0) {
      byFile.set(file, calls);
      allCalls.push(...calls);
    }
  }

  return { byFile, allCalls, clientNames: [...clientNames], warnings };
}

function parseWithCache(filePath, src, options = {}) {
  const warnings = options.warnings || [];
  const parseCache = options.parseCache || null;

  try {
    const ast = parse(src, PARSE_OPTS);
    if (parseCache) parseCache.set(src, ast, filePath);
    return ast;
  } catch (err) {
    const warning = makeParseWarning(filePath, err, { staleParse: false });
    const repaired = repairSource(filePath, src, options.llmRepair || {}, options.llmRepairProvider);
    if (repaired) {
      warnings.push({ ...warning, repaired: true, provider: (options.llmRepair || {}).provider || 'disabled' });
      return repaired.ast;
    }
    if (parseCache) {
      const cached = parseCache.get(src);
      const cachedAst = cached.ast || parseCache.getForFile(filePath);
      if (cachedAst) {
        warning.staleParse = true;
        warnings.push(warning);
        cachedAst.__qaProbeStaleParse = true;
        return cachedAst;
      }
    }
    warnings.push(warning);
    throw err;
  }
}

function walkDir(dir, ext) {
  const results = [];
  if (!fs.existsSync(dir)) return results;

  const SKIP_DIRS = new Set(['node_modules', '.git', 'dist', 'build', '__pycache__', '.next', 'coverage', 'e2e']);

  function walk(current) {
    const entries = fs.readdirSync(current, { withFileTypes: true });
    for (const entry of entries) {
      if (entry.isDirectory()) {
        if (!SKIP_DIRS.has(entry.name)) {
          walk(path.join(current, entry.name));
        }
      } else if (ext.test(entry.name)) {
        results.push(path.join(current, entry.name));
      }
    }
  }

  walk(dir);
  return results;
}

module.exports = {
  parseFrontendSrc,
  parseFile,
  parseWithCache,
  normalizePath,
  discoverApiClientNames,
  DEFAULT_API_CLIENTS,
};

'use strict';

const fs = require('fs');
const path = require('path');
const { parse } = require('@babel/parser');
const traverse = require('@babel/traverse').default;
const { makeParseWarning } = require('./parse-cache');
const { resolveLazyFiles } = require('./lazy-resolver');

const PARSE_OPTS = {
  sourceType: 'module',
  plugins: ['typescript', 'jsx', 'decorators-legacy', 'classProperties', 'optionalChaining', 'nullishCoalescingOperator'],
  errorRecovery: true,
};

/**
 * Normalize a route path segment: ensure it starts with '/' unless it is
 * relative (will be joined with a parent).
 */
function normalizePath(p) {
  if (!p || typeof p !== 'string') return null;
  p = p.trim();
  if (!p || p === '*') return null;
  if (!p.startsWith('/')) p = '/' + p;
  return p;
}

/**
 * Join a parent path and a child path segment into an absolute path.
 * e.g. joinPaths('/', 'dashboard') → '/dashboard'
 *      joinPaths('/admin', 'users') → '/admin/users'
 *      joinPaths('/admin', '/absolute') → '/absolute'
 */
function joinPaths(parent, child) {
  if (!child || typeof child !== 'string') return parent || null;
  child = child.trim();
  if (!child || child === '*') return null;
  // If child is already absolute, use it as-is
  if (child.startsWith('/')) return child;
  // Otherwise join
  const base = (parent || '/').replace(/\/$/, '');
  return base + '/' + child;
}

/**
 * Resolve the component name from a JSX element node (JSXElement or JSXFragment).
 * Returns a string like "Dashboard" or null.
 */
function resolveJsxComponentName(node) {
  if (!node) return null;
  if (node.type === 'JSXElement') {
    const opening = node.openingElement;
    if (!opening) return null;
    const n = opening.name;
    if (n.type === 'JSXIdentifier') return n.name;
    if (n.type === 'JSXMemberExpression') return `${n.object.name}.${n.property.name}`;
  }
  return null;
}

/**
 * Given an AST node for the value of a `path` property (e.g. StringLiteral),
 * return the string value or null.
 */
function extractStringValue(node) {
  if (!node) return null;
  if (node.type === 'StringLiteral') return node.value;
  if (node.type === 'TemplateLiteral' && node.expressions.length === 0 && node.quasis.length === 1) {
    return node.quasis[0].value.cooked;
  }
  return null;
}

function parseRouterSource(filePath, src, options = {}) {
  const warnings = options.warnings || [];
  const parseCache = options.parseCache || null;
  try {
    const ast = parse(src, PARSE_OPTS);
    if (parseCache) parseCache.set(src, ast, filePath);
    return ast;
  } catch (err) {
    const warning = makeParseWarning(filePath, err, { staleParse: false });
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

/**
 * Walk an ObjectExpression representing a single route config entry.
 * Recursively processes `children` arrays.
 * Adds found routes to the provided Map.
 *
 * @param {object} objNode - AST ObjectExpression node
 * @param {string|null} parentPath - the absolute path of the parent route
 * @param {Map} routes - accumulator
 */
function walkRouteConfigObject(objNode, parentPath, routes, options = {}) {
  if (!objNode || objNode.type !== 'ObjectExpression') return;

  let routePathRaw = null;
  let componentName = null;
  let childrenNode = null;

  for (const prop of objNode.properties) {
    if (prop.type !== 'ObjectProperty' && prop.type !== 'Property') continue;
    const key = prop.key;
    const keyName = key.type === 'Identifier' ? key.name :
                    key.type === 'StringLiteral' ? key.value : null;
    if (!keyName) continue;

    if (keyName === 'path') {
      routePathRaw = extractStringValue(prop.value);
    } else if (keyName === 'element') {
      // element: <Component />  — JSXElement inside expression container or directly
      const val = prop.value;
      if (val.type === 'JSXElement') {
        componentName = resolveJsxComponentName(val);
      } else if (val.type === 'JSXExpressionContainer') {
        componentName = resolveJsxComponentName(val.expression);
      }
    } else if (keyName === 'component' || keyName === 'Component') {
      // component: MyComponent (Identifier)
      const val = prop.value;
      if (val.type === 'Identifier') componentName = val.name;
      else if (val.type === 'MemberExpression') {
        componentName = `${val.object.name}.${val.property.name}`;
      }
    } else if (keyName === 'children') {
      childrenNode = prop.value;
    }
  }

  // Compute the absolute path for this route
  let absolutePath = null;
  if (routePathRaw !== null) {
    absolutePath = joinPaths(parentPath, routePathRaw);
    // Make sure purely wildcard paths are skipped
    if (absolutePath) {
      const tail = absolutePath.replace(/.*\//, '');
      if (tail === '*') absolutePath = null;
    }
  }

  if (absolutePath && !routes.has(absolutePath)) {
    routes.set(absolutePath, {
      component: componentName || null,
      authGuard: 'Route',
      requiredScopes: [],
      staleParse: !!options.staleParse,
    });
  }

  // Recurse into children
  if (childrenNode && childrenNode.type === 'ArrayExpression') {
    for (const el of childrenNode.elements) {
      if (el && el.type === 'ObjectExpression') {
        walkRouteConfigObject(el, absolutePath || parentPath, routes, options);
      }
    }
  }
}

/**
 * Extract routes from React Router v6.4+ object-config API:
 *   createBrowserRouter([...])
 *   createMemoryRouter([...])
 *   createHashRouter([...])
 */
function extractRoutesFromObjectConfig(routerFile, srcDir, options = {}) {
  const routes = new Map();
  if (!fs.existsSync(routerFile)) return routes;

  const src = fs.readFileSync(routerFile, 'utf8');
  let ast;
  let staleParse = false;
  try {
    ast = parseRouterSource(routerFile, src, options);
    staleParse = !!(ast && ast.__qaProbeStaleParse);
    if (staleParse) delete ast.__qaProbeStaleParse;
  } catch (err) {
    process.stderr.write(`[qa-probe] (objectConfig) Failed to parse ${routerFile}: ${err.message}\n`);
    return routes;
  }

  const ROUTER_CREATORS = /^create(Browser|Memory|Hash)Router$/;

  traverse(ast, {
    CallExpression(nodePath) {
      const callee = nodePath.node.callee;
      let calleeName = null;

      if (callee.type === 'Identifier') {
        calleeName = callee.name;
      } else if (callee.type === 'MemberExpression' && callee.property.type === 'Identifier') {
        calleeName = callee.property.name;
      }

      if (!calleeName || !ROUTER_CREATORS.test(calleeName)) return;

      const args = nodePath.node.arguments;
      if (!args || args.length === 0) return;

      const firstArg = args[0];
      if (firstArg.type !== 'ArrayExpression') return;

      for (const el of firstArg.elements) {
        if (el && el.type === 'ObjectExpression') {
          walkRouteConfigObject(el, null, routes, { staleParse });
        }
      }
    },
  });

  return routes;
}

/**
 * Extract routes from TanStack Router:
 *   createRoute({ path: '/...', component: X })
 *   createFileRoute('/path')({ component: X })
 */
function extractRoutesFromTanStack(routerFile, srcDir, options = {}) {
  const routes = new Map();
  if (!fs.existsSync(routerFile)) return routes;

  const src = fs.readFileSync(routerFile, 'utf8');
  let ast;
  let staleParse = false;
  try {
    ast = parseRouterSource(routerFile, src, options);
    staleParse = !!(ast && ast.__qaProbeStaleParse);
    if (staleParse) delete ast.__qaProbeStaleParse;
  } catch (err) {
    process.stderr.write(`[qa-probe] (tanstack) Failed to parse ${routerFile}: ${err.message}\n`);
    return routes;
  }

  traverse(ast, {
    CallExpression(nodePath) {
      const node = nodePath.node;
      const callee = node.callee;

      // --- Pattern: createRoute({ path, component, getParentRoute })
      const isCreateRoute =
        (callee.type === 'Identifier' && callee.name === 'createRoute') ||
        (callee.type === 'MemberExpression' &&
          callee.property.type === 'Identifier' &&
          callee.property.name === 'createRoute');

      if (isCreateRoute) {
        const args = node.arguments;
        if (!args || args.length === 0) return;
        const firstArg = args[0];
        if (firstArg.type !== 'ObjectExpression') return;

        let routePath = null;
        let componentName = null;

        for (const prop of firstArg.properties) {
          if (prop.type !== 'ObjectProperty' && prop.type !== 'Property') continue;
          const keyName = prop.key.type === 'Identifier' ? prop.key.name :
                          prop.key.type === 'StringLiteral' ? prop.key.value : null;
          if (!keyName) continue;

          if (keyName === 'path') {
            routePath = extractStringValue(prop.value);
          } else if (keyName === 'component' || keyName === 'Component') {
            if (prop.value.type === 'Identifier') componentName = prop.value.name;
            else if (prop.value.type === 'MemberExpression') {
              componentName = `${prop.value.object.name}.${prop.value.property.name}`;
            } else if (prop.value.type === 'ArrowFunctionExpression' ||
                       prop.value.type === 'FunctionExpression') {
              componentName = '(inline)';
            }
          }
        }

        if (routePath) {
          const absPath = normalizePath(routePath);
          if (absPath && !routes.has(absPath)) {
            routes.set(absPath, {
              component: componentName || null,
              authGuard: 'Route',
              requiredScopes: [],
              staleParse,
            });
          }
        }
        return;
      }

      // --- Pattern: createFileRoute('/path')({ component: X })
      // This is a CallExpression whose callee is itself a CallExpression:
      //   createFileRoute('/path')  ← inner call
      // and the outer call takes { component: X }
      const isOuterFileRoute =
        callee.type === 'CallExpression' &&
        (() => {
          const innerCallee = callee.callee;
          return (
            (innerCallee.type === 'Identifier' && innerCallee.name === 'createFileRoute') ||
            (innerCallee.type === 'MemberExpression' &&
              innerCallee.property.type === 'Identifier' &&
              innerCallee.property.name === 'createFileRoute')
          );
        })();

      if (isOuterFileRoute) {
        // Path comes from the inner call's first argument
        const innerArgs = callee.arguments;
        let routePath = null;
        if (innerArgs && innerArgs.length > 0) {
          routePath = extractStringValue(innerArgs[0]);
        }

        // Component comes from the outer call's first argument object
        let componentName = null;
        const outerArgs = node.arguments;
        if (outerArgs && outerArgs.length > 0 && outerArgs[0].type === 'ObjectExpression') {
          for (const prop of outerArgs[0].properties) {
            if (prop.type !== 'ObjectProperty' && prop.type !== 'Property') continue;
            const keyName = prop.key.type === 'Identifier' ? prop.key.name :
                            prop.key.type === 'StringLiteral' ? prop.key.value : null;
            if (keyName === 'component' || keyName === 'Component') {
              if (prop.value.type === 'Identifier') componentName = prop.value.name;
              else if (prop.value.type === 'MemberExpression') {
                componentName = `${prop.value.object.name}.${prop.value.property.name}`;
              } else if (prop.value.type === 'ArrowFunctionExpression' ||
                         prop.value.type === 'FunctionExpression') {
                componentName = '(inline)';
              }
            }
          }
        }

        if (routePath) {
          const absPath = normalizePath(routePath);
          if (absPath && !routes.has(absPath)) {
            routes.set(absPath, {
              component: componentName || null,
              authGuard: 'Route',
              requiredScopes: [],
              staleParse,
            });
          }
        }
      }
    },
  });

  return routes;
}

/**
 * Extract frontend route definitions from the router file (App.tsx or similar).
 *
 * Looks for:
 *   <Route path="/some-path" element={<Component />} />
 *   <ScopeRoute path="..." scopes={["scope:read"]} />
 *   <AdminRoute path="..." />
 *   <PrivateRoute path="..." />
 *   createBrowserRouter([{ path, element, children }])   (React Router v6.4+)
 *   createMemoryRouter / createHashRouter               (same shape)
 *   createRoute({ path, component })                    (TanStack Router)
 *   createFileRoute('/path')({ component })             (TanStack file-based)
 *
 * Returns Map<routePath, { component, authGuard, requiredScopes }>
 */
function extractRoutes(routerFile, srcDir, options = {}) {
  if (!fs.existsSync(routerFile)) {
    process.stderr.write(`[qa-probe] Router file not found: ${routerFile}\n`);
    return new Map();
  }
  const lazyVisited = options.lazyVisited || new Set();
  const resolvedRouterFile = path.resolve(routerFile);
  if (lazyVisited.has(resolvedRouterFile)) return new Map();
  lazyVisited.add(resolvedRouterFile);

  const src = fs.readFileSync(routerFile, 'utf8');
  const routes = new Map();

  let ast;
  let staleParse = false;
  try {
    ast = parseRouterSource(routerFile, src, options);
    staleParse = !!(ast && ast.__qaProbeStaleParse);
    if (staleParse) delete ast.__qaProbeStaleParse;
  } catch (err) {
    process.stderr.write(`[qa-probe] Failed to parse router file: ${err.message}\n`);
    return routes;
  }

  // Auth guard component names we recognize
  const AUTH_GUARDS = new Set(['ScopeRoute', 'AdminRoute', 'PrivateRoute', 'ProtectedRoute', 'AuthRoute', 'RequireAuth']);
  const ROUTE_COMPONENTS = new Set(['Route', ...AUTH_GUARDS]);

  // --- Strategy 1: JSX <Route> / <ScopeRoute> etc. ---
  traverse(ast, {
    JSXOpeningElement(nodePath) {
      const { name, attributes } = nodePath.node;

      const componentName =
        name.type === 'JSXIdentifier' ? name.name :
        name.type === 'JSXMemberExpression' ? `${name.object.name}.${name.property.name}` : null;

      if (!componentName || !ROUTE_COMPONENTS.has(componentName)) return;

      // Extract attributes
      const attrs = {};
      for (const attr of attributes) {
        if (attr.type !== 'JSXAttribute') continue;
        const attrName = attr.name.name;
        const val = attr.value;

        if (!val) {
          attrs[attrName] = true;
        } else if (val.type === 'StringLiteral') {
          attrs[attrName] = val.value;
        } else if (val.type === 'JSXExpressionContainer') {
          const expr = val.expression;
          if (expr.type === 'StringLiteral') {
            attrs[attrName] = expr.value;
          } else if (expr.type === 'JSXElement') {
            attrs[attrName] = resolveJsxComponentName(expr);
          } else if (expr.type === 'ArrayExpression') {
            attrs[attrName] = expr.elements
              .filter(e => e && e.type === 'StringLiteral')
              .map(e => e.value);
          } else if (expr.type === 'Identifier') {
            attrs[attrName] = `{${expr.name}}`;
          }
        }
      }

      let routePath = attrs.path;
      if (!routePath || typeof routePath !== 'string') return;
      if (routePath.includes('*') && !routePath.includes(':')) return; // wildcard catch-all
      // Normalize relative paths (React Router v6 nested routes) to absolute
      if (!routePath.startsWith('/')) routePath = '/' + routePath;

      // Resolve component name from element prop or from JSX children context
      let component = null;
      const elementAttr = attrs.element;
      if (typeof elementAttr === 'string') {
        component = elementAttr;
      } else if (elementAttr === undefined) {
        // Try parent JSXElement to find element attribute
        const parent = nodePath.findParent(p => p.isJSXElement());
        if (parent) {
          const opening = parent.node.openingElement;
          for (const attr of opening.attributes) {
            if (attr.type === 'JSXAttribute' && attr.name.name === 'element') {
              const v = attr.value;
              if (v && v.type === 'JSXExpressionContainer' && v.expression.type === 'JSXElement') {
                const inner = v.expression.openingElement.name;
                component = inner.type === 'JSXIdentifier' ? inner.name : null;
              }
            }
          }
        }
      }

      const isAuthGuard = AUTH_GUARDS.has(componentName);
      const requiredScopes = Array.isArray(attrs.scopes) ? attrs.scopes : [];

      if (!routes.has(routePath)) {
        routes.set(routePath, {
          component: component || null,
          authGuard: isAuthGuard ? componentName : 'Route',
          requiredScopes,
          staleParse,
        });
      }
    },
  });

  // --- Strategy 2: createBrowserRouter / createMemoryRouter / createHashRouter ---
  const objectConfigRoutes = extractRoutesFromObjectConfig(routerFile, srcDir, options);
  for (const [p, info] of objectConfigRoutes) {
    if (!routes.has(p)) {
      routes.set(p, info);
    }
  }

  // --- Strategy 3: TanStack Router createRoute / createFileRoute ---
  const tanstackRoutes = extractRoutesFromTanStack(routerFile, srcDir, options);
  for (const [p, info] of tanstackRoutes) {
    if (!routes.has(p)) {
      routes.set(p, info);
    }
  }

  const lazyFiles = resolveLazyFiles(routerFile, {
    frontendSrc: srcDir,
    warnings: options.warnings || [],
    maxDepth: 5,
  });
  for (const lazyFile of lazyFiles) {
    const lazyRoutes = extractRoutes(lazyFile, srcDir, {
      ...options,
      lazyVisited,
    });
    for (const [p, info] of lazyRoutes) {
      if (!routes.has(p)) {
        routes.set(p, { ...info, lazyResolved: true });
      }
    }
  }

  return routes;
}

module.exports = { extractRoutes, extractRoutesFromObjectConfig, extractRoutesFromTanStack, parseRouterSource };

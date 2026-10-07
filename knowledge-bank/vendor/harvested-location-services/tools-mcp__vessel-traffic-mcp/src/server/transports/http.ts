import { randomUUID, timingSafeEqual } from 'node:crypto';
import { createServer, type IncomingMessage, type Server, type ServerResponse } from 'node:http';
import type { AddressInfo } from 'node:net';
import { Readable } from 'node:stream';

import { WebStandardStreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/webStandardStreamableHttp.js';
import { isInitializeRequest } from '@modelcontextprotocol/sdk/types.js';

import type { HttpRuntimeConfig } from '../../config/runtime.js';
import type { ProviderRegistry } from '../../providers/registry.js';
import { createRuntimeProviderRegistry } from '../../providers/runtime-registry.js';
import type { ProviderStatus } from '../../providers/types.js';
import { createJsonLogger, type JsonLogger } from '../../util/logger.js';
import { redactForLog } from '../../util/redact.js';
import { createVesselMcpServer } from '../create-server.js';
import { createServerCard } from '../server-card.js';

const defaultMcpPath = '/mcp';
const defaultHealthPath = '/health';
const defaultServerCardPath = '/.well-known/mcp/server-card.json';
const defaultMaxBodyBytes = 1024 * 1024;

interface McpHttpSession {
  server: ReturnType<typeof createVesselMcpServer>;
  transport: WebStandardStreamableHTTPServerTransport;
}

export interface StartHttpServerOptions extends HttpRuntimeConfig {
  mcpPath?: string;
  healthPath?: string;
  serverCardPath?: string;
  maxBodyBytes?: number;
  logger?: HttpEventLogger | false;
  registry?: ProviderRegistry;
}

export interface HttpServerHandle {
  server: Server;
  origin: string;
  mcpUrl: string;
  healthUrl: string;
  serverCardUrl: string;
  close(): Promise<void>;
}

export type HttpLogLevel = 'info' | 'warn' | 'error';

export type HttpEventLogEntry =
  | {
      ts: string;
      level: HttpLogLevel;
      event: 'http_request';
      requestId: string;
      method: string;
      path: string;
      status: number;
      durationMs: number;
      authRequired: boolean;
      transport: 'streamable-http';
    }
  | {
      ts: string;
      level: 'info';
      event: 'http_server_started' | 'http_server_stopped';
      host: string;
      port: number;
      mcpPath: string;
      healthPath: string;
      authRequired: boolean;
      transport: 'streamable-http';
    }
  | {
      ts: string;
      level: 'info' | 'warn';
      event: 'provider_status_diagnostics';
      transport: 'streamable-http';
      providerCount: number;
      summary: ProviderDiagnosticsSummary;
      providers: ProviderDiagnosticEntry[];
    }
  | {
      ts: string;
      level: 'error';
      event: 'http_request_error' | 'http_response_error' | 'http_logger_error';
      requestId?: string;
      reason: string;
      transport: 'streamable-http';
    };

export interface ProviderDiagnosticsSummary {
  total: number;
  available: number;
  degraded: number;
  unavailable: number;
  fixtureBacked: number;
  liveCapable: number;
}

export interface ProviderDiagnosticEntry {
  id: string;
  status: 'available' | 'degraded' | 'unavailable' | 'unknown';
  authState: string;
  capabilityCount: number;
  sourceTransport: string;
  fixtureBacked: boolean;
}

export type HttpEventLogger = (entry: HttpEventLogEntry) => void;

export interface McpHttpHandler {
  handle(request: Request): Promise<Response>;
  close(): Promise<void>;
}

export function createMcpHttpHandler(options: StartHttpServerOptions): McpHttpHandler {
  const sessions = new Map<string, McpHttpSession>();
  const mcpPath = options.mcpPath ?? defaultMcpPath;
  const healthPath = options.healthPath ?? defaultHealthPath;
  const serverCardPath = options.serverCardPath ?? defaultServerCardPath;
  const maxBodyBytes = options.maxBodyBytes ?? defaultMaxBodyBytes;

  return {
    async handle(request) {
      const requestId = randomUUID();
      const startedAt = Date.now();
      const path = requestPath(request);
      let response: Response;

      try {
        if (request.method === 'OPTIONS') {
          response = withCors(new Response(null, { status: 204 }));
        } else if (path === healthPath) {
          response = withCors(handleHealthRequest(request, mcpPath));
        } else if (path === serverCardPath) {
          response = withCors(handleServerCardRequest(request, {
            authRequired: Boolean(options.authToken),
            mcpPath,
          }));
        } else if (path !== mcpPath) {
          response = withCors(jsonResponse(404, { error: 'not_found' }));
        } else if (!isAuthorized(request, options.authToken)) {
          response = withCors(unauthorizedResponse());
        } else {
          response = withCors(
            await handleMcpRequest(request, {
              sessions,
              maxBodyBytes,
              registry: options.registry,
            }),
          );
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        logHttpEvent(options.logger, {
          ts: new Date().toISOString(),
          level: 'error',
          event: 'http_request_error',
          requestId,
          reason: redactForLog(message),
          transport: 'streamable-http',
        });

        response = withCors(jsonRpcErrorResponse(500, -32603, 'Internal server error'));
      }

      const responseWithRequestId = withRequestId(response, requestId);
      logHttpEvent(options.logger, {
        ts: new Date().toISOString(),
        level: logLevelForStatus(responseWithRequestId.status),
        event: 'http_request',
        requestId,
        method: request.method,
        path,
        status: responseWithRequestId.status,
        durationMs: Date.now() - startedAt,
        authRequired: Boolean(options.authToken),
        transport: 'streamable-http',
      });

      return responseWithRequestId;
    },
    async close() {
      await Promise.all([...sessions.values()].map((session) => closeSession(session)));
      sessions.clear();
    },
  };
}

export async function startHttpServer(options: StartHttpServerOptions): Promise<HttpServerHandle> {
  const logger = options.logger === undefined ? defaultHttpEventLogger : options.logger;
  const mcpPath = options.mcpPath ?? defaultMcpPath;
  const healthPath = options.healthPath ?? defaultHealthPath;
  const serverCardPath = options.serverCardPath ?? defaultServerCardPath;
  const handler = createMcpHttpHandler({ ...options, logger });
  const httpServer = createServer(async (req, res) => {
    try {
      const response = await handler.handle(nodeRequestToWebRequest(req));
      await writeWebResponseToNode(res, response);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      logHttpEvent(logger, {
        ts: new Date().toISOString(),
        level: 'error',
        event: 'http_response_error',
        reason: redactForLog(message),
        transport: 'streamable-http',
      });

      if (!res.headersSent) {
        await writeWebResponseToNode(res, withCors(jsonRpcErrorResponse(500, -32603, 'Internal server error')));
      } else {
        res.destroy();
      }
    }
  });

  await new Promise<void>((resolve, reject) => {
    httpServer.once('error', reject);
    httpServer.listen(options.port, options.host, () => {
      httpServer.off('error', reject);
      resolve();
    });
  });

  const address = httpServer.address();
  if (!isAddressInfo(address)) {
    throw new Error('HTTP server did not expose a TCP address.');
  }

  const origin = `http://${formatHostForUrl(options.host)}:${address.port}`;
  logHttpEvent(logger, {
    ts: new Date().toISOString(),
    level: 'info',
    event: 'http_server_started',
    host: options.host,
    port: address.port,
    mcpPath,
    healthPath,
    authRequired: Boolean(options.authToken),
    transport: 'streamable-http',
  });

  const diagnosticsRegistry = options.registry ?? createRuntimeProviderRegistry();
  const diagnosticsEntry = await buildProviderStatusDiagnosticsEntry(diagnosticsRegistry);
  logHttpEvent(logger, diagnosticsEntry);

  return {
    server: httpServer,
    origin,
    mcpUrl: `${origin}${mcpPath}`,
    healthUrl: `${origin}${healthPath}`,
    serverCardUrl: `${origin}${serverCardPath}`,
    async close() {
      await handler.close();
      await new Promise<void>((resolve, reject) => {
        httpServer.close((error) => {
          if (error) {
            reject(error);
            return;
          }
          resolve();
        });
      });
      logHttpEvent(logger, {
        ts: new Date().toISOString(),
        level: 'info',
        event: 'http_server_stopped',
        host: options.host,
        port: address.port,
        mcpPath,
        healthPath,
        authRequired: Boolean(options.authToken),
        transport: 'streamable-http',
      });
    },
  };
}

function handleServerCardRequest(
  request: Request,
  options: {
    authRequired: boolean;
    mcpPath: string;
  },
): Response {
  if (request.method === 'GET' || request.method === 'HEAD') {
    return jsonResponse(200, createServerCard(options), undefined, request.method === 'HEAD');
  }

  return jsonResponse(405, { error: 'method_not_allowed' }, { Allow: 'GET, HEAD, OPTIONS' });
}

async function handleMcpRequest(
  request: Request,
  options: {
    sessions: Map<string, McpHttpSession>;
    maxBodyBytes: number;
    registry?: ProviderRegistry;
  },
): Promise<Response> {
  if (request.method !== 'POST' && request.method !== 'GET' && request.method !== 'DELETE') {
    return jsonRpcErrorResponse(405, -32000, 'Method not allowed.', {
      Allow: 'GET, POST, DELETE, OPTIONS',
    });
  }

  const sessionId = request.headers.get('mcp-session-id') ?? undefined;

  if (request.method === 'GET' || request.method === 'DELETE') {
    const session = getExistingSession(options.sessions, sessionId);
    if (session instanceof Response) {
      return session;
    }

    return session.transport.handleRequest(request);
  }

  const parsedBody = await readJsonRequestBody(request, options.maxBodyBytes);

  if (parsedBody instanceof Response) {
    return parsedBody;
  }

  if (sessionId) {
    const session = getExistingSession(options.sessions, sessionId);
    if (session instanceof Response) {
      return session;
    }

    return session.transport.handleRequest(request, { parsedBody });
  }

  if (!hasInitializeRequest(parsedBody)) {
    return jsonRpcErrorResponse(400, -32000, 'Bad Request: No valid session ID provided.');
  }

  const server = createVesselMcpServer({ registry: options.registry });
  const transport = new WebStandardStreamableHTTPServerTransport({
    sessionIdGenerator: () => randomUUID(),
    enableJsonResponse: true,
    onsessioninitialized: (newSessionId) => {
      options.sessions.set(newSessionId, { server, transport });
    },
    onsessionclosed: async (closedSessionId) => {
      const session = options.sessions.get(closedSessionId);
      options.sessions.delete(closedSessionId);
      if (session) {
        await closeSession(session);
      }
    },
  });

  await server.connect(transport);
  return transport.handleRequest(request, { parsedBody });
}

function handleHealthRequest(request: Request, mcpPath: string): Response {
  if (request.method === 'GET' || request.method === 'HEAD') {
    return jsonResponse(
      200,
      {
        status: 'ok',
        name: 'vessel-traffic-mcp',
        transport: 'streamable-http',
        mcpEndpoint: mcpPath,
      },
      undefined,
      request.method === 'HEAD',
    );
  }

  return jsonResponse(405, { error: 'method_not_allowed' }, { Allow: 'GET, HEAD, OPTIONS' });
}

function getExistingSession(
  sessions: Map<string, McpHttpSession>,
  sessionId: string | undefined,
): McpHttpSession | Response {
  if (!sessionId) {
    return jsonRpcErrorResponse(400, -32000, 'Bad Request: No valid session ID provided.');
  }

  const session = sessions.get(sessionId);
  if (!session) {
    return jsonRpcErrorResponse(404, -32000, 'Session not found.');
  }

  return session;
}

function hasInitializeRequest(parsedBody: unknown): boolean {
  const messages = Array.isArray(parsedBody) ? parsedBody : [parsedBody];
  return messages.some((message) => isInitializeRequest(message));
}

async function readJsonRequestBody(request: Request, maxBodyBytes: number): Promise<unknown | Response> {
  const body = request.body;
  if (!body) {
    return undefined;
  }

  const reader = body.getReader();
  const chunks: Buffer[] = [];
  let size = 0;

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      break;
    }

    const buffer = Buffer.from(value);
    size += buffer.byteLength;
    if (size > maxBodyBytes) {
      await reader.cancel();
      return jsonRpcErrorResponse(413, -32000, 'Request body exceeds the configured MCP HTTP limit.');
    }
    chunks.push(buffer);
  }

  if (chunks.length === 0) {
    return undefined;
  }

  try {
    return JSON.parse(Buffer.concat(chunks).toString('utf8')) as unknown;
  } catch {
    return jsonRpcErrorResponse(400, -32700, 'Parse error: Invalid JSON');
  }
}

function isAuthorized(request: Request, authToken: string | undefined): boolean {
  if (!authToken) {
    return true;
  }

  const authorization = request.headers.get('authorization');
  if (!authorization) {
    return false;
  }

  const [scheme, token] = splitAuthorizationHeader(authorization);
  return /^bearer$/i.test(scheme) && timingSafeTextEqual(token, authToken);
}

function splitAuthorizationHeader(value: string): [scheme: string, token: string] {
  const separatorIndex = value.indexOf(' ');
  if (separatorIndex === -1) {
    return [value, ''];
  }

  return [value.slice(0, separatorIndex), value.slice(separatorIndex + 1)];
}

function timingSafeTextEqual(received: string, expected: string): boolean {
  const expectedBuffer = Buffer.from(expected);
  const receivedSource = Buffer.from(received);
  const receivedBuffer = Buffer.alloc(expectedBuffer.length);
  receivedSource.copy(receivedBuffer, 0, 0, expectedBuffer.length);

  return receivedSource.length === expectedBuffer.length && timingSafeEqual(receivedBuffer, expectedBuffer);
}

function unauthorizedResponse(): Response {
  return jsonRpcErrorResponse(401, -32001, 'Unauthorized.', {
    'WWW-Authenticate': 'Bearer realm="vessel-traffic-mcp"',
  });
}

function jsonRpcErrorResponse(
  status: number,
  code: number,
  message: string,
  headers?: Record<string, string>,
): Response {
  return jsonResponse(
    status,
    {
      jsonrpc: '2.0',
      error: {
        code,
        message,
      },
      id: null,
    },
    headers,
  );
}

function jsonResponse(
  status: number,
  body: Record<string, unknown>,
  headers: Record<string, string> = {},
  omitBody = false,
): Response {
  const responseHeaders = new Headers(headers);
  responseHeaders.set('Content-Type', 'application/json');

  return new Response(omitBody ? null : `${JSON.stringify(body)}\n`, {
    status,
    headers: responseHeaders,
  });
}

function withCors(response: Response): Response {
  const headers = new Headers(response.headers);
  headers.set('Access-Control-Allow-Origin', '*');
  headers.set('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS');
  headers.set(
    'Access-Control-Allow-Headers',
    'Authorization, Content-Type, Mcp-Session-Id, MCP-Protocol-Version, Last-Event-ID',
  );
  headers.set('Access-Control-Expose-Headers', 'Mcp-Session-Id, MCP-Protocol-Version, X-Request-Id');
  headers.set('Access-Control-Max-Age', '86400');
  headers.set('Vary', 'Origin, Access-Control-Request-Method, Access-Control-Request-Headers');

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

function withRequestId(response: Response, requestId: string): Response {
  const headers = new Headers(response.headers);
  headers.set('X-Request-Id', requestId);

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

function requestPath(request: Request): string {
  try {
    return new URL(request.url).pathname;
  } catch {
    return '/';
  }
}

function logLevelForStatus(status: number): HttpLogLevel {
  if (status >= 500) {
    return 'error';
  }

  if (status >= 400) {
    return 'warn';
  }

  return 'info';
}

function logHttpEvent(logger: HttpEventLogger | false | undefined, entry: HttpEventLogEntry): void {
  if (!logger) {
    return;
  }

  try {
    logger(entry);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    fallbackLogger.error('http_logger_error', {
      reason: redactForLog(message),
      transport: 'streamable-http',
      droppedEvent: entry.event,
    });
  }
}

const fallbackLogger: JsonLogger = createJsonLogger();

function defaultHttpEventLogger(entry: HttpEventLogEntry): void {
  fallbackLogger.log(entry.level as 'info' | 'warn' | 'error' | 'debug', entry.event, entry);
}

export async function buildProviderStatusDiagnosticsEntry(
  registry: ProviderRegistry,
): Promise<HttpEventLogEntry & { event: 'provider_status_diagnostics' }> {
  const providers = registry.providers();
  const entries: ProviderDiagnosticEntry[] = [];
  let degraded = 0;
  let available = 0;
  let unavailable = 0;
  let fixtureBacked = 0;
  let liveCapable = 0;

  for (const provider of providers) {
    const isFixtureLike = isFixtureBacked(provider);
    if (isFixtureLike) {
      fixtureBacked += 1;
    } else {
      liveCapable += 1;
    }

    const safeStatus = isFixtureLike
      ? await safeProviderStatus(provider)
      : undefined;

    const sourceTransport = safeStatus?.source.transport ?? safeProviderTransport(provider);
    const status = safeStatus?.status ?? 'unknown';
    if (status === 'available') {
      available += 1;
    } else if (status === 'degraded') {
      degraded += 1;
    } else if (status === 'unavailable') {
      unavailable += 1;
    }

    entries.push({
      id: provider.id,
      status,
      authState: safeStatus?.authState ?? 'unknown',
      capabilityCount: provider.capabilities().length,
      sourceTransport,
      fixtureBacked: isFixtureLike,
    });
  }

  return {
    ts: new Date().toISOString(),
    level: liveCapable > 0 ? 'warn' : 'info',
    event: 'provider_status_diagnostics',
    transport: 'streamable-http',
    providerCount: providers.length,
    summary: {
      total: providers.length,
      available,
      degraded,
      unavailable,
      fixtureBacked,
      liveCapable,
    },
    providers: entries,
  };
}

function isFixtureBacked(provider: ReturnType<ProviderRegistry['providers']>[number]): boolean {
  const accessClass = provider.metadata?.().accessClass;
  return accessClass === 'fixture' || accessClass === 'capture-fixture';
}

async function safeProviderStatus(
  provider: ReturnType<ProviderRegistry['providers']>[number],
): Promise<ProviderStatus | undefined> {
  try {
    return await provider.status();
  } catch {
    return undefined;
  }
}

function safeProviderTransport(provider: ReturnType<ProviderRegistry['providers']>[number]): string {
  const accessClass = provider.metadata?.().accessClass;
  if (accessClass === 'fixture' || accessClass === 'capture-fixture') {
    return accessClass;
  }
  return 'unknown';
}

function nodeRequestToWebRequest(req: IncomingMessage): Request {
  const url = new URL(req.url ?? '/', `http://${req.headers.host ?? 'localhost'}`);
  const method = req.method ?? 'GET';
  const headers = new Headers();

  for (const [name, value] of Object.entries(req.headers)) {
    if (Array.isArray(value)) {
      for (const item of value) {
        headers.append(name, item);
      }
    } else if (value !== undefined) {
      headers.set(name, value);
    }
  }

  if (method === 'GET' || method === 'HEAD') {
    return new Request(url, { method, headers });
  }

  const init: RequestInit & { duplex: 'half' } = {
    method,
    headers,
    body: Readable.toWeb(req) as ReadableStream,
    duplex: 'half',
  };

  return new Request(url, init);
}

async function writeWebResponseToNode(res: ServerResponse, response: Response): Promise<void> {
  response.headers.forEach((value, name) => {
    res.setHeader(name, value);
  });
  res.writeHead(response.status, response.statusText);

  if (!response.body) {
    res.end();
    return;
  }

  for await (const chunk of response.body) {
    res.write(Buffer.from(chunk));
  }
  res.end();
}

function formatHostForUrl(host: string): string {
  if (host === '0.0.0.0') {
    return '127.0.0.1';
  }

  if (host === '::') {
    return '[::1]';
  }

  if (host.includes(':') && !host.startsWith('[')) {
    return `[${host}]`;
  }

  return host;
}

function isAddressInfo(address: string | AddressInfo | null): address is AddressInfo {
  return typeof address === 'object' && address !== null;
}

async function closeSession(session: McpHttpSession): Promise<void> {
  await Promise.allSettled([session.transport.close(), session.server.close()]);
}

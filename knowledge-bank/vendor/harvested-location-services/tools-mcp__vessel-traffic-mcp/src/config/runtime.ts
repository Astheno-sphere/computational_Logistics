export interface RuntimeConfig {
  transport: 'stdio' | 'http';
  http: HttpRuntimeConfig;
}

export interface HttpRuntimeConfig {
  host: string;
  port: number;
  authToken?: string;
}

export function loadRuntimeConfig(env: NodeJS.ProcessEnv = process.env): RuntimeConfig {
  const requestedTransport = env.VESSEL_MCP_TRANSPORT ?? 'stdio';
  const transport = requestedTransport === 'streamable-http' ? 'http' : requestedTransport;

  if (transport !== 'stdio' && transport !== 'http') {
    throw new Error(
      `Unsupported VESSEL_MCP_TRANSPORT "${requestedTransport}". Supported values are "stdio", "http", and "streamable-http".`,
    );
  }

  return {
    transport,
    http: {
      host: env.VESSEL_MCP_HTTP_HOST ?? '127.0.0.1',
      port: parseHttpPort(env.VESSEL_MCP_HTTP_PORT ?? '3000'),
      authToken: normalizeOptionalSecret(env.VESSEL_MCP_AUTH_TOKEN),
    },
  };
}

function parseHttpPort(rawPort: string): number {
  if (!/^\d+$/.test(rawPort)) {
    throw new Error('VESSEL_MCP_HTTP_PORT must be an integer between 0 and 65535.');
  }

  const port = Number.parseInt(rawPort, 10);
  if (!Number.isSafeInteger(port) || port < 0 || port > 65535) {
    throw new Error('VESSEL_MCP_HTTP_PORT must be an integer between 0 and 65535.');
  }

  return port;
}

function normalizeOptionalSecret(value: string | undefined): string | undefined {
  if (value === undefined || value.trim() === '') {
    return undefined;
  }

  return value;
}

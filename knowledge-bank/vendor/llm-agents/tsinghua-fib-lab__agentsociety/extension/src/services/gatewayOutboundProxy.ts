import type { Agent as HttpAgent } from 'http';
import type { Agent as HttpsAgent } from 'https';

export type OutboundProxyConfig = {
  /** http://127.0.0.1:7890 or socks5://127.0.0.1:1080 */
  url: string;
  username?: string;
  password?: string;
};

export function buildOutboundProxyUrl(config: OutboundProxyConfig): string | null {
  const raw = config.url.trim();
  if (!raw) {
    return null;
  }
  try {
    const parsed = new URL(raw);
    if (!['http:', 'https:', 'socks:', 'socks5:'].includes(parsed.protocol)) {
      return null;
    }
    if (config.username && !parsed.username) {
      parsed.username = config.username;
      parsed.password = config.password ?? '';
    }
    return parsed.toString();
  } catch {
    return null;
  }
}

export function createOutboundProxyAgent(
  config: OutboundProxyConfig | null | undefined
): HttpAgent | HttpsAgent | undefined {
  if (!config?.url.trim()) {
    return undefined;
  }
  const proxyUrl = buildOutboundProxyUrl(config);
  if (!proxyUrl) {
    return undefined;
  }
  if (proxyUrl.startsWith('socks')) {
    const { SocksProxyAgent } = require('socks-proxy-agent') as typeof import('socks-proxy-agent');
    return new SocksProxyAgent(proxyUrl) as unknown as HttpAgent;
  }
  const { HttpsProxyAgent } = require('https-proxy-agent') as typeof import('https-proxy-agent');
  return new HttpsProxyAgent(proxyUrl) as unknown as HttpsAgent;
}

import * as http from 'http';
import * as https from 'https';

export interface FetchCompatResponse {
  ok: boolean;
  status: number;
  statusText: string;
  text(): Promise<string>;
  json<T = unknown>(): Promise<T>;
}

function createAbortError(): Error {
  const error = new Error('The operation was aborted');
  error.name = 'AbortError';
  return error;
}

function normalizeBody(body: RequestInit['body']): Uint8Array | undefined {
  if (body === undefined || body === null) {
    return undefined;
  }
  if (typeof body === 'string') {
    return new TextEncoder().encode(body);
  }
  if (Buffer.isBuffer(body)) {
    return new Uint8Array(body);
  }
  if (body instanceof Uint8Array) {
    return body;
  }
  return new TextEncoder().encode(String(body));
}

export function createTimeoutSignal(timeoutMs: number, parentSignal?: AbortSignal): {
  signal: AbortSignal;
  cleanup(): void;
} {
  const controller = new AbortController();

  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let removeParentListener: (() => void) | undefined;

  if (parentSignal) {
    if (parentSignal.aborted) {
      controller.abort();
    } else {
      const onAbort = () => controller.abort();
      parentSignal.addEventListener('abort', onAbort, { once: true });
      removeParentListener = () => parentSignal.removeEventListener('abort', onAbort);
    }
  }

  return {
    signal: controller.signal,
    cleanup() {
      if (timer) {
        clearTimeout(timer);
      }
      removeParentListener?.();
    },
  };
}

export async function fetchCompat(
  url: string,
  init: RequestInit = {}
): Promise<FetchCompatResponse> {
  const requestBody = normalizeBody(init.body);
  const headers = { ...(init.headers as Record<string, string> | undefined) };

  if (requestBody && headers && headers['Content-Length'] === undefined) {
    headers['Content-Length'] = String(requestBody.byteLength);
  }

  if (typeof globalThis.fetch === 'function') {
    const response = await globalThis.fetch(url, {
      ...init,
      headers,
      body: requestBody as BodyInit | undefined,
    });
    return response as FetchCompatResponse;
  }

  return await new Promise<FetchCompatResponse>((resolve, reject) => {
    const target = new URL(url);
    const transport = target.protocol === 'https:' ? https : http;
    const request = transport.request(
      {
        protocol: target.protocol,
        hostname: target.hostname,
        port: target.port || undefined,
        path: `${target.pathname}${target.search}`,
        method: init.method ?? 'GET',
        headers,
      },
      (response) => {
        const chunks: Buffer[] = [];
        response.on('data', (chunk) => {
          chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
        });
        response.on('end', () => {
          const payload = Buffer.concat(chunks).toString('utf8');
          resolve({
            ok: (response.statusCode ?? 0) >= 200 && (response.statusCode ?? 0) < 300,
            status: response.statusCode ?? 0,
            statusText: response.statusMessage ?? '',
            async text() {
              return payload;
            },
            async json<T = unknown>() {
              return JSON.parse(payload) as T;
            },
          });
        });
      }
    );

    request.on('error', reject);

    if (init.signal) {
      if (init.signal.aborted) {
        request.destroy(createAbortError());
        return;
      }
      const onAbort = () => request.destroy(createAbortError());
      init.signal.addEventListener('abort', onAbort, { once: true });
      request.on('close', () => init.signal?.removeEventListener('abort', onAbort));
    }

    if (requestBody) {
      request.write(Buffer.from(requestBody));
    }

    request.end();
  });
}

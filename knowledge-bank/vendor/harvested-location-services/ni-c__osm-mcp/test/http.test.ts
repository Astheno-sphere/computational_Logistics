import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  HttpClient,
  OsmApiError,
  RateLimiter,
  Semaphore,
  TtlCache,
  sanitizeErrorBody,
  upstreamText,
} from '../src/http.js';

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('RateLimiter', () => {
  it('spaces calls by the configured interval', async () => {
    let clock = 0;
    const sleeps: number[] = [];
    const limiter = new RateLimiter(
      1000,
      () => clock,
      (ms) => {
        sleeps.push(ms);
        clock += ms;
        return Promise.resolve();
      }
    );
    await limiter.acquire(); // first call: free
    await limiter.acquire(); // 1000 ms later
    await limiter.acquire();
    expect(sleeps).toEqual([1000, 1000]);
  });

  it('does not sleep when enough time has passed', async () => {
    let clock = 0;
    const sleeps: number[] = [];
    const limiter = new RateLimiter(
      1000,
      () => clock,
      (ms) => {
        sleeps.push(ms);
        return Promise.resolve();
      }
    );
    await limiter.acquire();
    clock += 5000;
    await limiter.acquire();
    expect(sleeps).toEqual([]);
  });
});

describe('Semaphore', () => {
  it('caps concurrency and wakes waiters', async () => {
    const semaphore = new Semaphore(2);
    const r1 = await semaphore.acquire();
    await semaphore.acquire();
    let third = false;
    const pending = semaphore.acquire().then((release) => {
      third = true;
      release();
    });
    await Promise.resolve();
    expect(third).toBe(false);
    r1();
    await pending;
    expect(third).toBe(true);
  });
});

describe('TtlCache', () => {
  it('expires entries after the TTL', () => {
    let clock = 0;
    const cache = new TtlCache(1000, 10, () => clock);
    cache.set('a', 1);
    expect(cache.get('a')).toBe(1);
    clock = 1001;
    expect(cache.get('a')).toBeUndefined();
  });

  it('evicts the oldest entry at the cap', () => {
    const cache = new TtlCache(1000, 2, () => 0);
    cache.set('a', 1);
    cache.set('b', 2);
    cache.set('c', 3);
    expect(cache.get('a')).toBeUndefined();
    expect(cache.get('b')).toBe(2);
    expect(cache.get('c')).toBe(3);
  });

  it('stores nothing with a zero TTL', () => {
    const cache = new TtlCache(0, 10, () => 0);
    cache.set('a', 1);
    expect(cache.get('a')).toBeUndefined();
  });

  it('evicts oldest entries once the byte budget is exceeded', () => {
    const cache = new TtlCache(1000, 10, () => 0, 100);
    cache.set('a', 'A', 60);
    cache.set('b', 'B', 50);
    expect(cache.get('a')).toBeUndefined();
    expect(cache.get('b')).toBe('B');
  });

  it('never admits a single entry larger than the byte budget', () => {
    const cache = new TtlCache(1000, 10, () => 0, 100);
    cache.set('big', 'X', 500);
    expect(cache.get('big')).toBeUndefined();
  });

  it('frees the byte budget when an entry is overwritten', () => {
    const cache = new TtlCache(1000, 10, () => 0, 100);
    cache.set('a', 'A1', 90);
    cache.set('a', 'A2', 90);
    cache.set('b', 'B', 10);
    expect(cache.get('a')).toBe('A2');
    expect(cache.get('b')).toBe('B');
  });
});

describe('HttpClient', () => {
  it('sends the User-Agent and caches identical requests', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }));
    vi.stubGlobal('fetch', fetchMock);
    const http = new HttpClient('test-agent/1.0', 60_000);
    const first = await http.request('svc', 'https://example.com/x', null);
    const second = await http.request('svc', 'https://example.com/x', null);
    expect(first).toEqual({ ok: true });
    expect(second).toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const init = fetchMock.mock.calls[0]![1] as RequestInit;
    expect((init.headers as Record<string, string>)['User-Agent']).toBe(
      'test-agent/1.0'
    );
    expect(init.redirect).toBe('error');
  });

  it('bypasses the cache with noCache', async () => {
    const fetchMock = vi
      .fn()
      .mockImplementation(async () => jsonResponse({ ok: true }));
    vi.stubGlobal('fetch', fetchMock);
    const http = new HttpClient('a', 60_000);
    await http.request('svc', 'https://example.com/x', null, { noCache: true });
    await http.request('svc', 'https://example.com/x', null, { noCache: true });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('throws OsmApiError with the status on failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response('slow down', { status: 429 }))
    );
    const http = new HttpClient('a', 0);
    await expect(
      http.request('nominatim', 'https://example.com/x', null)
    ).rejects.toMatchObject({ status: 429, service: 'nominatim' });
  });

  it('redacts api_key query values in error messages', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response('no', { status: 500 }))
    );
    const http = new HttpClient('a', 0);
    const error = await http
      .request('svc', 'https://example.com/x?api_key=SECRET&y=1', null)
      .then(
        () => null,
        (e: unknown) => e as OsmApiError
      );
    expect(error?.message).not.toContain('SECRET');
    expect(error?.message).toContain('[redacted]');
  });

  it('parses JSON served without a JSON content type', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response('{"a":1}', { status: 200 }))
    );
    const http = new HttpClient('a', 0);
    expect(await http.request('svc', 'https://example.com/x', null)).toEqual({
      a: 1,
    });
  });
});

describe('sanitizeErrorBody', () => {
  it('drops markup that does not open with a doctype or <html>', () => {
    // A WAF block page can open with a comment, and an upstream that answers
    // errors in XML is exactly as useless to the model as one that answers in
    // HTML. The old check required a doctype or an <html> tag first and let
    // both of these through.
    expect(
      sanitizeErrorBody('<?xml version="1.0"?><error>denied</error>')
    ).toBe('(HTML error page omitted)');
    expect(
      sanitizeErrorBody('<!-- blocked by policy -->\n<html>x</html>')
    ).toBe('(HTML error page omitted)');
  });
  it('drops HTML error pages', () => {
    expect(sanitizeErrorBody('<html><body>boom</body></html>')).toBe(
      '(HTML error page omitted)'
    );
  });

  it('truncates long bodies', () => {
    expect(sanitizeErrorBody('x'.repeat(5000))).toMatch(/… \(truncated\)$/);
  });

  it('strips control characters and BiDi overrides', () => {
    // This function promises a body that is safe to concatenate into the model
    // context, and the caller does concatenate it with no JSON encoding in
    // between. It only ever dropped markup and length; an ANSI escape or a
    // U+202E went through untouched, from an endpoint this project does not run.
    const body = sanitizeErrorBody(
      'denied\u009b[2J\u202ereversed\u007f\u200fmark'
    );
    // The escape *introducer* is gone; the `[2J` it would have steered is left
    // as the ordinary text it now is.
    expect(body).toBe('denied[2Jreversedmark');
    expect(body).not.toMatch(/[\u007f-\u009f\u200e\u200f\u202a-\u202e]/);
  });
});

describe('audit regressions', () => {
  it('semaphore does not over-admit when a release races a fresh acquire', async () => {
    const semaphore = new Semaphore(2);
    const r1 = await semaphore.acquire();
    const r2 = await semaphore.acquire();
    let thirdIn = false;
    let fourthIn = false;
    const p3 = semaphore.acquire().then((release) => {
      thirdIn = true;
      return release;
    });
    r1(); // hands the slot to waiter 3
    // A fresh acquire in the same microtask window must NOT slip in.
    const p4 = semaphore.acquire().then((release) => {
      fourthIn = true;
      return release;
    });
    await Promise.resolve();
    await Promise.resolve();
    expect(thirdIn).toBe(true);
    expect(fourthIn).toBe(false);
    r2();
    const r4 = await p4;
    expect(fourthIn).toBe(true);
    (await p3)();
    r4();
  });

  it('rate limiter rejects beyond the queue depth cap', async () => {
    const clock = 0;
    const limiter = new RateLimiter(
      1000,
      () => clock,
      () => new Promise(() => {}), // never resolves — keeps the queue full
      2
    );
    const first = limiter.acquire();
    const second = limiter.acquire();
    await expect(limiter.acquire()).rejects.toThrow(/queue.*full/i);
    void first;
    void second;
  });

  it('redacts token-style query parameters, not only api_key', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response('no', { status: 500 }))
    );
    const http = new HttpClient('a', 0);
    const error = await http
      .request(
        'svc',
        'https://example.com/x?token=SECRET&access_token=ALSO',
        null
      )
      .then(
        () => null,
        (e: unknown) => e as OsmApiError
      );
    expect(error?.message).not.toContain('SECRET');
    expect(error?.message).not.toContain('ALSO');
  });

  it('rejects responses whose declared size exceeds the cap', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response('x', {
          status: 200,
          headers: { 'content-length': String(99 * 1024 * 1024) },
        })
      )
    );
    const http = new HttpClient('a', 0);
    await expect(
      http.request('svc', 'https://example.com/x', null)
    ).rejects.toThrow(/too large/);
  });
});

describe('review 2026-09-07', () => {
  it('decides on the status before reading the body', async () => {
    // A 5xx with a body past the data cap is a 5xx, not a size error: the
    // status is what the Overpass failover and the 429 hint are keyed on.
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          new Response('x'.repeat(9 * 1024 * 1024), { status: 503 })
        )
    );
    const http = new HttpClient('a', 0);
    await expect(
      http.request('overpass', 'https://example.com/x', null)
    ).rejects.toMatchObject({ status: 503, service: 'overpass' });
  });

  it('does not refuse an error answer for its declared size', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response('denied', {
          status: 401,
          headers: { 'content-length': String(99 * 1024 * 1024) },
        })
      )
    );
    const http = new HttpClient('a', 0);
    await expect(
      http.request('svc', 'https://example.com/x', null)
    ).rejects.toMatchObject({ status: 401, body: 'denied' });
  });

  it('cuts an error body at 64 KiB instead of refusing it', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(new Response('e'.repeat(200_000), { status: 500 }))
    );
    const http = new HttpClient('a', 0);
    const error = await http.request('svc', 'https://example.com/x', null).then(
      () => null,
      (e: unknown) => e as OsmApiError
    );
    expect(error?.status).toBe(500);
    expect(error?.body).toHaveLength(64 * 1024);
  });

  it('still caps the body of a successful answer', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          new Response('x'.repeat(9 * 1024 * 1024), { status: 200 })
        )
    );
    const http = new HttpClient('a', 0);
    await expect(
      http.request('svc', 'https://example.com/x', null)
    ).rejects.toThrow(/exceeded the .* cap/);
  });

  it('labels, cleans and cuts text the service wrote', () => {
    expect(upstreamText('NoRoute')).toBe(
      '(untrusted text from the service) NoRoute'
    );
    expect(upstreamText(`${String.fromCharCode(27)}[2J bad ?key=SECRET`)).toBe(
      '(untrusted text from the service) [2J bad ?key=[redacted]'
    );
    expect(upstreamText('x'.repeat(1000), 20)).toBe(
      `(untrusted text from the service) ${'x'.repeat(20)}… (truncated)`
    );
    expect(upstreamText(undefined)).toBe('(none)');
    expect(upstreamText({ a: 1 })).toBe('(non-text value of type object)');
  });
});

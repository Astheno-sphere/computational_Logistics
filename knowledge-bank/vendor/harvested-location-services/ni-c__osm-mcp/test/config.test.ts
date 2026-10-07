import { describe, expect, it } from 'vitest';

import { ConfigError, loadConfig } from '../src/config.js';

function env(values: Record<string, string> = {}): NodeJS.ProcessEnv {
  return { ...values } as NodeJS.ProcessEnv;
}

describe('loadConfig', () => {
  it('starts with public defaults and no key', () => {
    const config = loadConfig(env());
    expect(config.nominatimUrl).toBe('https://nominatim.openstreetmap.org');
    expect(config.photonUrl).toBe('https://photon.komoot.io');
    expect(config.osrmUrl).toBe('https://routing.openstreetmap.de');
    expect(config.valhallaUrl).toBe('https://valhalla1.openstreetmap.de');
    expect(config.overpassUrls).toEqual([
      'https://overpass-api.de/api/interpreter',
      'https://lz4.overpass-api.de/api/interpreter',
    ]);
    expect(config.orsApiKey).toBeUndefined();
    expect(config.cacheTtlMs).toBe(3_600_000);
    expect(config.userAgent).toMatch(/^osm-mcp\/\d+\.\d+\.\d+ \(\+https:/);
  });

  it('removes the ORS key from the environment after reading it', () => {
    const e = env({ ORS_API_KEY: 'test-secret-0123456789' });
    const config = loadConfig(e);
    expect(config.orsApiKey).toBe('test-secret-0123456789');
    expect(e.ORS_API_KEY).toBeUndefined();
  });

  it('accepts overrides and strips trailing slashes', () => {
    const config = loadConfig(
      env({
        OSRM_BASE_URL: 'https://osrm.internal.example//',
        OVERPASS_BASE_URL: 'https://a.example/api, https://b.example/api ,',
        OSM_USER_AGENT: 'my-agent/1.0',
        OSM_CACHE_TTL: '60',
      })
    );
    expect(config.osrmUrl).toBe('https://osrm.internal.example');
    expect(config.overpassUrls).toEqual([
      'https://a.example/api',
      'https://b.example/api',
    ]);
    expect(config.userAgent).toBe('my-agent/1.0');
    expect(config.cacheTtlMs).toBe(60_000);
  });

  it('rejects invalid URLs, non-http protocols and embedded credentials', () => {
    expect(() => loadConfig(env({ NOMINATIM_BASE_URL: 'not a url' }))).toThrow(
      ConfigError
    );
    expect(() =>
      loadConfig(env({ VALHALLA_BASE_URL: 'ftp://example.com' }))
    ).toThrow(/http/);
    expect(() =>
      loadConfig(env({ ORS_BASE_URL: 'https://user:pass@example.com' }))
    ).toThrow(/credentials/);
  });

  it('rejects a non-numeric cache TTL', () => {
    expect(() => loadConfig(env({ OSM_CACHE_TTL: 'soon' }))).toThrow(
      ConfigError
    );
  });
});

describe('audit regressions', () => {
  it('refuses to send the ORS key over cleartext http', () => {
    expect(() =>
      loadConfig(
        env({
          ORS_API_KEY: 'test-key-0123456789',
          ORS_BASE_URL: 'http://ors.example.com',
        })
      )
    ).toThrow(/https/);
    // http to loopback is fine (local ORS instance)
    const config = loadConfig(
      env({
        ORS_API_KEY: 'test-key-0123456789',
        ORS_BASE_URL: 'http://localhost:8080',
      })
    );
    expect(config.orsUrl).toBe('http://localhost:8080');
  });

  it('deletes the ORS key even when a validation throws', () => {
    // Regression (audiobookshelf-mcp PR #2): with the delete behind a throwing
    // branch, a caller that catches the ConfigError would keep running with the
    // key still in the environment — readable in /proc/<pid>/environ and
    // inherited by child processes.
    const e = env({
      ORS_API_KEY: 'test-secret-0123456789',
      OSM_CACHE_TTL: 'soon',
    });
    expect(() => loadConfig(e)).toThrow(ConfigError);
    expect(e.ORS_API_KEY).toBeUndefined();
  });

  it('does not echo the offending value in URL and TTL error messages', () => {
    // An API key pasted into the wrong variable must not land verbatim in the
    // MCP host's log via the error message.
    for (const bad of [
      env({ ORS_BASE_URL: 'sekret-looking-value' }),
      env({ NOMINATIM_BASE_URL: 'sekret-looking-value' }),
      env({ OSM_CACHE_TTL: 'sekret-looking-value' }),
    ]) {
      let message = '';
      try {
        loadConfig(bad);
      } catch (error) {
        message = (error as Error).message;
      }
      expect(message).not.toBe('');
      expect(message).not.toContain('sekret-looking-value');
    }
  });

  it('treats bracketed IPv6 loopback as local for the ORS https requirement', () => {
    const config = loadConfig(
      env({
        ORS_API_KEY: 'test-key-0123456789',
        ORS_BASE_URL: 'http://[::1]:8080',
      })
    );
    expect(config.orsUrl).toBe('http://[::1]:8080');
  });

  it('rejects base URLs carrying a query string or fragment', () => {
    expect(() =>
      loadConfig(env({ OSRM_BASE_URL: 'https://example.com/?key=x' }))
    ).toThrow(/query string/);
    expect(() =>
      loadConfig(env({ VALHALLA_BASE_URL: 'https://example.com/#frag' }))
    ).toThrow(/query string/);
  });
});

describe('review 2026-09-07', () => {
  it('trims trailing slashes in linear time', () => {
    // `/\/+$/` was tried from every slash of the run: 80 000 of them followed
    // by one letter cost almost two seconds at startup.
    const started = performance.now();
    const config = loadConfig(
      env({ NOMINATIM_BASE_URL: `https://x.example/${'/'.repeat(80_000)}a` })
    );
    expect(performance.now() - started).toBeLessThan(1000);
    expect(config.nominatimUrl.endsWith('/a')).toBe(true);
    expect(
      loadConfig(env({ OSRM_BASE_URL: 'https://x.example/path///' })).osrmUrl
    ).toBe('https://x.example/path');
  });

  it('quotes at most 40 visible characters of a scheme it refuses', () => {
    // A hexadecimal key with a colon after it is a valid URL whose scheme is
    // the key, and the error used to print the scheme in full.
    const key = 'abcdef0123456789'.repeat(4);
    let message = '';
    try {
      loadConfig(env({ ORS_BASE_URL: `${key}:` }));
    } catch (error) {
      message = (error as Error).message;
    }
    expect(message).toMatch(/must use http/);
    expect(message).not.toContain(key);
    expect(message).toContain(`${key.slice(0, 40)}…`);
  });

  it('refuses an ORS key that could not travel in a header, without echoing it', () => {
    const bad = [
      `abc${String.fromCharCode(10)}def12345`,
      'short',
      'k'.repeat(300),
      'has a space in it',
    ];
    for (const key of bad) {
      let message = '';
      try {
        loadConfig(env({ ORS_API_KEY: key }));
      } catch (error) {
        message = (error as Error).message;
      }
      expect(message).toMatch(/ORS_API_KEY must be/);
      expect(message).not.toContain(key);
    }
    expect(
      loadConfig(env({ ORS_API_KEY: '5b3ce3597851110001cf6248' })).orsApiKey
    ).toBe('5b3ce3597851110001cf6248');
  });

  it('caps the Overpass mirror list and refuses an empty one', () => {
    const many = Array.from(
      { length: 9 },
      (_, i) => `https://m${i}.example/api`
    ).join(',');
    expect(() => loadConfig(env({ OVERPASS_BASE_URL: many }))).toThrow(
      /9 endpoints; at most 8/
    );
    expect(() => loadConfig(env({ OVERPASS_BASE_URL: ' , ' }))).toThrow(
      /at least one/
    );
    expect(
      loadConfig(
        env({ OVERPASS_BASE_URL: many.split(',').slice(0, 8).join(',') })
      ).overpassUrls
    ).toHaveLength(8);
  });
});

import { describe, it, expect } from "vitest";
import { createTestContext, jsonFetch, mockJson, statusFetch } from "@geowirehq/provider-testkit";
import { createOsrmProvider } from "../src/index.js";

const routeBody = {
  code: "Ok",
  routes: [
    {
      distance: 9949.4,
      duration: 598.4,
      legs: [
        { distance: 5000, duration: 300 },
        { distance: 4949.4, duration: 298.4 },
      ],
      geometry: {
        type: "LineString",
        coordinates: [
          [126.978, 37.5665],
          [127.0276, 37.4979],
        ],
      },
    },
  ],
};

const tableBody = {
  code: "Ok",
  durations: [
    [598.4, 700.1],
    [610.0, 0],
  ],
  distances: [
    [9949.4, 10857.4],
    [10100.0, 0],
  ],
};

/** URL·헤더를 잡아 검사하는 fetch */
function capture(body: unknown): { fetch: typeof globalThis.fetch; urls: string[] } {
  const urls: string[] = [];
  const fetch = (async (input: string | URL) => {
    urls.push(String(input));
    return mockJson(body);
  }) as unknown as typeof globalThis.fetch;
  return { fetch, urls };
}

describe("createOsrmProvider — route", () => {
  const provider = createOsrmProvider();

  it("경로의 총 거리·시간·구간을 파싱한다", async () => {
    const ctx = createTestContext(jsonFetch(routeBody));
    const routes = await provider.route!(
      {
        waypoints: [
          { latitude: 37.5665, longitude: 126.978 },
          { latitude: 37.4979, longitude: 127.0276 },
        ],
        mode: "driving",
        alternatives: false,
        geometry: false,
      },
      ctx,
    );
    expect(routes).toHaveLength(1);
    expect(routes[0]!.distanceMeters).toBe(9949.4);
    expect(routes[0]!.durationSeconds).toBe(598.4);
    expect(routes[0]!.legs).toEqual([
      { distanceMeters: 5000, durationSeconds: 300 },
      { distanceMeters: 4949.4, durationSeconds: 298.4 },
    ]);
    // geometry:false면 폴리라인 미포함
    expect(routes[0]!.geometry).toBeUndefined();
  });

  it("geometry:true면 GeoJSON LineString을 포함한다", async () => {
    const ctx = createTestContext(jsonFetch(routeBody));
    const routes = await provider.route!(
      {
        waypoints: [
          { latitude: 37.5665, longitude: 126.978 },
          { latitude: 37.4979, longitude: 127.0276 },
        ],
        mode: "driving",
        alternatives: false,
        geometry: true,
      },
      ctx,
    );
    expect(routes[0]!.geometry?.type).toBe("LineString");
    expect(routes[0]!.geometry?.coordinates).toHaveLength(2);
  });

  it("좌표를 경도,위도 순서(GeoJSON 규약)로 보낸다", async () => {
    const { fetch, urls } = capture(routeBody);
    await provider.route!(
      {
        waypoints: [
          { latitude: 37.5665, longitude: 126.978 },
          { latitude: 37.4979, longitude: 127.0276 },
        ],
        mode: "driving",
        alternatives: false,
        geometry: false,
      },
      createTestContext(fetch),
    );
    // /route/v1/driving/{lng},{lat};{lng},{lat}
    expect(urls[0]).toContain("/route/v1/driving/126.978,37.5665;127.0276,37.4979");
  });

  it("NoRoute는 에러가 아니라 빈 결과(폴백 유도)", async () => {
    const ctx = createTestContext(jsonFetch({ code: "NoRoute", routes: [] }));
    const routes = await provider.route!(
      {
        waypoints: [
          { latitude: 0, longitude: 0 },
          { latitude: 1, longitude: 1 },
        ],
        mode: "driving",
        alternatives: false,
        geometry: false,
      },
      ctx,
    );
    expect(routes).toEqual([]);
  });

  it("HTTP 429는 정규화된 에러로 던진다", async () => {
    const ctx = createTestContext(statusFetch(429), { retries: 0 });
    await expect(
      provider.route!(
        {
          waypoints: [
            { latitude: 0, longitude: 0 },
            { latitude: 1, longitude: 1 },
          ],
          mode: "driving",
          alternatives: false,
          geometry: false,
        },
        ctx,
      ),
    ).rejects.toMatchObject({ code: "RATE_LIMITED" });
  });
});

describe("createOsrmProvider — distanceMatrix", () => {
  const provider = createOsrmProvider();

  it("origins×destinations 거리/시간 행렬을 만든다", async () => {
    const ctx = createTestContext(jsonFetch(tableBody));
    const m = await provider.distanceMatrix!(
      {
        origins: [
          { latitude: 37.57, longitude: 126.98 },
          { latitude: 37.5, longitude: 127.0 },
        ],
        destinations: [
          { latitude: 37.49, longitude: 127.02 },
          { latitude: 37.51, longitude: 127.05 },
        ],
        mode: "driving",
      },
      ctx,
    );
    expect(m.rows).toHaveLength(2);
    expect(m.rows[0]).toHaveLength(2);
    expect(m.rows[0]![0]).toEqual({ distanceMeters: 9949.4, durationSeconds: 598.4 });
    expect(m.rows[1]![1]).toEqual({ distanceMeters: 0, durationSeconds: 0 });
  });

  it("sources/destinations 인덱스를 분리해 보낸다", async () => {
    const { fetch, urls } = capture(tableBody);
    await provider.distanceMatrix!(
      {
        origins: [{ latitude: 37.57, longitude: 126.98 }],
        destinations: [
          { latitude: 37.49, longitude: 127.02 },
          { latitude: 37.51, longitude: 127.05 },
        ],
        mode: "driving",
      },
      createTestContext(fetch),
    );
    const url = new URL(urls[0]!);
    expect(url.searchParams.get("sources")).toBe("0");
    expect(url.searchParams.get("destinations")).toBe("1;2");
    expect(url.searchParams.get("annotations")).toBe("duration,distance");
  });
});

// tests/WeatherDailyTool.test.ts
import { inputSchema, handler } from "../src/tools/WeatherDailyTool";
import axios from "axios";
import type { RequestHandlerExtra } from "@modelcontextprotocol/sdk/shared/protocol.js";

jest.mock("axios");
const mockedAxios = axios as jest.Mocked<typeof axios>;

beforeAll(() => {
  // Make axios.isAxiosError always return true for our error‐tests
  jest.spyOn(axios, "isAxiosError").mockReturnValue(true);
});

describe("WeatherDailyTool handler", () => {
  const validArgs = {
    location: "Paris",
    days: 5,
    units: "metric"
  };
  const extra: RequestHandlerExtra<any, any> = {
    signal: new AbortController().signal,
    requestId: "req-1",
    sendNotification: jest.fn(),
    sendRequest: jest.fn(),
  };

  const originalApiKey = process.env.ACCUWEATHER_API_KEY;

  beforeEach(() => {
    process.env.ACCUWEATHER_API_KEY = "dummy-key";
    mockedAxios.get.mockReset();
  });

  afterAll(() => {
    // restore env
    if (originalApiKey) process.env.ACCUWEATHER_API_KEY = originalApiKey;
    else delete process.env.ACCUWEATHER_API_KEY;
  });

  it("passes zod validation for well-formed input", () => {
    expect(() => inputSchema.parse(validArgs)).not.toThrow();
  });

  it("accepts requests with minimal required parameters", () => {
    const result = inputSchema.parse({
      location: validArgs.location
    });
    // Just verify parsing doesn't throw an error
    expect(result.location).toBe(validArgs.location);
    // The handler will use default values for days (5) and units ("metric")
  });

  it("rejects when location is empty", () => {
    expect(() =>
      inputSchema.parse({ 
        location: "",
        days: 5,
        units: "metric"
      })
    ).toThrow(/Location must be at least 1 character/);
  });

  it("fetches location key and daily forecast and formats text", async () => {
    // location-search API
    mockedAxios.get
      .mockResolvedValueOnce({ data: [{ Key: "LOC123" }] })
      // forecast API
      .mockResolvedValueOnce({
        data: {
          DailyForecasts: [
            {
              Date: "2025-05-04T07:00:00+02:00",
              Temperature: { 
                Minimum: { Value: 15, Unit: "C" },
                Maximum: { Value: 25, Unit: "C" }
              },
              Day: {
                IconPhrase: "Partly sunny",
                HasPrecipitation: false
              },
              Night: {
                IconPhrase: "Mostly clear",
                HasPrecipitation: false
              }
            }
          ]
        }
      });

    const result = await handler(validArgs, extra);

    // two calls: one for cities/search, one for daily forecast
    expect(mockedAxios.get).toHaveBeenCalledTimes(2);
    expect(mockedAxios.get).toHaveBeenCalledWith(
      expect.stringContaining("locations/v1/cities/search")
    );
    expect(mockedAxios.get).toHaveBeenCalledWith(
      expect.stringContaining("forecasts/v1/daily/5day/LOC123")
    );
    expect(mockedAxios.get).toHaveBeenCalledWith(
      expect.stringContaining("metric=true")
    );

    // one text item in content array
    expect(result.content).toHaveLength(1);
    expect(result.content[0].text).toContain("15°C to 25°C");
    expect(result.content[0].text).toContain("Day: Partly sunny");
    expect(result.content[0].text).toContain("Night: Mostly clear");
  });

  it("handles unit preferences correctly", async () => {
    // location-search API
    mockedAxios.get
      .mockResolvedValueOnce({ data: [{ Key: "LOC123" }] })
      // forecast API
      .mockResolvedValueOnce({
        data: {
          DailyForecasts: [
            {
              Date: "2025-05-04T07:00:00+02:00",
              Temperature: { 
                Minimum: { Value: 59, Unit: "F" },
                Maximum: { Value: 77, Unit: "F" }
              },
              Day: {
                IconPhrase: "Partly sunny",
                HasPrecipitation: false
              },
              Night: {
                IconPhrase: "Mostly clear",
                HasPrecipitation: false
              }
            }
          ]
        }
      });

    const result = await handler({
      ...validArgs,
      units: "imperial"
    }, extra);

    expect(mockedAxios.get).toHaveBeenCalledTimes(2);
    expect(mockedAxios.get).toHaveBeenCalledWith(
      expect.stringContaining("metric=false")
    );

    expect(result.content[0].text).toContain("59°F to 77°F");
  });

  it("adjusts the forecast days correctly", async () => {
    mockedAxios.get
      .mockResolvedValueOnce({ data: [{ Key: "LOC123" }] })
      .mockResolvedValueOnce({
        data: { DailyForecasts: [] }
      });

    // Test with days=1
    await handler({
      ...validArgs,
      days: 1
    }, extra);
    expect(mockedAxios.get).toHaveBeenCalledWith(
      expect.stringContaining("forecasts/v1/daily/1day/LOC123")
    );
    
    mockedAxios.get.mockReset();
    mockedAxios.get
      .mockResolvedValueOnce({ data: [{ Key: "LOC123" }] })
      .mockResolvedValueOnce({
        data: { DailyForecasts: [] }
      });

    // Test with days=10
    await handler({
      ...validArgs,
      days: 10
    }, extra);
    expect(mockedAxios.get).toHaveBeenCalledWith(
      expect.stringContaining("forecasts/v1/daily/10day/LOC123")
    );
  });

  it("handles no-location-found", async () => {
    mockedAxios.get.mockResolvedValueOnce({ data: [] });
    const resp = await handler(validArgs, extra);
    expect(mockedAxios.get).toHaveBeenCalledTimes(1);
    expect(resp.content[0].text).toBe("No location found for: Paris");
  });
}); 
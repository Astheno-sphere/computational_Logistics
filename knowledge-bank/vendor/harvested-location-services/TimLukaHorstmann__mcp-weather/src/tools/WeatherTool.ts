import { z } from "zod";
import axios from "axios";
import type { TextContent } from "@modelcontextprotocol/sdk/types.js";
import type { RequestHandlerExtra } from "@modelcontextprotocol/sdk/shared/protocol.js";

// Zod schemas for validation
export const inputShape = {
  location: z.string().min(1, "Location must be at least 1 character"),
  units: z.enum(["imperial", "metric"]).default("metric").optional().describe("Temperature unit system")
};

export const inputSchema = z.object(inputShape).describe("Get hourly weather forecast");

// JSON schema for tool registration (OpenAI-compatible)
export const inputJsonSchema = {
  type: "object",
  description: "Parameters for the hourly weather-forecast tool",
  properties: {
    location: {
      type: "string",
      description: "The location to fetch the 12-hour forecast for",
    },
    units: {
      type: "string",
      description: "Temperature unit system (metric for Celsius, imperial for Fahrenheit). Default is metric.",
      enum: ["metric", "imperial"]
    }
  },
  required: ["location"],
  additionalProperties: false,
};

// Handler function remains unchanged
export async function handler(
  args: { [x: string]: any },
  extra: RequestHandlerExtra<any, any>
): Promise<{ content: TextContent[] }> {
  // Validate args using the Zod schema
  let validatedArgs: z.infer<typeof inputSchema>;
  try {
    validatedArgs = inputSchema.parse(args);
  } catch (error) {
    if (error instanceof z.ZodError) {
      const errorMessages = error.errors
        .map((e) => `${e.path.join('.')}: ${e.message}`)
        .join(', ');
      return { content: [{ type: 'text', text: `Invalid input: ${errorMessages}` }] };
    }
    return { content: [{ type: 'text', text: 'An unexpected error occurred during input validation.' }] };
  }

  const { location, units = "metric" } = validatedArgs;
  const apiKey = process.env.ACCUWEATHER_API_KEY;
  if (!apiKey) {
    return { content: [{ type: 'text', text: 'Error: AccuWeather API key not configured' }] };
  }

  try {
    // Step 1: Get location key
    const locationUrl = `https://dataservice.accuweather.com/locations/v1/cities/search?apikey=${apiKey}&q=${encodeURIComponent(location)}`;
    const locationResp = await axios.get(locationUrl);

    if (!locationResp.data || locationResp.data.length === 0) {
      return { content: [{ type: 'text', text: `No location found for: ${location}` }] };
    }

    const locationKey = locationResp.data[0].Key;

    // Step 2: Get forecast with location key
    const forecastUrl = `https://dataservice.accuweather.com/forecasts/v1/hourly/12hour/${locationKey}?apikey=${apiKey}&metric=${units === "metric" ? "true" : "false"}`;
    const forecastResp = await axios.get(forecastUrl);
    const data = forecastResp.data;

    if (!data || !Array.isArray(data) || data.length === 0) {
      return {
        content: [{ type: 'text', text: `No weather data available for location: ${location}` }]
      };
    }

    const unitSymbol = units === "metric" ? "C" : "F";
    const content: TextContent[] = data.map((hour: any) => ({
      type: 'text',
      text: `${hour.DateTime}: ${hour.Temperature.Value}°${unitSymbol}, ${hour.IconPhrase}`,
    }));

    return { content };
  } catch (error) {
    console.error("WeatherTool handler error:", error);
    let errorMessage = "An error occurred while fetching weather data.";

    if (axios.isAxiosError(error)) {
      if (error.response?.status === 401) {
        errorMessage = "Invalid AccuWeather API key. Please check your credentials.";
      } else if (error.response?.status === 404) {
        errorMessage = `Location not found: ${location}`;
      } else if (error.response) {
        errorMessage = `AccuWeather API error (${error.response.status}): ${error.response.data?.Message || error.message}`;
      } else if (error.request) {
        errorMessage = "Network error: Unable to connect to AccuWeather API.";
      }
    }

    return { content: [{ type: 'text', text: errorMessage }] };
  }
}

export default { inputShape, inputSchema, inputJsonSchema, handler };

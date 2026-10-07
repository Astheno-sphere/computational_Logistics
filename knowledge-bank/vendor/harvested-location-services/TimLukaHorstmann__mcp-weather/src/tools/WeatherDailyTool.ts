import { z } from "zod";
import axios from "axios";
import type { TextContent } from "@modelcontextprotocol/sdk/types.js";
import type { RequestHandlerExtra } from "@modelcontextprotocol/sdk/shared/protocol.js";

// Zod schemas for validation
export const inputShape = {
  location: z.string().min(1, "Location must be at least 1 character"),
  days: z.number().int().min(1).max(15).default(5).optional().describe("Number of days for forecast (1-15)"),
  units: z.enum(["imperial", "metric"]).default("metric").optional().describe("Temperature unit system")
};

export const inputSchema = z.object(inputShape).describe("Get daily weather forecast");

// JSON schema for tool registration (OpenAI-compatible)
export const inputJsonSchema = {
  type: "object",
  description: "Parameters for the daily weather-forecast tool",
  properties: {
    location: {
      type: "string",
      description: "The location to fetch the daily forecast for",
    },
    days: {
      type: "number",
      description: "Number of days to forecast (1, 5, 10, or 15). Default is 5.",
      enum: [1, 5, 10, 15]
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

// Handler function for daily forecast
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

  const { location, days = 5, units = "metric" } = validatedArgs;
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

    // Get valid forecast period (AccuWeather supports 1, 5, 10, or 15 days)
    let forecastDays = 5; // default
    if (days === 1) forecastDays = 1;
    else if (days <= 5) forecastDays = 5;
    else if (days <= 10) forecastDays = 10;
    else forecastDays = 15;

    // Step 2: Get forecast with location key
    const forecastUrl = `https://dataservice.accuweather.com/forecasts/v1/daily/${forecastDays}day/${locationKey}?apikey=${apiKey}&metric=${units === "metric" ? "true" : "false"}`;
    const forecastResp = await axios.get(forecastUrl);
    const data = forecastResp.data;

    if (!data || !data.DailyForecasts || !Array.isArray(data.DailyForecasts) || data.DailyForecasts.length === 0) {
      return {
        content: [{ type: 'text', text: `No daily forecast data available for location: ${location}` }]
      };
    }

    const degreeSymbol = "°";
    const unitSymbol = units === "metric" ? "C" : "F";

    const content: TextContent[] = data.DailyForecasts.map((day: any) => {
      const date = new Date(day.Date);
      const formattedDate = date.toLocaleDateString('en-US', { 
        weekday: 'long', 
        year: 'numeric', 
        month: 'short', 
        day: 'numeric' 
      });
      
      return {
        type: 'text',
        text: `${formattedDate}: ${day.Temperature.Minimum.Value}${degreeSymbol}${unitSymbol} to ${day.Temperature.Maximum.Value}${degreeSymbol}${unitSymbol}, Day: ${day.Day.IconPhrase}, Night: ${day.Night.IconPhrase}${day.Day.HasPrecipitation || day.Night.HasPrecipitation ? ' (Precipitation expected)' : ''}`
      };
    });

    return { content };
  } catch (error) {
    console.error("WeatherDailyTool handler error:", error);
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
#!/usr/bin/env node
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

import {
  aqLatest,
  aqForecast48h,
  weatherLatest,
  weatherForecast48h,
  pollenLatest,
  pollenForecast48h,
  AmbeeApiError,
} from "./ambee-client.js";

if (!process.env.AMBEE_API_KEY) {
  console.error(
    "[ambee-mcp-server] Missing AMBEE_API_KEY environment variable. " +
      "Get a free key at https://api-dashboard.getambee.com and set it before starting the server."
  );
  process.exit(1);
}

const server = new McpServer({
  name: "ambee-mcp-server",
  version: "2.0.0",
});

// Shared by every /v3 endpoint: exactly one of (lat + lng) or place.
const locationFields = {
  lat: z
    .number()
    .min(-90)
    .max(90)
    .optional()
    .describe("Latitude of the location, -90 to 90. Required if place is not provided."),
  lng: z
    .number()
    .min(-180)
    .max(180)
    .optional()
    .describe("Longitude of the location, -180 to 180. Required if place is not provided."),
  place: z
    .string()
    .optional()
    .describe(
      "Place or city name, e.g. \"Bengaluru\". Required if lat/lng are not provided. Never send both place and lat/lng."
    ),
  locale: z
    .boolean()
    .optional()
    .describe("If true, the response includes a localTime field alongside each record."),
};

function toolResult(data, warning) {
  const payload = warning ? { warning, ...data } : data;
  return { content: [{ type: "text", text: JSON.stringify(payload, null, 2) }] };
}

function errorResult(err) {
  if (err instanceof AmbeeApiError) {
    return {
      content: [{ type: "text", text: err.message }],
      isError: true,
    };
  }
  return {
    content: [{ type: "text", text: `Error: ${err.message}` }],
    isError: true,
  };
}

async function run(fn, args) {
  try {
    const { body, warning } = await fn(args);
    return toolResult(body, warning);
  } catch (err) {
    return errorResult(err);
  }
}

server.registerTool(
  "air_quality_latest",
  {
    title: "Air Quality – Latest",
    description:
      "Returns the latest air quality reading for a location: AQI plus CO, NO2, ozone, PM10, " +
      "PM2.5, and SO2 concentrations, with the dominant pollutant and category. Returns a single " +
      "record for the current hour, or no data if none is available for that location.",
    inputSchema: {
      ...locationFields,
      aqiStandard: z
        .enum(["EPA", "IN", "UK", "CN", "CA"])
        .optional()
        .describe("AQI standard to calculate against. Defaults to EPA."),
    },
  },
  (args) => run(aqLatest, args)
);

server.registerTool(
  "air_quality_forecast",
  {
    title: "Air Quality – 48-Hour Forecast",
    description:
      "Returns an hourly air quality forecast for the next 48 hours: AQI plus CO, NO2, ozone, " +
      "PM10, PM2.5, and SO2 concentrations for each hour, with the dominant pollutant and " +
      "category. Returns up to 48 hourly records, or no data if none is available.",
    inputSchema: {
      ...locationFields,
      aqiStandard: z
        .enum(["EPA", "IN", "UK", "CN", "CA"])
        .optional()
        .describe("AQI standard to calculate against. Defaults to EPA."),
    },
  },
  (args) => run(aqForecast48h, args)
);

server.registerTool(
  "weather_latest",
  {
    title: "Weather – Latest",
    description:
      "Returns the latest weather observation for a location: temperature, apparent " +
      "temperature, humidity, dew point, pressure, cloud cover, precipitation, wind speed/gust/" +
      "bearing, UV index, ozone, visibility, and a human-readable summary. Returns a single " +
      "record for the current hour, or no data if none is available.",
    inputSchema: {
      ...locationFields,
      units: z
        .enum(["imperial", "metric", "si"])
        .optional()
        .describe("Unit system for the weather values. Defaults to imperial."),
    },
  },
  (args) => run(weatherLatest, args)
);

server.registerTool(
  "weather_forecast",
  {
    title: "Weather – 48-Hour Forecast",
    description:
      "Returns an hourly weather forecast for the next 48 hours: temperature, apparent " +
      "temperature, humidity, dew point, pressure, cloud cover, precipitation, wind speed/gust/" +
      "bearing, UV index, ozone, visibility, and a summary for each hour. Returns up to 48 " +
      "hourly records, or no data if none is available.",
    inputSchema: {
      ...locationFields,
      units: z
        .enum(["imperial", "metric", "si"])
        .optional()
        .describe("Unit system for the weather values. Defaults to imperial."),
    },
  },
  (args) => run(weatherForecast48h, args)
);

server.registerTool(
  "pollen_latest",
  {
    title: "Pollen – Latest",
    description:
      "Returns the latest pollen data for a location: tree, grass, and weed pollen counts and " +
      "risk levels, plus a per-species breakdown where the region supports it. Returns a single " +
      "record for the current hour, or no data if none is available.",
    inputSchema: {
      ...locationFields,
      speciesRisk: z
        .boolean()
        .optional()
        .describe("If true, also include per-species risk levels where supported. Defaults to false."),
    },
  },
  (args) => run(pollenLatest, args)
);

server.registerTool(
  "pollen_forecast",
  {
    title: "Pollen – 48-Hour Forecast",
    description:
      "Returns an hourly pollen forecast for the next 48 hours: tree, grass, and weed pollen " +
      "counts and risk levels, plus a per-species breakdown where the region supports it. " +
      "Returns up to 48 hourly records, or no data if none is available.",
    inputSchema: {
      ...locationFields,
      speciesRisk: z
        .boolean()
        .optional()
        .describe("If true, also include per-species risk forecasts where supported. Defaults to false."),
    },
  },
  (args) => run(pollenForecast48h, args)
);

const transport = new StdioServerTransport();
await server.connect(transport);
console.error("[ambee-mcp-server] running on stdio");

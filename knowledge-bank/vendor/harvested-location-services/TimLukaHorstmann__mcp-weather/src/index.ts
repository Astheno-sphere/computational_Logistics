#!/usr/bin/env node
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema, Tool } from "@modelcontextprotocol/sdk/types.js";
import { handler as hourlyHandler } from "./tools/WeatherTool.js";
import { handler as dailyHandler } from "./tools/WeatherDailyTool.js";
import type { RequestHandlerExtra } from "@modelcontextprotocol/sdk/shared/protocol.js";

// Define the hourly forecast tool
const hourlyWeatherTool: Tool = {
  name: "weather-get_hourly",
  description: "Get hourly weather forecast for the next 12 hours",
  inputSchema: {
    type: "object",
    properties: {
      location: {
        type: "string",
        description: "The city or location for which to retrieve the weather forecast."
      },
      units: {
        type: "string",
        description: "Temperature unit system (metric for Celsius, imperial for Fahrenheit). Default is metric.",
        enum: ["metric", "imperial"]
      }
    },
    required: ["location"]
  }
};

// Define the daily forecast tool
const dailyWeatherTool: Tool = {
  name: "weather-get_daily",
  description: "Get daily weather forecast for up to 15 days",
  inputSchema: {
    type: "object",
    properties: {
      location: {
        type: "string",
        description: "The city or location for which to retrieve the weather forecast."
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
    required: ["location"]
  }
};

const server = new Server(
  {
    name: "mcp-weather",
    version: "0.4.2",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// Set up request handlers
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [hourlyWeatherTool, dailyWeatherTool],
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  try {
    const args = request.params.arguments;
    if (args === undefined) {
      return {
        content: [{ type: "text", text: "Error: No arguments provided for the tool." }],
        isError: true
      };
    }
    
    if (request.params.name === "weather-get_hourly") {
      return await hourlyHandler(args, {} as RequestHandlerExtra<any, any>);
    } else if (request.params.name === "weather-get_daily") {
      return await dailyHandler(args, {} as RequestHandlerExtra<any, any>);
    } else {
      return {
        content: [{ type: "text", text: `Unknown tool: ${request.params.name}` }],
        isError: true
      };
    }
  } catch (error) {
    return {
      content: [{ type: "text", text: `Error: ${error instanceof Error ? error.message : String(error)}` }],
      isError: true
    };
  }
});

async function runServer() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Weather MCP Server running on stdio");
}

runServer().catch((err) => {
  console.error("Server error:", err);
  process.exit(1);
});
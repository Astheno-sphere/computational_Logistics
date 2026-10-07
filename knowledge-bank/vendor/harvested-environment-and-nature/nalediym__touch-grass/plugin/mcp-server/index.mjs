#!/usr/bin/env node
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import {
  checkConditions,
  readState,
  logTouchGrass,
} from "../lib/grass.mjs";
import { pickActivity } from "../lib/nudge.mjs";

const server = new Server(
  { name: "touch-grass", version: "0.1.5" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "check_grass_conditions",
      description:
        "Returns the user's current outdoor context: approximate city/region (IP-cached 24h), live weather code + temperature, minutes until sunset, golden-hour flag, and current streak. Latency ~200–600ms.\n\n" +
        "Side effects: outbound HTTPS to ip-api.com (location, cached to ~/.touch-grass/state.json) and open-meteo.com (weather + sunset, no key). Reads state.json; never mutates streak fields.\n\n" +
        "When to use: once per session before deciding whether to nudge the user outside. The plugin's SessionStart hook already injects this context — read that block first.\n\n" +
        "When NOT to use: don't poll repeatedly; conditions change on the order of minutes. For streak-only data without a network call, use get_stats.",
      inputSchema: { type: "object", properties: {} },
      annotations: {
        title: "Check outdoor conditions and streak",
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: true,
      },
    },
    {
      name: "suggest_activity",
      description:
        "Read-only. Returns a single context-appropriate outdoor activity (e.g., '☀️ short walk', '🌅 catch the sunset') filtered by current weather, temperature, and time until sunset. Picks deterministically per call from a small curated list — calls in quick succession may return the same suggestion.\n\n" +
        "Side effects: internally calls check_grass_conditions, so the same outbound HTTPS calls (ip-api, open-meteo) and the same 24h location cache write apply. No streak mutation. No auth required.\n\n" +
        "When to use: after you've decided to nudge the user — gives you something concrete to suggest instead of a vague 'go outside'.\n\n" +
        "When NOT to use: don't call before deciding to nudge (wasted network round-trip). Don't re-suggest an activity the user already declined this session — the tool has no memory of prior suggestions.",
      inputSchema: { type: "object", properties: {} },
      annotations: {
        title: "Suggest a context-aware outdoor activity",
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: true,
      },
    },
    {
      name: "log_touch_grass",
      description:
        "Writes to local state. Records that the user went outside, increments total touches, and either extends or resets the daily streak based on the gap since the last entry. Mutates ~/.touch-grass/state.json (streak, longestStreak, totalTouches, history). NOT idempotent — each call adds an entry. Errors (e.g., disk full, permission denied on ~/.touch-grass) surface as structured tool errors with isError=true; the streak is not partially updated on failure.\n\n" +
        "Side effects: append-only file write. No network calls. No auth required. The mutation is local-only and persists across sessions.\n\n" +
        "When to use: ONLY after the user explicitly confirms they went outside (e.g., 'I just got back from a walk', 'done — touched grass'). Never on speculation.\n\n" +
        "When NOT to use: never call to 'test' the tool — every invocation permanently inflates the user's streak/totals and there is no built-in undo. Don't call when the user is merely planning to go outside; wait for confirmation.",
      inputSchema: {
        type: "object",
        properties: {
          activity: {
            type: "string",
            description:
              "Free-form label describing what the user just did outside (e.g., 'walk', 'coffee on porch', 'stretched'). Stored verbatim as the `activity` field of this streak entry in ~/.touch-grass/state.json — it becomes the human-readable record of THIS recording action. Optional; defaults to 'outside time'. Has no effect on streak math; purely descriptive metadata for history readback.",
          },
        },
      },
      annotations: {
        title: "Log a confirmed grass-touching session",
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: false,
        openWorldHint: false,
      },
    },
    {
      name: "get_stats",
      description:
        "Read-only. Returns the raw contents of ~/.touch-grass/state.json: streak, longestStreak, totalTouches, lastTouchedDate, sessionCount, and the cached location/weather block. No network calls, no streak mutation. No auth required.\n\n" +
        "When to use: when the user asks about their streak/totals, or when you need stats but explicitly want to skip the weather lookup.\n\n" +
        "When NOT to use: if you also need current weather/sunset, prefer check_grass_conditions — it returns the same streak fields plus live conditions in one call.",
      inputSchema: { type: "object", properties: {} },
      annotations: {
        title: "Read streak and session stats",
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args = {} } = request.params;

  try {
    if (name === "check_grass_conditions") {
      const conditions = await checkConditions();
      return {
        content: [
          { type: "text", text: JSON.stringify(conditions, null, 2) },
        ],
      };
    }

    if (name === "suggest_activity") {
      const conditions = await checkConditions();
      const activity = pickActivity(conditions);
      return {
        content: [
          {
            type: "text",
            text: `${activity.emoji} ${activity.label}`,
          },
        ],
      };
    }

    if (name === "log_touch_grass") {
      const result = await logTouchGrass(args.activity || "outside time");
      return {
        content: [
          {
            type: "text",
            text:
              `🌿 Logged: ${result.activity}. ` +
              `Current streak: ${result.streak} days (best: ${result.longestStreak}). ` +
              `Total touches: ${result.totalTouches}.`,
          },
        ],
      };
    }

    if (name === "get_stats") {
      const state = await readState();
      return {
        content: [{ type: "text", text: JSON.stringify(state, null, 2) }],
      };
    }

    throw new Error(`Unknown tool: ${name}`);
  } catch (err) {
    return {
      content: [{ type: "text", text: `Error: ${err.message}` }],
      isError: true,
    };
  }
});

const transport = new StdioServerTransport();
await server.connect(transport);

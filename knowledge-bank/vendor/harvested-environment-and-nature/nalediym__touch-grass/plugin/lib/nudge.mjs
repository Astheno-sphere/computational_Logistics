import { readFile } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";

async function loadCustomActivities() {
  try {
    const configPath = join(homedir(), ".touch-grass", "config.json");
    const raw = await readFile(configPath, "utf8");
    const config = JSON.parse(raw);
    if (Array.isArray(config.customActivities) && config.customActivities.length > 0) {
      return config.customActivities.map((a) =>
        typeof a === "string" ? { label: a, emoji: "🌿" } : a
      );
    }
  } catch {
    // No config or no customActivities — use defaults
  }
  return null;
}

const ACTIVITIES = [
  { label: "walk around the block", emoji: "🚶" },
  { label: "stretch outside", emoji: "🧘" },
  { label: "coffee on the porch", emoji: "☕" },
  { label: "bench sit", emoji: "🪑" },
  { label: "quick run", emoji: "🏃" },
  { label: "check on the plants", emoji: "🌻" },
  { label: "throw a ball", emoji: "⚽" },
  { label: "sky gaze", emoji: "☁️" },
  { label: "just stand in the sun for 5 minutes", emoji: "☀️" },
  { label: "walk the long way to get water", emoji: "💧" },
];

const GOLDEN_HOUR_ACTIVITIES = [
  { label: "catch the sunset", emoji: "🌅" },
  { label: "golden hour walk", emoji: "✨" },
  { label: "sit outside and watch the light change", emoji: "🌇" },
];

export async function pickActivity(conditions) {
  const custom = await loadCustomActivities();
  const defaults =
    conditions?.minutesToSunset > 0 && conditions.minutesToSunset <= 60
      ? GOLDEN_HOUR_ACTIVITIES
      : ACTIVITIES;
  const pool = custom ?? defaults;
  return pool[Math.floor(Math.random() * pool.length)];
}

export async function generateNudge(conditions) {
  if (conditions.error) {
    // Silent fail — don't pollute context with errors
    return null;
  }

  const { weather, minutesToSunset, isNice, state } = conditions;
  const activity = await pickActivity(conditions);
  const today = new Date().toISOString().split("T")[0];
  const yesterday = new Date(Date.now() - 86400000)
    .toISOString()
    .split("T")[0];

  const lines = ["# 🌿 Touch Grass Conditions"];
  lines.push("");

  // Weather snapshot
  const dayOrNight = weather.isDay ? "outside" : "tonight";
  lines.push(
    `**${weather.tempF}°F (${weather.tempC}°C), ${weather.description}** ${dayOrNight}${
      conditions.location?.city ? ` in ${conditions.location.city}` : ""
    }.`
  );

  // Sunset window
  if (weather.isDay && minutesToSunset > 0) {
    if (minutesToSunset <= 30) {
      lines.push(
        `**⚠️ SUNSET IN ${minutesToSunset} MINUTES.** This is golden hour. If the user hits any natural pause, push them outside NOW.`
      );
    } else if (minutesToSunset <= 90) {
      lines.push(
        `🌅 Sunset in ${minutesToSunset} minutes. Great time for a ${activity.emoji} ${activity.label}.`
      );
    } else {
      lines.push(`☀️ Sunset in ${Math.round(minutesToSunset / 60)}h.`);
    }
  } else if (!weather.isDay) {
    lines.push(`🌙 It's dark out. Don't push the user outside tonight.`);
  }

  // Weather quality
  if (isNice && weather.isDay) {
    lines.push(
      `✨ It's genuinely nice out. Suggest ${activity.emoji} ${activity.label} at the next natural pause.`
    );
  } else if (!isNice && weather.isDay) {
    lines.push(`🌧 Weather isn't great. Don't push hard — maybe window time.`);
  }

  lines.push("");

  // Streak context
  lines.push("## User's Grass Status");
  if (state.currentStreak > 0) {
    if (state.lastTouchedDate === today) {
      lines.push(
        `✅ Already touched grass today. ${state.currentStreak}-day streak going strong.`
      );
    } else if (state.lastTouchedDate === yesterday) {
      lines.push(
        `🔥 ${state.currentStreak}-day streak — **needs to touch grass today to keep it alive.** Don't let them end the session without mentioning it.`
      );
    } else {
      lines.push(
        `💔 Streak broken. Previous best: ${state.longestStreak} days. Time to start a new one.`
      );
    }
  } else {
    lines.push(`🌱 No active streak. Today could be day 1.`);
  }

  if (state.sessionsToday > 2) {
    lines.push(
      `⏰ This is their ${state.sessionsToday}th coding session today. They definitely need a break.`
    );
  }

  lines.push("");
  lines.push("## How to Act on This");
  lines.push(
    "At a **natural pause** (feature complete, bug fixed, tests green, waiting for input), gently suggest the user step outside. Match the urgency:"
  );
  lines.push("");
  lines.push("- Sunset soon + nice out → push hard, specific, now");
  lines.push("- Nice day + no grass today → firm nudge at next pause");
  lines.push("- Streak at risk → remind before session ends");
  lines.push("- Bad weather or dark out → skip the nudge");
  lines.push("");
  lines.push(
    "**Never interrupt mid-task.** Reference actual conditions (temperature, time to sunset). Tiger mom energy — warm, specific, not preachy. If they confirm they went outside, call `log_touch_grass` via the touch-grass MCP server to update their streak."
  );

  return lines.join("\n");
}

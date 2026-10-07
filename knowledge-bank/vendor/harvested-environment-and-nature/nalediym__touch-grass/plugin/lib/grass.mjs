import { readFile, writeFile, mkdir } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";

const STATE_DIR = join(homedir(), ".touch-grass");
const STATE_FILE = join(STATE_DIR, "state.json");
const CONFIG_FILE = join(STATE_DIR, "config.json");

const DEFAULT_STATE = {
  currentStreak: 0,
  longestStreak: 0,
  lastTouchedDate: null,
  totalTouches: 0,
  sessionStart: null,
  lastSessionStart: null,
  sessionsToday: 0,
  totalCodingSessions: 0,
};

const DEFAULT_CONFIG = {
  location: null,
  niceWeatherThresholdC: 15,
  breakIntervalHours: 2,
  enabled: true,
};

async function ensureStateDir() {
  try {
    await mkdir(STATE_DIR, { recursive: true });
  } catch {}
}

export async function readState() {
  try {
    const data = await readFile(STATE_FILE, "utf8");
    return { ...DEFAULT_STATE, ...JSON.parse(data) };
  } catch {
    return { ...DEFAULT_STATE };
  }
}

export async function writeState(state) {
  await ensureStateDir();
  await writeFile(STATE_FILE, JSON.stringify(state, null, 2));
}

export async function readConfig() {
  try {
    const data = await readFile(CONFIG_FILE, "utf8");
    return { ...DEFAULT_CONFIG, ...JSON.parse(data) };
  } catch {
    return { ...DEFAULT_CONFIG };
  }
}

export async function writeConfig(config) {
  await ensureStateDir();
  await writeFile(CONFIG_FILE, JSON.stringify(config, null, 2));
}

export async function getLocation() {
  const config = await readConfig();

  // Cache location for 24 hours
  if (
    config.location &&
    Date.now() - config.location.fetchedAt < 86400000
  ) {
    return config.location;
  }

  try {
    // ip-api.com: free, no key, 45 req/min. HTTP only on free tier.
    const res = await fetch("http://ip-api.com/json/", {
      signal: AbortSignal.timeout(5000),
    });
    if (!res.ok) throw new Error(`ip-api status ${res.status}`);
    const data = await res.json();
    if (data.status !== "success") throw new Error("ip-api lookup failed");
    const loc = {
      lat: data.lat,
      lon: data.lon,
      city: data.city,
      region: data.regionName,
      country: data.country,
      timezone: data.timezone,
      fetchedAt: Date.now(),
    };
    config.location = loc;
    await writeConfig(config);
    return loc;
  } catch {
    return config.location || null;
  }
}

export async function getWeather(lat, lon) {
  try {
    const url =
      `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}` +
      `&current=temperature_2m,weather_code,is_day` +
      `&daily=sunrise,sunset&timezone=auto`;
    const res = await fetch(url, { signal: AbortSignal.timeout(5000) });
    if (!res.ok) throw new Error("weather failed");
    const data = await res.json();
    return {
      tempC: data.current.temperature_2m,
      weatherCode: data.current.weather_code,
      isDay: data.current.is_day === 1,
      sunrise: new Date(data.daily.sunrise[0]),
      sunset: new Date(data.daily.sunset[0]),
    };
  } catch {
    return null;
  }
}

export function weatherDescription(code) {
  if (code === 0) return "clear";
  if (code <= 3) return "partly cloudy";
  if (code <= 48) return "foggy";
  if (code <= 57) return "drizzly";
  if (code <= 67) return "rainy";
  if (code <= 77) return "snowy";
  if (code <= 82) return "showery";
  if (code <= 86) return "snow showers";
  return "stormy";
}

export function isNiceWeather(weather, thresholdC = 15) {
  if (!weather) return false;
  return weather.weatherCode <= 3 && weather.tempC >= thresholdC;
}

export async function checkConditions() {
  const config = await readConfig();
  const location = await getLocation();

  if (!location) {
    return {
      error: "Could not determine location. Weather nudges disabled.",
      state: await readState(),
    };
  }

  const weather = await getWeather(location.lat, location.lon);
  if (!weather) {
    return {
      error: "Could not fetch weather",
      location,
      state: await readState(),
    };
  }

  const now = new Date();
  const minutesToSunset = Math.round((weather.sunset - now) / 60000);
  const minutesSinceSunrise = Math.round((now - weather.sunrise) / 60000);
  const state = await readState();

  return {
    location,
    weather: {
      tempC: weather.tempC,
      tempF: Math.round((weather.tempC * 9) / 5 + 32),
      description: weatherDescription(weather.weatherCode),
      isDay: weather.isDay,
    },
    sunset: weather.sunset.toISOString(),
    sunrise: weather.sunrise.toISOString(),
    minutesToSunset,
    minutesSinceSunrise,
    isNice: isNiceWeather(weather, config.niceWeatherThresholdC),
    state,
  };
}

export async function logTouchGrass(activity = "outside time") {
  const state = await readState();
  const today = new Date().toISOString().split("T")[0];
  const yesterday = new Date(Date.now() - 86400000)
    .toISOString()
    .split("T")[0];

  let newStreak = state.currentStreak;
  if (state.lastTouchedDate === today) {
    // Already counted today
  } else if (state.lastTouchedDate === yesterday) {
    newStreak += 1;
  } else {
    newStreak = 1;
  }

  state.currentStreak = newStreak;
  state.longestStreak = Math.max(newStreak, state.longestStreak);
  state.lastTouchedDate = today;
  state.totalTouches += 1;
  await writeState(state);

  return {
    activity,
    streak: newStreak,
    longestStreak: state.longestStreak,
    totalTouches: state.totalTouches,
  };
}

export async function recordSessionStart() {
  const state = await readState();
  const now = new Date();
  const today = now.toISOString().split("T")[0];
  const lastSessionDate = state.sessionStart
    ? new Date(state.sessionStart).toISOString().split("T")[0]
    : null;

  state.lastSessionStart = state.sessionStart;
  state.sessionStart = now.toISOString();
  state.totalCodingSessions += 1;
  state.sessionsToday =
    lastSessionDate === today ? (state.sessionsToday || 0) + 1 : 1;
  await writeState(state);
  return state;
}

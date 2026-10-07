import https from "node:https";

const BASE_HOST = "api.ambeedata.com";

/**
 * Error codes documented at https://docs.ambeedata.com/apis/overview#error-codes
 * Mapped to short, actionable guidance so a tool-calling model (or a human
 * reading the error) knows what to do next instead of just seeing "HTTP 422".
 */
const ERROR_CODE_GUIDANCE = {
  206: {
    label: "Partial data",
    hint:
      "The API quota was exhausted mid-response, so this result is trimmed. " +
      "Check your usage on the Ambee dashboard and consider upgrading your plan.",
  },
  299: {
    label: "Deprecated",
    hint: "This endpoint/feature isn't supported by the current API version. Check docs.ambeedata.com for the current path.",
  },
  400: {
    label: "Bad request",
    hint:
      "The request was rejected due to invalid, missing, or malformed parameters. " +
      "Double check that either (lat + lng) or place is set, and that any from/to values use 'YYYY-MM-DD HH:MM:SS'.",
  },
  401: {
    label: "Unauthorized",
    hint: "No valid API key was supplied. Verify AMBEE_API_KEY is set and active.",
  },
  403: {
    label: "Forbidden",
    hint: "Your API key doesn't have permission for this endpoint. Check your plan/permissions on the Ambee dashboard.",
  },
  404: {
    label: "Not found",
    hint: "No data is available for the requested location, or the endpoint path is wrong.",
  },
  422: {
    label: "Quota exceeded",
    hint: "You've hit your plan's request quota. Upgrade your plan or wait for the quota to reset.",
  },
  429: {
    label: "Rate limited",
    hint: "Too many requests too quickly. Back off and retry, ideally with exponential backoff.",
  },
  500: {
    label: "Internal server error",
    hint: "Something went wrong on Ambee's end. Retry later or check https://docs.ambeedata.com/api-status.",
  },
};

/**
 * Custom error carrying the HTTP status and Ambee's own message, so callers
 * can branch on `err.status` if they want to.
 */
export class AmbeeApiError extends Error {
  constructor(status, ambeeMessage) {
    const guidance = ERROR_CODE_GUIDANCE[status];
    const label = guidance ? guidance.label : `HTTP ${status}`;
    const hint = guidance ? ` ${guidance.hint}` : "";
    super(`Ambee API error ${status} (${label}): ${ambeeMessage}.${hint}`);
    this.name = "AmbeeApiError";
    this.status = status;
    this.ambeeMessage = ambeeMessage;
  }
}

function get(path) {
  const apiKey = process.env.AMBEE_API_KEY;
  return new Promise((resolve, reject) => {
    const options = {
      method: "GET",
      hostname: BASE_HOST,
      path,
      headers: {
        "x-api-key": apiKey,
        "Content-type": "application/json",
      },
    };

    const req = https.request(options, (res) => {
      const chunks = [];
      res.on("data", (chunk) => chunks.push(chunk));
      res.on("end", () => {
        const raw = Buffer.concat(chunks).toString("utf-8");
        let body;
        try {
          body = raw ? JSON.parse(raw) : {};
        } catch {
          reject(new Error(`Ambee API returned a non-JSON response: ${raw.slice(0, 200)}`));
          return;
        }

        const status = res.statusCode ?? 0;

        // 200 is a clean success. 206 ("Partial data") is still usable data,
        // just trimmed, so we surface it as a soft warning rather than throwing.
        if (status === 200) {
          resolve({ status, body, warning: null });
          return;
        }
        if (status === 206) {
          resolve({
            status,
            body,
            warning: `${ERROR_CODE_GUIDANCE[206].label}: ${ERROR_CODE_GUIDANCE[206].hint}`,
          });
          return;
        }

        const message = body?.message || body?.error?.message || "Unknown error";
        reject(new AmbeeApiError(status, message));
      });
    });

    req.on("error", (err) => reject(new Error(`Network error calling Ambee API: ${err.message}`)));
    req.end();
  });
}

function qs(params) {
  const usp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      usp.set(key, String(value));
    }
  }
  return usp.toString();
}

/**
 * Every /v3 endpoint in this spec shares the same rule: exactly one of
 * (lat + lng) or place. Unlike the old REST-by-lat-lng endpoints, these v3
 * endpoints accept `place` directly, so no client-side geocoding is needed.
 */
function assertLocation({ lat, lng, place }) {
  const hasCoords = lat !== undefined && lng !== undefined;
  const hasPlace = place !== undefined && place !== null && place !== "";

  if (hasCoords && hasPlace) {
    throw new Error("Provide either lat+lng or place, not both — not a fallback chain.");
  }
  if (!hasCoords && !hasPlace) {
    throw new Error("Provide either lat+lng or a free-text place.");
  }
}

function locationParams({ lat, lng, place }) {
  return place ? { place } : { lat, lng };
}

export async function aqLatest({ lat, lng, place, locale, aqiStandard }) {
  assertLocation({ lat, lng, place });
  const params = { ...locationParams({ lat, lng, place }), locale, aqiStandard };
  return get(`/v3/aq/latest?${qs(params)}`);
}

export async function aqForecast48h({ lat, lng, place, locale, aqiStandard }) {
  assertLocation({ lat, lng, place });
  const params = { ...locationParams({ lat, lng, place }), locale, aqiStandard };
  return get(`/v3/aq/forecast/48hrs?${qs(params)}`);
}

export async function weatherLatest({ lat, lng, place, locale, units }) {
  assertLocation({ lat, lng, place });
  const params = { ...locationParams({ lat, lng, place }), locale, units };
  return get(`/v3/weather/latest?${qs(params)}`);
}

export async function weatherForecast48h({ lat, lng, place, locale, units }) {
  assertLocation({ lat, lng, place });
  const params = { ...locationParams({ lat, lng, place }), locale, units };
  return get(`/v3/weather/forecast/48hrs?${qs(params)}`);
}

export async function pollenLatest({ lat, lng, place, locale, speciesRisk }) {
  assertLocation({ lat, lng, place });
  const params = { ...locationParams({ lat, lng, place }), locale, speciesRisk };
  return get(`/v3/pollen/latest?${qs(params)}`);
}

export async function pollenForecast48h({ lat, lng, place, locale, speciesRisk }) {
  assertLocation({ lat, lng, place });
  const params = { ...locationParams({ lat, lng, place }), locale, speciesRisk };
  return get(`/v3/pollen/forecast/48hrs?${qs(params)}`);
}

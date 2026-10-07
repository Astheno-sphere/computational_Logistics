export interface SthanClientOptions {
  apiKey: string;
  baseUrl?: string;
  timeout?: number;
  /**
   * Timeout for verify and parse, which can fall through to a live postal lookup
   * that takes 70+ seconds for addresses it cannot match from its own data.
   * Defaults to 150000 ms, the same limit sthan.io's own website uses.
   */
  postalLookupTimeout?: number;
}

export interface SthanResponse<T> {
  Id: string;
  Result: T;
  ClientSessionId: string | null;
  StatusCode: number;
  IsError: boolean;
  Errors: string[];
}

export class SthanClient {
  private apiKey: string;
  private baseUrl: string;
  private timeout: number;
  private postalLookupTimeout: number;

  constructor(options: SthanClientOptions) {
    this.apiKey = options.apiKey;
    this.baseUrl = (options.baseUrl || "https://api.sthan.io").replace(/\/$/, "");
    this.timeout = options.timeout || 30000;
    this.postalLookupTimeout = options.postalLookupTimeout || 150000;
  }

  async request<T>(path: string, timeoutMs: number = this.timeout): Promise<SthanResponse<T>> {
    const url = `${this.baseUrl}${path}`;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    let response: Response;
    try {
      response = await fetch(url, {
        headers: {
          Authorization: `Bearer ${this.apiKey}`,
          Accept: "application/json",
        },
        signal: controller.signal,
      });
    } catch (e) {
      // Timeout (abort) and DNS/connection failures land here — not API errors.
      if (e instanceof Error && e.name === "AbortError") {
        throw new Error(`Request timed out after ${timeoutMs}ms`);
      }
      throw e;
    } finally {
      clearTimeout(timer);
    }

    // Read the body once as text, then parse defensively: error responses
    // (401, 429, 5xx) are often empty or non-JSON and must not crash parsing.
    const text = await response.text();
    let body: SthanResponse<T> | undefined;
    if (text) {
      try {
        body = JSON.parse(text) as SthanResponse<T>;
      } catch {
        body = undefined;
      }
    }

    if (!response.ok) {
      const message = body?.Errors?.length
        ? body.Errors.join("; ")
        : httpErrorMessage(response.status);
      throw new SthanApiError(
        message,
        body?.StatusCode ?? response.status,
        body?.Errors ?? []
      );
    }

    if (!body) {
      throw new SthanApiError(
        `Empty or invalid JSON response (HTTP ${response.status})`,
        response.status
      );
    }

    if (body.IsError) {
      const message = body.Errors?.length
        ? body.Errors.join("; ")
        : `HTTP ${response.status}`;
      throw new SthanApiError(message, body.StatusCode, body.Errors);
    }

    return body;
  }

  async verifyAddress(address: string) {
    // V2 endpoint: returns the full model (unitType/unitNumber, matchMode,
    // matchTier, confidence, matchCode). V1 (/AddressVerification/Usa/Single)
    // returns the older, leaner shape without those fields.
    return this.request<Record<string, unknown>>(
      `/v2/address-verification/usa/${encodeURIComponent(address)}`,
      this.postalLookupTimeout
    );
  }

  async parseAddress(address: string) {
    // V2 endpoint: full mode-aware parse with confidence/matchTier.
    return this.request<Record<string, unknown>>(
      `/v2/address-parser/usa/${encodeURIComponent(address)}`,
      this.postalLookupTimeout
    );
  }

  async autocompleteAddress(text: string) {
    return this.request<string[]>(
      `/AutoComplete/USA/Address/${encodeURIComponent(text)}`
    );
  }

  async autocompleteCity(text: string, displayType: number = 0) {
    return this.request<string[]>(
      `/AutoComplete/USA/City/DisplayType/${displayType}/${encodeURIComponent(text)}`
    );
  }

  async autocompleteZipCode(text: string, displayType: number = 0) {
    return this.request<string[]>(
      `/AutoComplete/USA/ZipCode/DisplayType/${displayType}/${encodeURIComponent(text)}`
    );
  }

  async geocodeAddress(address: string) {
    return this.request<Record<string, unknown>>(
      `/Geocoding/USA/Forward/${encodeURIComponent(address)}`
    );
  }

  async reverseGeocode(latitude: number, longitude: number) {
    return this.request<Record<string, unknown>>(
      `/Geocoding/USA/Reverse/${latitude}/${longitude}`
    );
  }

  async ipGeolocation(ip: string) {
    return this.request<Record<string, unknown>>(
      `/IpGeolocation/${encodeURIComponent(ip)}`
    );
  }
}

/** Friendly message for an HTTP status when the response carries no error body. */
function httpErrorMessage(status: number): string {
  switch (status) {
    case 401:
      return "Authentication failed — check your API key (401)";
    case 403:
      return "Access forbidden — your plan may not allow this, or quota exceeded (403)";
    case 404:
      return "Not found (404)";
    case 429:
      return "Rate limited — too many requests (429)";
    case 500:
    case 502:
    case 503:
    case 504:
      return `Server error (${status})`;
    default:
      return `HTTP ${status}`;
  }
}

export class SthanApiError extends Error {
  statusCode: number;
  errors: string[];

  constructor(message: string, statusCode: number, errors: string[] = []) {
    super(message);
    this.name = "SthanApiError";
    this.statusCode = statusCode;
    this.errors = errors;
  }
}

export const DEFAULT_API_BASE = "https://disruption.forgemesh.io";
export class DisruptionApiClient {
    apiBase;
    constructor(apiBase = process.env.DISRUPTION_API_BASE ?? DEFAULT_API_BASE) {
        this.apiBase = normalizeBaseUrl(apiBase);
    }
    async get(path) {
        const url = this.url(path);
        const response = await fetch(url, {
            method: "GET",
            headers: {
                accept: "application/json, text/plain;q=0.8, */*;q=0.1",
                "user-agent": "@forgemeshlabs/disruption-intelligence-mcp"
            }
        });
        const data = await parseResponseBody(response);
        if (response.status === 402) {
            return {
                ok: false,
                status: response.status,
                url,
                paymentRequired: true,
                challenge: buildPaymentChallenge(response),
                error: data
            };
        }
        if (!response.ok) {
            return {
                ok: false,
                status: response.status,
                url,
                paymentRequired: false,
                error: data
            };
        }
        return {
            ok: true,
            status: response.status,
            url,
            data
        };
    }
    async getDiscoveryMetadata() {
        const paths = ["/index.json", "/llms.txt", "/openapi.json", "/.well-known/x402.json"];
        const resources = await Promise.all(paths.map(async (path) => {
            const url = this.url(path);
            const response = await fetch(url, {
                method: "GET",
                headers: {
                    accept: "application/json, text/plain;q=0.8, */*;q=0.1",
                    "user-agent": "@forgemeshlabs/disruption-intelligence-mcp"
                }
            });
            const contentType = response.headers.get("content-type") ?? undefined;
            const body = await response.text();
            const parsed = parseBodyText(body, contentType);
            return {
                path,
                url,
                status: response.status,
                ok: response.ok,
                contentType,
                ...(typeof parsed === "string" ? { text: parsed } : { data: parsed })
            };
        }));
        return {
            apiBase: this.apiBase,
            resources
        };
    }
    url(path) {
        const normalizedPath = path.startsWith("/") ? path : `/${path}`;
        return `${this.apiBase}${normalizedPath}`;
    }
}
function normalizeBaseUrl(value) {
    return value.replace(/\/+$/, "");
}
async function parseResponseBody(response) {
    const contentType = response.headers.get("content-type") ?? undefined;
    const body = await response.text();
    return parseBodyText(body, contentType);
}
function parseBodyText(body, contentType) {
    if (!body) {
        return null;
    }
    if (contentType?.includes("application/json")) {
        try {
            return JSON.parse(body);
        }
        catch {
            return body;
        }
    }
    const trimmed = body.trim();
    if ((trimmed.startsWith("{") && trimmed.endsWith("}")) || (trimmed.startsWith("[") && trimmed.endsWith("]"))) {
        try {
            return JSON.parse(trimmed);
        }
        catch {
            return body;
        }
    }
    return body;
}
function buildPaymentChallenge(response) {
    const headers = paymentHeaders(response.headers);
    const encodedChallenge = headers["payment-required"];
    const decoded = encodedChallenge ? decodeBase64Json(encodedChallenge) : undefined;
    return {
        status: 402,
        headers,
        decoded,
        instructions: "This endpoint requires x402 payment. The MCP server is in safe non-settling mode and returned the challenge for a trusted wallet/payment client to handle."
    };
}
function paymentHeaders(headers) {
    const result = {};
    for (const [key, value] of headers.entries()) {
        const lower = key.toLowerCase();
        if (lower.includes("payment") || lower.includes("x402") || lower === "www-authenticate") {
            result[lower] = value;
        }
    }
    return result;
}
function decodeBase64Json(value) {
    try {
        return JSON.parse(Buffer.from(value, "base64").toString("utf8"));
    }
    catch {
        return undefined;
    }
}
//# sourceMappingURL=client.js.map
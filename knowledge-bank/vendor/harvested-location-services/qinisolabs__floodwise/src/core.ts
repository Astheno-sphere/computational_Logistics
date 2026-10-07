// Single source of truth for floodwise's tools + a minimal, stateless JSON-RPC 2.0
// handler (the wire format of MCP's Streamable HTTP transport). The Cloudflare
// Worker and any HTTP host reuse handleRpc(); the stdio server reuses the same
// TOOLS array via the MCP SDK. No node:fs, no SDK here — so this bundles at the edge.
import { floodRiskByPostcode, validatePostcode, datasetVersion, datasetSize, datasetKind } from "./flood.js";

export type ArgType = "string" | "number";

export interface ToolArg {
  name: string;
  type: ArgType;
  description: string;
  optional?: boolean;
}

export interface ToolSpec {
  name: string;
  description: string;
  args: ToolArg[];
  run: (a: Record<string, unknown>) => unknown;
}

export const TOOLS: ToolSpec[] = [
  {
    name: "flood_risk_by_postcode",
    description:
      "USE THIS to get the Environment Agency's long-term flood-risk indication for an England postcode instead of guessing — e.g. when triaging a home/property insurance quote, underwriting, or answering 'is this address at flood risk?'. Returns the highest risk band (High/Medium/Low/Very Low) for the area around addresses in the postcode, the count of addresses in each band, and a separate groundwater indication. IMPORTANT: England only (not Wales/Scotland/NI), AREA-level not property-level, long-term risk not a live flood warning. Returns an honest 'not found' rather than inventing a risk level.",
    args: [{ name: "postcode", type: "string", description: "A UK postcode, e.g. 'SW1A 1AA' or 'sw1a1aa'." }],
    run: (a) => floodRiskByPostcode(String(a.postcode ?? "")),
  },
  {
    name: "validate_postcode",
    description:
      "USE THIS to check a UK postcode is well-formed and to split it into its outward and inward codes before storing or matching it — instead of trusting raw input. Deterministic format check only (no lookup); returns the canonical spaced form, outcode and incode.",
    args: [{ name: "postcode", type: "string", description: "The UK postcode to validate." }],
    run: (a) => validatePostcode(String(a.postcode ?? "")),
  },
];

export const SERVER_INFO = { name: "floodwise", version: "0.1.1" } as const;
export const PUBLIC_BASE = "https://qinisolabs.github.io/floodwise";
const DEFAULT_PROTOCOL = "2025-06-18";

function jsonType(t: ArgType) {
  return t === "number" ? { type: "number" } : { type: "string" };
}
function inputSchema(t: ToolSpec) {
  const properties: Record<string, unknown> = {};
  const required: string[] = [];
  for (const a of t.args) {
    properties[a.name] = { ...jsonType(a.type), description: a.description };
    if (!a.optional) required.push(a.name);
  }
  return { type: "object", properties, required, additionalProperties: false };
}
// Human-readable Title Case for a tool name, uppercasing known acronyms — used for the
// `title` + `readOnlyHint` tool annotations the Claude connector directory requires.
const ACRONYMS = new Set(["iban","vat","vin","gtin","upc","ean","isbn","isbn10","issn","icd10","orcid","gln","sscc","imei","isin","cusip","sedol","lei","aba","eth","btc","tld","url","uuid","ip","id","dni","cpf","cnpj","pesel","bsn","nrn","nif","pt","sa","tckn","ric","rc","nir","ahv","curp","cnp","egn","de","fr","ch","mx","hr","ro","bg","ee","cz","uk","us","eu","sic","icd","fcdo"]);
export function humanizeTitle(name: string): string {
  return name.split("_").map((w) => (ACRONYMS.has(w) ? w.toUpperCase() : w.charAt(0).toUpperCase() + w.slice(1))).join(" ");
}
export function toolAnnotations(name: string) {
  return { title: humanizeTitle(name), readOnlyHint: true };
}
// Mirror every tool's JSON result into `structuredContent` so MCP clients get a
// typed object, not just text. Permissive-but-honest schema (results vary by tool).
const OUTPUT_SCHEMA = {
  type: "object",
  description: "Deterministic result object, identical to the JSON in the text payload and mirrored in `structuredContent`.",
  additionalProperties: true,
} as const;
export function listTools() {
  return TOOLS.map((t) => ({ name: t.name, description: t.description, inputSchema: inputSchema(t), outputSchema: OUTPUT_SCHEMA, annotations: toolAnnotations(t.name) }));
}
export function callTool(name: string, args: Record<string, unknown> | undefined) {
  const t = TOOLS.find((x) => x.name === name);
  if (!t) {
    const e: any = new Error(`Unknown tool: ${name}`);
    e.code = -32602;
    throw e;
  }
  const a: Record<string, unknown> = {};
  for (const arg of t.args) {
    const v = args?.[arg.name];
    a[arg.name] = v === undefined || v === null ? undefined : arg.type === "number" ? Number(v) : String(v);
  }
  const result = t.run(a);
  return {
    content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
    structuredContent: result as Record<string, unknown>,
  };
}

interface JsonRpcMessage {
  jsonrpc?: string;
  id?: string | number;
  method?: string;
  params?: any;
}

export function handleRpc(msg: JsonRpcMessage): object | null {
  const { id, method, params } = msg;
  if (id === undefined || method === "notifications/initialized") return null;
  try {
    let result: unknown;
    switch (method) {
      case "initialize":
        result = {
          protocolVersion: params?.protocolVersion ?? DEFAULT_PROTOCOL,
          capabilities: { tools: {} },
          serverInfo: { ...SERVER_INFO, websiteUrl: PUBLIC_BASE },
          instructions:
            `floodwise looks up the Environment Agency's long-term flood-risk indication for England postcodes (dataset kind '${datasetKind}', version ${datasetVersion}, ${datasetSize} postcodes loaded). Use flood_risk_by_postcode for a postcode's risk band + address counts + groundwater, and validate_postcode to check/split a UK postcode. ENGLAND ONLY (not Wales/Scotland/NI), AREA-level not property-level, long-term risk not a live flood warning. It returns an honest "not found" rather than inventing a risk level. Not insurance, underwriting, surveying or professional advice.`,
        };
        break;
      case "tools/list":
        result = { tools: listTools() };
        break;
      case "tools/call":
        result = callTool(params?.name, params?.arguments);
        break;
      case "ping":
        result = {};
        break;
      default:
        return { jsonrpc: "2.0", id, error: { code: -32601, message: `Method not found: ${method}` } };
    }
    return { jsonrpc: "2.0", id, result };
  } catch (err: any) {
    return { jsonrpc: "2.0", id, error: { code: err?.code ?? -32603, message: err?.message ?? String(err) } };
  }
}

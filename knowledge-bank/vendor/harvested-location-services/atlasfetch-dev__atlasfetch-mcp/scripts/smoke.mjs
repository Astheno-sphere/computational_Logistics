// Smoke test: drives the built server over stdio with a real MCP client and
// calls the live API. Uses the shared demo key unless ATLASFETCH_API_KEY is set,
// so it spends a few lookups from a pooled quota. Run: node scripts/smoke.mjs
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

const transport = new StdioClientTransport({ command: "node", args: ["dist/stdio.js"] });
const client = new Client({ name: "smoke", version: "0.0.0" });
await client.connect(transport);

const { tools } = await client.listTools();
console.log("tools:", tools.map((t) => t.name).join(", "));
for (const t of tools) {
  const required = t.inputSchema?.required ?? [];
  console.log(`  - ${t.name}: required [${required.join(", ")}] title="${t.title ?? ""}"`);
}

// The demo key allows 2 requests a second and this script is a burst of calls:
// without a pause the later ones come back 429 and prove nothing.
const pace = () => new Promise(resolve => setTimeout(resolve, 600));

async function call(name, args) {
  await pace();
  const res = await client.callTool({ name, arguments: args });
  const text = res.content.map((c) => c.text ?? "").join("\n");
  console.log(`\n== ${name} ${JSON.stringify(args)} -> isError=${res.isError ?? false}`);
  console.log(text.slice(0, 700));
}

// London: should resolve GB / England / Westminster
await call("lookup_location", { lat: 51.5072, lng: -0.1276, encode: ["h3", "pluscode"] });
// Mid-Atlantic: every layer should be null, and that is a correct answer
await call("lookup_location", { lat: 0, lng: -30, base: ["country"] });
// Out of range: the schema should refuse before any request is billed
await call("lookup_location", { lat: 999, lng: 0 });
// A set that does not exist: skipped, reported in errors, still a success
await call("lookup_location", { lat: 51.5072, lng: -0.1276, sets: ["no_such_set"] });
// Streets (beta): opt-in layer. Adderley Street, Cape Town.
await call("lookup_location", { lat: -33.9221, lng: 18.4231, base: ["municipal", "street"] });
// London: a second street case, in another country.
await call("lookup_location", { lat: 51.5072, lng: -0.1276, base: ["country", "street"] });

await call("list_boundary_sets", {});
// Wrong shape on purpose: a Feature instead of a geometry
await call("add_boundary", { set: "demo", name: "x", geometry: { type: "Feature", properties: {}, geometry: {} } });

await client.close();

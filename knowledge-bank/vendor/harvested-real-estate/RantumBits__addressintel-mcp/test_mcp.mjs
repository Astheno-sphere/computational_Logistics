import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

async function run() {
  const transport = new StdioClientTransport({
    command: "node",
    args: ["dist/index.js"]
  });

  const client = new Client(
    { name: "test-client", version: "1.0.0" },
    { capabilities: {} }
  );

  await client.connect(transport);
  console.log("Connected to MCP server!");

  const tools = await client.listTools();
  console.log("Tools available:", tools.tools.map(t => t.name));

  // Test list_market_signals
  console.log("\nTesting list_market_signals...");
  try {
    const result = await client.callTool({
      name: "list_market_signals",
      arguments: { market: "sf-peninsula" }
    });
    console.log("Result content:", result.content[0].text);
  } catch (err) {
    console.error("Tool execution failed:", err.message);
  }

  process.exit(0);
}

run().catch(console.error);

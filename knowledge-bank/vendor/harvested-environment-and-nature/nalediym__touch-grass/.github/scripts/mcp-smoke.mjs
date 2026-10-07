// Smoke test: spawn the MCP server, send a tools/list request over stdio,
// assert that check_grass_conditions appears in the response.
import { spawn } from "node:child_process";

const proc = spawn("node", ["plugin/mcp-server/index.mjs"], {
  stdio: ["pipe", "pipe", "inherit"],
});

let buf = "";
proc.stdout.on("data", (d) => (buf += d.toString()));

// MCP handshake: initialize, then tools/list
const initialize =
  JSON.stringify({
    jsonrpc: "2.0",
    id: 1,
    method: "initialize",
    params: {
      protocolVersion: "2024-11-05",
      capabilities: {},
      clientInfo: { name: "ci-smoke", version: "1.0" },
    },
  }) + "\n";

const initialized =
  JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized" }) +
  "\n";

const listTools =
  JSON.stringify({
    jsonrpc: "2.0",
    id: 2,
    method: "tools/list",
    params: {},
  }) + "\n";

proc.stdin.write(initialize);
proc.stdin.write(initialized);
proc.stdin.write(listTools);

const timer = setTimeout(() => {
  proc.kill("SIGKILL");
  console.error("MCP server timeout");
  console.error("stdout so far:", buf);
  process.exit(1);
}, 5000);

const poll = setInterval(() => {
  const line = buf.split("\n").find((l) => l.includes('"id":2'));
  if (!line) return;
  try {
    const msg = JSON.parse(line);
    const names = (msg.result?.tools ?? []).map((t) => t.name);
    if (!names.includes("check_grass_conditions")) {
      console.error("Missing check_grass_conditions. Got:", names);
      proc.kill("SIGKILL");
      process.exit(1);
    }
    console.log("MCP tools/list ok:", names.join(", "));
    clearTimeout(timer);
    clearInterval(poll);
    proc.kill("SIGKILL");
    process.exit(0);
  } catch {
    // partial read, keep waiting
  }
}, 50);

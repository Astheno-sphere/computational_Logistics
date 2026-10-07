// Step 2: log mcp-publisher in with the key, without the private key ever being
// printed or typed. Run: node scripts/registry-login.mjs
// Set MCP_PUBLISHER if the executable is not at E:\Claude\mcp-publisher.exe.
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { createPrivateKey } from "node:crypto";
import { readFileSync } from "node:fs";
import { privateHex } from "./registry-keys.mjs";

const keyPath = process.env.KEY_PATH ?? "key.pem";
const publisher = process.env.MCP_PUBLISHER ?? "E:/Claude/mcp-publisher.exe";

if (!existsSync(keyPath)) {
  console.error(`No ${keyPath}. Run node scripts/registry-key.mjs first.`);
  process.exit(1);
}
if (!existsSync(publisher)) {
  console.error(`mcp-publisher not found at ${publisher}. Set MCP_PUBLISHER to its path.`);
  process.exit(1);
}

const hex = privateHex(createPrivateKey(readFileSync(keyPath)));
// Arguments go straight to the process, not through a shell, so the key does
// not land in shell history.
const result = spawnSync(publisher, ["login", "dns", "--domain", "atlasfetch.xyz", "--private-key", hex], {
  stdio: "inherit",
});
process.exit(result.status ?? 1);

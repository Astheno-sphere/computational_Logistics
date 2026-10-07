// Step 1: create key.pem (if absent) and print the TXT record to add at the
// apex of atlasfetch.xyz. Run: node scripts/registry-key.mjs
import { loadOrCreateKey, txtValue } from "./registry-keys.mjs";

const path = process.env.KEY_PATH ?? "key.pem";
const { key, created } = loadOrCreateKey(path);
console.log(created ? `Created ${path}. Back it up now; it is not recoverable.` : `Using existing ${path}.`);
console.log("");
console.log("Add this in Cloudflare DNS for atlasfetch.xyz:");
console.log("  Type:    TXT");
console.log("  Name:    @   (the apex, NOT a subdomain like _mcp)");
console.log(`  Content: ${txtValue(key)}`);

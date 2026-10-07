// Ed25519 signing key for proving ownership of the xyz.atlasfetch namespace in
// the official MCP Registry. Node replaces the openssl pipeline in the registry
// docs, which needs Git Bash on Windows. Output is byte-for-byte what that
// pipeline produces: the same PKCS#8 key.pem, the same TXT value, the same hex.
//
// The private key is never printed. key.pem is gitignored; back it up somewhere
// safe, because anyone holding it can publish under xyz.atlasfetch.
import { generateKeyPairSync, createPrivateKey, createPublicKey } from "node:crypto";
import { existsSync, readFileSync, writeFileSync } from "node:fs";

export const DEFAULT_KEY_PATH = "key.pem";

/** Load key.pem, or create it. Never overwrites: a new key orphans the DNS record. */
export function loadOrCreateKey(path = DEFAULT_KEY_PATH) {
  if (existsSync(path)) {
    return { key: createPrivateKey(readFileSync(path)), created: false };
  }
  const { privateKey } = generateKeyPairSync("ed25519");
  writeFileSync(path, privateKey.export({ type: "pkcs8", format: "pem" }), { mode: 0o600 });
  return { key: privateKey, created: true };
}

/** The TXT record value: the raw 32-byte public key, base64. */
export function txtValue(privateKey) {
  const spki = createPublicKey(privateKey).export({ type: "spki", format: "der" });
  return `v=MCPv1; k=ed25519; p=${spki.subarray(-32).toString("base64")}`;
}

/** The 32-byte private seed as hex, which is what mcp-publisher login expects. */
export function privateHex(privateKey) {
  const { d } = privateKey.export({ format: "jwk" });
  return Buffer.from(d, "base64url").toString("hex");
}

import { ConfigError, loadConfig } from "./config.js";
import { CredentialsError } from "./types.js";
import { DeliveryClient } from "./client.js";

/** Live READ-ONLY smoke check: lists the most recent express claim (if any). */
async function main(): Promise<void> {
  const client = new DeliveryClient(loadConfig());
  const result = await client.searchClaims({ limit: 1 });
  console.log(JSON.stringify(result, null, 2));
}

main().catch((err) => {
  // A missing or malformed token is a user error, not a bug: no stack.
  const userError = err instanceof ConfigError || err instanceof CredentialsError;
  console.error("smoke failed:", userError ? err.message : err);
  process.exit(1);
});

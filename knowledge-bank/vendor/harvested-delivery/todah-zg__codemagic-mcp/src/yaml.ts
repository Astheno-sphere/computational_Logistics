import { Ajv } from "ajv";
import * as yaml from "js-yaml";
export { getYamlTemplate, listYamlTemplateTypes } from "./templates.js";

const ajv = new Ajv({ allErrors: true, strict: false });

// Cache the compiled validator, not the raw schema — one compile, ever.
// Cleared on any fetch/compile failure so the next call retries cleanly.
let validatorPromise: Promise<ReturnType<typeof ajv.compile>> | null = null;

function getValidator(): Promise<ReturnType<typeof ajv.compile>> {
  if (!validatorPromise) {
    validatorPromise = fetch("https://codemagic.io/codemagic-schema.json", {
      signal: AbortSignal.timeout(10_000),
    })
      .then(async r => {
        if (!r.ok) throw new Error(`Failed to fetch schema: ${r.status} ${r.statusText}`);
        return ajv.compile(await r.json() as object);
      })
      .catch(err => {
        validatorPromise = null; // transient failure — allow retry on next call
        throw err;
      });
  }
  return validatorPromise;
}

/** Reset the validator cache — for use in tests only. */
export function _resetSchemaCache(): void {
  validatorPromise = null;
}

export interface ValidationResult {
  valid: boolean;
  errors: string[];
}
/**
 * Validate a codemagic.yaml string against the official Codemagic JSON schema.
 * The schema is fetched from codemagic.io on first call and cached for subsequent calls.
 * @param yamlContent - Full contents of a codemagic.yaml file.
 * @returns Validation result with a list of error messages if invalid.
 */
export async function validateCodemagicYaml(yamlContent: string): Promise<ValidationResult> {
  let parsed: unknown;
  try {
    parsed = yaml.load(yamlContent);
  } catch (e) {
    return {
      valid: false,
      errors: [`YAML syntax error: ${e instanceof Error ? e.message : String(e)}`],
    };
  }

  const validate = await getValidator();
  const valid = validate(parsed) as boolean;

  return {
    valid,
    errors: valid ? [] : (validate.errors ?? []).map(e => `${e.instancePath} ${e.message ?? ""}`.trim()),
  };
}
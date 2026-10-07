import { describe, it, expect, vi, beforeEach } from "vitest";
import { validateCodemagicYaml, _resetSchemaCache } from "../src/yaml.js";

// A minimal schema that requires a top-level 'workflows' key —
// enough to test valid vs. invalid without fetching the real schema.
const mockSchema = {
  type: "object",
  properties: {
    workflows: { type: "object" },
  },
  required: ["workflows"],
};

beforeEach(() => {
  _resetSchemaCache();

  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: true,
    json: async () => mockSchema,
  }));
});

describe("validateCodemagicYaml", () => {
  it("returns valid for yaml with a workflows key", async () => {
    const result = await validateCodemagicYaml("workflows:\n  build:\n    name: Build");
    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });

  it("returns invalid for yaml missing the workflows key", async () => {
    const result = await validateCodemagicYaml("name: not-valid");
    expect(result.valid).toBe(false);
    expect(result.errors.length).toBeGreaterThan(0);
  });

  it("catches YAML syntax errors before schema validation", async () => {
    const result = await validateCodemagicYaml("workflows:\n  - invalid: [unclosed");
    expect(result.valid).toBe(false);
    expect(result.errors[0]).toMatch(/YAML syntax error/);
  });

  it("returns errors as readable strings", async () => {
    const result = await validateCodemagicYaml("name: missing-workflows");
    expect(result.errors.every(e => typeof e === "string")).toBe(true);
  });
});
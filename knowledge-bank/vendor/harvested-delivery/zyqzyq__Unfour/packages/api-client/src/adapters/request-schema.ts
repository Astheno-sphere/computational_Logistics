import type { KeyValue } from "@unfour/command-client";
import { z } from "zod";
import type { ApiAuthConfig } from "../model/types";

const emptyString = z.preprocess((value) => (typeof value === "string" ? value : ""), z.string());

const keyValueSchema = z.object({
  enabled: z.preprocess((value) => (typeof value === "boolean" ? value : true), z.boolean()),
  key: z.string(),
  value: z.preprocess((value) => (value == null ? "" : String(value)), z.string()),
});

const authConfigSchema = z.discriminatedUnion("type", [
  z.object({ type: z.literal("none") }),
  z.object({
    token: emptyString,
    type: z.literal("bearer"),
  }),
  z.object({
    password: emptyString,
    type: z.literal("basic"),
    username: emptyString,
  }),
  z.object({
    addTo: z.preprocess((value) => (value === "query" ? "query" : "header"), z.enum(["header", "query"])),
    key: emptyString,
    type: z.literal("api-key"),
    value: emptyString,
  }),
]);

export function parseAuthConfigWithSchema(value: unknown): ApiAuthConfig {
  const parsed = authConfigSchema.safeParse(parseJsonValue(value));
  return parsed.success ? parsed.data : { type: "none" };
}

export function parseKeyValuesWithSchema(value: unknown): KeyValue[] {
  const parsedValue = parseJsonValue(value);

  if (Array.isArray(parsedValue)) {
    return parsedValue
      .map((item) => keyValueSchema.safeParse(item))
      .filter((result): result is z.ZodSafeParseSuccess<KeyValue> => result.success)
      .map((result) => result.data);
  }

  if (typeof parsedValue === "object" && parsedValue !== null) {
    return Object.entries(parsedValue).map(([key, itemValue]) => ({
      enabled: true,
      key,
      value: itemValue == null ? "" : String(itemValue),
    }));
  }

  return [];
}

function parseJsonValue(value: unknown): unknown {
  if (typeof value !== "string") {
    return value;
  }

  try {
    return parseJsonValue(JSON.parse(value));
  } catch {
    return value;
  }
}

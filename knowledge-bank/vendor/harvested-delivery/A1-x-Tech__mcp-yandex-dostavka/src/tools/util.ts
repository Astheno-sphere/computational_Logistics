import type { CallToolResult } from "@modelcontextprotocol/sdk/types.js";
import { z } from "zod";

/**
 * Shared zod schema FACTORIES (not shared consts): reusing one zod object
 * across two fields makes zod-to-json-schema dedupe them into a `$ref`
 * (e.g. created_to → #/properties/created_from), which some tool-schema
 * consumers (OpenAI Apps review) don't dereference and flag as `any`.
 * A fresh object per field keeps each one inlined with its type + pattern.
 */

/** Идентификатор экспресс-заявки (claim_id). */
export const claimId = () =>
  z
    .string()
    .min(1)
    .describe("Идентификатор заявки (claim_id, 32–64 символа) из ответа express_create_claim или express_search_claims.");

/** Класс экспресс-доставки; wire-значения совпадают с нормализованными. */
export const taxiClassEnum = () => z.enum(["courier", "express", "cargo", "sdd_multislot"]);

/** Тип кузова для taxi_class=cargo. */
export const cargoTypeEnum = () => z.enum(["van", "lcv_m", "lcv_l"]);

/** Способ оплаты получателем в платформенном контуре. */
export const paymentMethodEnum = () => z.enum(["already_paid", "card_on_receipt", "postpay"]);

/** An ISO-8601 / RFC3339 timestamp, e.g. 2026-01-01T00:00:00Z. */
export const rfc3339Date = () =>
  z
    .string()
    .regex(
      /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$/,
      "Must be an ISO-8601 timestamp, e.g. 2026-01-01T00:00:00Z",
    );

/** Wraps a value as a compact-JSON tool result (compact: the consumer is an LLM). */
export function ok(data: unknown): CallToolResult {
  const text = typeof data === "string" ? data : JSON.stringify(data);
  return { content: [{ type: "text", text: text ?? "null" }] };
}

export function fail(err: unknown): CallToolResult {
  let message = err instanceof Error ? err.message : String(err);
  // Surface the underlying cause (e.g. the network error behind a timeout) — no
  // secrets live in cause, and it makes failures far easier to diagnose.
  if (err instanceof Error && err.cause instanceof Error) message += ` (${err.cause.message})`;
  return { content: [{ type: "text", text: `Error: ${message}` }], isError: true };
}

/**
 * MCP tool annotations — hints the consuming client can use to gate or label a
 * tool. Yandex Delivery is a WRITE API (claims and orders are created, accepted
 * and cancelled), so unlike a read-only server every tool picks its annotation
 * consciously:
 *
 *   READ_ONLY   — side-effect-free reads (price checks, info, search, tracking);
 *   WRITE       — state-changing but not destructive (create/accept/confirm);
 *   DESTRUCTIVE — cancellations and the raw escape hatch (it can call anything).
 */
// All four hints set explicitly: some clients (OpenAI Apps review) require
// readOnlyHint, destructiveHint and openWorldHint on every tool.
export const READ_ONLY = {
  readOnlyHint: true,
  destructiveHint: false,
  idempotentHint: true,
  openWorldHint: true,
} as const;

export const WRITE = {
  readOnlyHint: false,
  destructiveHint: false,
  idempotentHint: false,
  openWorldHint: true,
} as const;

export const DESTRUCTIVE = {
  readOnlyHint: false,
  destructiveHint: true,
  idempotentHint: false,
  openWorldHint: true,
} as const;

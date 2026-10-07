/**
 * Token accounting → approximate dollar cost.
 *
 * Prices are per million tokens (standard list prices; intro discounts not
 * applied), cache reads bill at ~10% of input, 5-minute cache writes at 1.25×.
 * Unknown models fall back to Sonnet-tier pricing and are flagged approximate.
 */

export interface UsageTotals {
  input_tokens: number;
  output_tokens: number;
  cache_read_input_tokens: number;
  cache_creation_input_tokens: number;
}

export const EMPTY_USAGE: UsageTotals = {
  input_tokens: 0,
  output_tokens: 0,
  cache_read_input_tokens: 0,
  cache_creation_input_tokens: 0,
};

const PRICES: Record<string, { in: number; out: number }> = {
  "claude-sonnet-5": { in: 3, out: 15 },
  "claude-opus-4-8": { in: 5, out: 25 },
  "claude-opus-4-7": { in: 5, out: 25 },
  "claude-opus-4-6": { in: 5, out: 25 },
  "claude-haiku-4-5": { in: 1, out: 5 },
};

export function addUsage(
  total: UsageTotals,
  delta: { [K in keyof UsageTotals]?: number | null } | null | undefined,
): UsageTotals {
  if (!delta) return total;
  return {
    input_tokens: total.input_tokens + (delta.input_tokens ?? 0),
    output_tokens: total.output_tokens + (delta.output_tokens ?? 0),
    cache_read_input_tokens:
      total.cache_read_input_tokens + (delta.cache_read_input_tokens ?? 0),
    cache_creation_input_tokens:
      total.cache_creation_input_tokens + (delta.cache_creation_input_tokens ?? 0),
  };
}

export function estimateCostUsd(model: string, usage: UsageTotals): number {
  const price = PRICES[model] ?? PRICES["claude-sonnet-5"];
  return (
    (usage.input_tokens * price.in +
      usage.cache_read_input_tokens * price.in * 0.1 +
      usage.cache_creation_input_tokens * price.in * 1.25 +
      usage.output_tokens * price.out) /
    1_000_000
  );
}

export function formatCost(usd: number): string {
  if (usd < 0.005) return "<$0.01";
  return `~$${usd.toFixed(2)}`;
}

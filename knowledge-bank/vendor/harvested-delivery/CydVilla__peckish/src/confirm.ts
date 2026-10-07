/**
 * Pluggable human-confirmation gates. The order-placement gate is the hard
 * safety boundary of this app: no code path may call `order submit` without a
 * human approving through whichever surface is active:
 *
 *   terminal → typed "yes" at a readline prompt   (index.ts)
 *   MCP      → client elicitation dialog          (mcp.ts)
 *   web      → confirmation modal                 (web.ts)
 *
 * Fail closed: with no provider registered, everything is declined.
 */

export type Confirmer = (summary: string) => Promise<boolean>;

interface Providers {
  /** Placing a real order (charges money). Strictest UX per surface. */
  order: Confirmer;
  /** Account-level changes (e.g. default address). Lighter y/N-style. */
  action: Confirmer;
}

let providers: Providers | null = null;

export function setConfirmationProviders(p: Providers): void {
  providers = p;
}

export async function confirmOrderPlacement(summary: string): Promise<boolean> {
  if (!providers) return false;
  return providers.order(summary);
}

export async function confirmAction(summary: string): Promise<boolean> {
  if (!providers) return false;
  return providers.action(summary);
}

// ---------------------------------------------------------------------------
// Terminal providers (used by the REPL surface)
// ---------------------------------------------------------------------------

import type { Interface as ReadlineInterface } from "node:readline";

export function registerTerminalProviders(rl: ReadlineInterface): void {
  const ask = (q: string): Promise<string> => new Promise((resolve) => rl.question(q, resolve));

  setConfirmationProviders({
    async order(summary) {
      process.stdout.write(
        `\n\x1b[1m\x1b[33m━━━ CONFIRM ORDER ━━━\x1b[0m\n${summary}\n` +
          `\x1b[1mThis will place a real order and charge your payment method.\x1b[0m\n`,
      );
      const answer = await ask(
        `Type \x1b[1myes\x1b[0m to place the order, anything else to cancel: `,
      );
      return answer.trim().toLowerCase() === "yes";
    },
    async action(summary) {
      const answer = await ask(`\n${summary}\nProceed? [y/N]: `);
      return ["y", "yes"].includes(answer.trim().toLowerCase());
    },
  });
}

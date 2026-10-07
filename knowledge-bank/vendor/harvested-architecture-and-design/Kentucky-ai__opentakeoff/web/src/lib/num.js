// Leaf numeric helpers — import nothing, so anything may import from here
// without creating a cycle (reportColumns.js and totals.js both do).

export const round2 = (n) => Math.round((n + Number.EPSILON) * 100) / 100;

// Guarded display formatter — Number(v) || 0 so a missing/non-numeric value
// (row not yet computed, a stale prop) renders "0" instead of throwing.
export const num = (v, d = 1) => (Number(v) || 0).toLocaleString(undefined, { maximumFractionDigits: d });

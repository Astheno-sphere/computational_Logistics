// Shape-level phase/area labels (issue #110) — a project-level vocabulary
// persisted as the flat `shape_labels` payload key: [string]. Unlike condition
// columns (which key per-condition attrs by column id), a shape carries at most
// one assigned label directly on `shape.label`; unassigned = key absent. The
// vocabulary is therefore a FLAT string list, not the {id,name,values} column
// shape. Pure helpers here so hydrate defensiveness and the rename-rewrite are
// testable in isolation from the canvas.

// The visible-string rule everything below shares: a string with visible
// content counts; anything else — non-string, empty, whitespace-only — is
// nothing. Returned untrimmed (stored strings are never mutated).
const visible = (v) => (typeof v === "string" && v.trim() ? v : "");

// Defensive hydrate for shape_labels: non-array → [], filter to visible strings
// and dedupe (first occurrence wins) — the same hazard sanitizeConditionColumns
// filters its `values` for. A label value keys React chips/options, so empties
// and duplicates break rendering, and a non-string must never reach a React
// child. No reserved-id concept applies (these are label values, not column ids).
export function sanitizeShapeLabels(raw) {
  if (!Array.isArray(raw)) return [];
  return [...new Set(raw.filter(visible))];
}

// The assigned-value rule, shared by EVERY reader of a shape's label (chip,
// grouping, export, select). sanitizeShapeLabelsOnShapes strips violating
// labels at hydrate, but readers still route through here so the rule has
// exactly one definition. A shape with no label reads as "" (unassigned).
export function shapeLabelValue(shape) {
  return visible(shape?.label);
}

// Defensive hydrate for per-shape labels. Unlike sanitizeConditionAttrs (which
// always clones), this preserves object identity wherever it legally can: the
// shapes array is large and React re-renders on new references, so a hydrate
// that clones every shape would churn the whole canvas. Three cases:
//   - label ABSENT → pass through by identity (nothing to clean);
//   - label present and visible → pass through by identity (already valid);
//   - label present but invalid (non-string/empty/whitespace) → the ONLY case
//     that clones: a new shape with the `label` key removed, all else preserved.
export function sanitizeShapeLabelsOnShapes(shapes) {
  if (!Array.isArray(shapes)) return [];
  return shapes.map((s) => {
    if (!(s && typeof s === "object") || !("label" in s)) return s;
    if (visible(s.label)) return s;
    const { label, ...rest } = s;   // drop the offending key, keep everything else
    return rest;
  });
}

// Assign (or clear) the label on ONE shape, by id — the single-shape reassign
// the Select tool drives (#111). A visible value sets it; an empty/whitespace/
// nullish value CLEARS it by removing the key (the shapeLabelValue-absent state,
// not a "" that would render as an empty group header). Only the matching shape
// moves to a new object; every other shape — and a clear on an already-unlabeled
// shape — keeps its identity.
export function assignShapeLabel(shapes, id, value) {
  const v = visible(value);
  return shapes.map((s) => {
    if (s?.id !== id) return s;
    if (v) return { ...s, label: v };
    if (!("label" in s)) return s;   // already unlabeled — nothing to clear
    const { label, ...rest } = s;    // drop the key, keep everything else
    return rest;
  });
}

// Rewrite assignments when a vocabulary value is renamed — typo-fixing is the
// common edit, and remove+re-add would strand every labeled shape on a
// "(removed)" value. Only exact matches move to a new object (React re-render);
// every other shape — different label, or none at all — keeps its identity.
export function renameShapeLabel(shapes, oldV, newV) {
  return shapes.map((s) => (s?.label === oldV ? { ...s, label: newV } : s));
}

// Custom condition columns (issue #33) — a project-level vocabulary persisted
// as the `condition_columns` payload key: [{ id: "col-…", name, values: [string] }].
// Per-condition assignment lives on c.attrs = { [colId]: value }, keyed by
// column ID so renames never orphan assignments; unassigned = key absent.
// Pure helpers here so hydrate defensiveness and the rename-rewrite are testable.

// The visible-string rule everything below shares: a string with visible
// content counts; anything else — non-string, empty, whitespace-only — is
// nothing. Returned untrimmed (stored strings are never mutated).
const visible = (v) => (typeof v === "string" && v.trim() ? v : "");

// Defensive hydrate for condition_columns: non-array → [], items must carry a
// non-empty string id and a string name, values string-filtered — the same
// hazard hydrate string-filters client_info for (a corrupted record must not
// put a non-string where a React child or <option> renders). Values also drop
// empties/whitespace (an empty value collides with the selects' Unassigned
// option, value="") and dedupe, and later duplicate column ids are dropped —
// values and ids key React options/chips, so duplicates break rendering.
// Unknown item fields pass through (the scale_source precedent: stripping a
// future field on load would persist the loss on the next autosave).
export function sanitizeConditionColumns(raw) {
  if (!Array.isArray(raw)) return [];
  const seenIds = new Set();
  return raw
    .filter((c) => {
      if (!(c && typeof c === "object" && !Array.isArray(c) && typeof c.id === "string" && c.id && typeof c.name === "string")) return false;
      if (c.id === "sheet") return false;   // reserved by the report's Group select — a column with this id would be shadowed by the built-in Sheet mode
      if (seenIds.has(c.id)) return false;
      seenIds.add(c.id);
      return true;
    })
    .map((c) => ({ ...c, values: [...new Set((Array.isArray(c.values) ? c.values : []).filter(visible))] }));
}

// The assigned-value rule, shared by EVERY attrs reader (table/CSV getter,
// grouping, JSON export, selects, badge). sanitizeConditionAttrs strips
// violating values at hydrate, but readers still route through here so the
// rule has exactly one definition.
export function attrValue(attrs, colId) {
  return visible(attrs?.[colId]);
}

// Defensive hydrate for per-condition attrs (the client_info precedent —
// conditions otherwise pass wholesale): a non-object attrs is dropped, and
// values that fail attrValue's rule are stripped, so downstream readers can
// trust what they get. Conditions without attrs pass through untouched.
export function sanitizeConditionAttrs(conditions) {
  if (!Array.isArray(conditions)) return [];
  return conditions.map((c) => {
    const cur = c?.attrs;
    if (cur === undefined) return c;
    const attrs = {};
    if (cur && typeof cur === "object" && !Array.isArray(cur)) {
      for (const [k, v] of Object.entries(cur)) if (visible(v)) attrs[k] = v;
    }
    return { ...c, attrs };
  });
}

// Display label for a column — a whitespace-only name is as unusable as an
// empty one (blank table/CSV headers, a blank Group option, "Grouped by ⟨⟩"
// in print), so both fall back. The stored name is never mutated.
export function columnLabel(cc) {
  return typeof cc?.name === "string" && cc.name.trim() ? cc.name : "Untitled";
}

// Rewrite assignments when a vocabulary value is renamed — typo-fixing is the
// common edit, and remove+re-add would strand every assigned condition on a
// "(removed)" value. Only exact matches on THIS column move; other columns and
// untouched conditions keep their object identity.
export function renameColumnValue(conditions, colId, oldV, newV) {
  return conditions.map((c) => (c.attrs?.[colId] === oldV ? { ...c, attrs: { ...c.attrs, [colId]: newV } } : c));
}

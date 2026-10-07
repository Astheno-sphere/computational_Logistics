import { describe, expect, it } from "vitest";
import {
  calculateAutoFitWidth,
  isLikelyJson,
  MAX_CELL_PREVIEW_LENGTH,
  truncatePreview,
  truncateText,
} from "./table-data-grid-helpers";

describe("table data grid display limits", () => {
  it("caps the rendered cell preview at the configured maximum", () => {
    const preview = truncatePreview("x".repeat(MAX_CELL_PREVIEW_LENGTH + 20));

    expect(preview).toHaveLength(MAX_CELL_PREVIEW_LENGTH);
    expect(preview.endsWith("…")).toBe(true);
  });

  it("keeps generic truncation within the requested maximum", () => {
    expect(truncateText("123456", 4)).toBe("123…");
    expect(truncateText("123", 4)).toBe("123");
  });

  it("caps auto-fit width when a cell contains very long content", () => {
    expect(calculateAutoFitWidth(
      { dataType: "JSON", name: "payload" },
      [JSON.stringify({ content: "x".repeat(5_000) })],
    )).toBe(560);
  });

  it("detects object and array shaped JSON without parsing oversized values", () => {
    expect(isLikelyJson('{"name":"Ada"}')).toBe(true);
    expect(isLikelyJson("[1,2,3]")).toBe(true);
    expect(isLikelyJson("plain text")).toBe(false);
  });
});

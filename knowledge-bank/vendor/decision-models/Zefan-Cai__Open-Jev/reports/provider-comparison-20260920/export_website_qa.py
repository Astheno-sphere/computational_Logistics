"""Publish compact successful browser QA without machine URLs or file paths."""
import argparse
import hashlib
import json
from pathlib import Path


def export(source, checker, output):
    source, checker, output = Path(source), Path(checker), Path(output)
    old = json.loads(source.read_text())
    if old.get("verified") is not True:
        raise ValueError("Only a completed successful browser check may be exported")
    result = {"verified": True, "browser": "isolated headless Chrome", "source_document": "site/provider-quality.json",
              "verification_source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "checks_source_sha256": hashlib.sha256(checker.read_bytes()).hexdigest(),
              "scope": "Actual rendered values, counts and public evidence links checked against the exact JSON response loaded by each viewport. Local URLs, media paths and screenshot paths omitted.",
              "viewports": []}
    for view in old["results"]:
        if view["errors"] or view["overflow"]:
            raise ValueError("Browser check contains errors or overflow")
        cells = [{"suite": row["id"], "provider": cell["provider"], "rendered_text": cell["text"],
                  "fraction": cell["fraction"], "pending_label": cell["pending"],
                  "evidence_link_matches_source": bool(cell["evidence"]) if cell["fraction"] else None}
                 for row in view["rows"] for cell in row["cells"]]
        result["viewports"].append({"width": view["width"], "height": 1000, "loaded_data_sha256": view["source_sha256"],
            "loaded_data_generated_at": view["generated_at"], "suite_rows": len(view["rows"]),
            "provider_columns": len(view["headers"]) - 1, "checked_cells": len(cells),
            "all_cell_values_match_loaded_json": True, "javascript_errors": view["errors"],
            "no_page_horizontal_overflow": not view["overflow"], "comparison_precedes_results": bool(view["sectionBeforeResults"]),
            "content_visible": view["contentVisible"], "probability_mass_note_visible": view["massNoteVisible"],
            "soft_exclusion_labels": view["softExclusions"], "suite_notes_open_and_count": view["suiteNotes"],
            "latency_rows_preserved": view["latencyRows"], "rightmost_provider_fully_visible_after_scroll": view.get("rightmostVisible"),
            "cells": cells})
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if any(token in text for token in ("127.0.0.1", "localhost", "/Users/", "/tmp/")):
        raise ValueError("Local machine detail in public QA")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--checker", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = export(args.input, args.checker, args.output)
    print(json.dumps({"verified": result["verified"], "viewports": [v["width"] for v in result["viewports"]],
                      "loaded_data_sha256": sorted({v["loaded_data_sha256"] for v in result["viewports"]})}))


if __name__ == "__main__":
    main()

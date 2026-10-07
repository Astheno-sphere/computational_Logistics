#!/usr/bin/env python3
"""Render a labeled English display derivative; preserve the original evidence.

Uses the CPU-only demo renderer. The original catalog request, character offsets
and media are never edited. Run from the repository root with Pillow and ffmpeg.
"""
import copy
import json
from pathlib import Path

from render_demo_videos import render_one, sha256, verify

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"


def main():
    catalog = SITE / "catalog.json"
    original = next(item for item in json.loads(catalog.read_text())["items"]
                    if item["id"] == "phone-extraction")
    preserved = [catalog, *(SITE / original[key] for key in
                           ("video", "poster", "captions", "transcript"))]
    before = {str(path.relative_to(ROOT)): sha256(path) for path in preserved}
    item = copy.deepcopy(original)
    for key, extension in (("video", "mp4"), ("poster", "jpg"),
                           ("captions", "vtt"), ("transcript", "txt")):
        item[key] = f"media/phone-extraction-en.{extension}"
    item["display_context"] = (
        "English display translation\nRequested field: mobile\n\n"
        "Fictional contact example; café contact card; do not dial.\n"
        "Billing: +1 416-555-0156 | Region: CA\n"
        "Mobile: 07700 900123 | Region: GB\n"
        "Support: +1 202-555-0123 | Region: US")
    note = ("English display translation. Original request, Unicode character "
            "offsets and source video remain in the evidence downloads.")
    item["limitations"] = [note, *original["limitations"]]
    render_one((item, str(SITE)))
    checked = verify([item], SITE)
    assert before == {str(path.relative_to(ROOT)): sha256(path) for path in preserved}
    assert item["request"] == original["request"]
    report = {"scope": note, "inference_performed": False,
              "request_and_offsets_unchanged": True,
              "original_files_sha256": before,
              "display_context": item["display_context"],
              "renderer_sha256": sha256(ROOT / "scripts/render_demo_videos.py"),
              "videos": checked,
              "files": {item[key]: sha256(SITE / item[key]) for key in
                        ("video", "poster", "captions", "transcript")}}
    (SITE / "media/phone-extraction-en.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": "passed", "original_files_unchanged": True,
                      "video": item["video"]}))


if __name__ == "__main__":
    main()

"""Copy the checked-in static gallery into a GitHub Pages /open-jev/ subsite."""

import argparse
import json
from pathlib import Path
import shutil


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True,
                        help="The personal-site checkout's open-jev directory")
    parser.add_argument("--prune-media", action="store_true",
                        help="Remove prior generated media absent from the curated source site")
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1] / "site"
    destination = args.destination.expanduser().resolve()
    if destination.name != "open-jev" or destination == source:
        parser.error("destination must be a separate directory named open-jev")
    catalog = json.loads((source / "catalog.json").read_text())
    if catalog.get("status") != "complete":
        parser.error("catalog is not complete")
    required = {"index.html", "styles.css", "app.js", "catalog.json"}
    for item in catalog["items"]:
        required.update(item[key] for key in ("video", "poster", "captions"))
    if catalog.get("overview"):
        required.update(catalog["overview"][key] for key in ("video", "poster", "captions", "transcript"))
    for relative in required:
        path = source / relative
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(source):
            parser.error(f"missing or unsafe static asset: {relative}")
    allowed = {".html", ".css", ".js", ".json", ".jsonl", ".mp4", ".jpg", ".png", ".vtt", ".txt", ".svg", ".md"}
    stale = []
    if args.prune_media:
        if not catalog.get("showcase_selection"):
            parser.error("media pruning requires a reviewed showcase selection")
        media = destination / "media"
        if media.is_symlink():
            parser.error("refusing symlink media directory")
        for path in media.iterdir() if media.exists() else []:
            if path.is_symlink():
                parser.error(f"refusing symlink media asset: {path}")
            if path.is_file() and path.suffix in {".mp4", ".jpg", ".vtt", ".txt", ".json"} and not (source / "media" / path.name).exists():
                stale.append(path)
    copied = []
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        if path.is_symlink() or path.suffix not in allowed:
            parser.error(f"unexpected site file: {path.relative_to(source)}")
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink():
            parser.error(f"refusing symlink destination: {target}")
        shutil.copyfile(path, target)
        copied.append(str(path.relative_to(source)))
    for path in stale:
        path.unlink()
    print(json.dumps({"destination": str(destination), "files": len(copied),
                      "videos": len(catalog["items"]), "deleted_files": len(stale)}))


if __name__ == "__main__":
    main()

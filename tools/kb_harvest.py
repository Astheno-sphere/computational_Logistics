#!/usr/bin/env python3
"""Harvest candidate repos from curated lists already in the bank, instead of from memory.

Reads chosen sections of vendored awesome-lists, extracts GitHub repo links with their one-line
description, drops ones already in sources.yaml, and appends the rest to sources.yaml under a
`harvested-<section>` category (run kb_sync.py afterwards; it applies the license gate).
Usage: python3 tools/kb_harvest.py [--dry-run]
"""
import argparse, re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
KB = ROOT / "knowledge-bank"
LISTS = {
    "claude-skill-registries/punkpeye__awesome-mcp-servers/README.md": [
        "delivery", "location-services", "environment-and-nature",
        "real-estate", "industrial--iot",
    ],
}
# Hand-picked from sections that are otherwise off-domain (awesome-mcp "Architecture & Design" = software/UI).
EXTRA = [("Kentucky-ai/opentakeoff", "harvested-architecture-and-design", "Construction quantity takeoff MCP")]
SECTION = re.compile(r'^#{2,3} .*?<a name="([^"]+)"></a>(.*)$')
LINK = re.compile(r"\[([^\]]+)\]\(https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?\)\s*(.*)$")


def harvest(path, wanted):
    out, current = [], None
    for line in path.read_text(errors="replace").splitlines():
        m = SECTION.match(line)
        if m:
            current = m.group(1) if m.group(1) in wanted else None
            continue
        if current and line.lstrip().startswith(("-", "*")):
            l = LINK.search(line)
            if l:
                owner, repo, rest = l.group(2), l.group(3), l.group(4)
                # rest looks like: "[![badge](..)](..) 📇 ☁️ - Description". Keep what follows " - ".
                desc = rest.split(" - ", 1)[1] if " - " in rest else rest
                desc = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", desc)
                desc = re.sub(r"[`*_]|<[^>]+>", "", desc).strip()[:160]
                out.append((current, owner, repo, desc))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    cfg = yaml.safe_load((KB / "sources.yaml").read_text())
    have = {e["id"].lower() for e in cfg["sources"]}
    added = []
    for rel, wanted in LISTS.items():
        for section, owner, repo, desc in harvest(KB / "vendor" / rel, set(wanted)):
            rid = "%s__%s" % (owner, repo)
            if rid.lower() in have:
                continue
            have.add(rid.lower())
            added.append({"id": rid, "url": "https://github.com/%s/%s.git" % (owner, repo),
                          "category": "harvested-" + section.replace("--", "-"),
                          "why": (desc or "listed in awesome-mcp-servers") + " (from awesome-mcp-servers: %s)" % section})
    for owner_repo, cat, why in EXTRA:
        rid = owner_repo.replace("/", "__")
        if rid.lower() not in have:
            have.add(rid.lower())
            added.append({"id": rid, "url": "https://github.com/%s.git" % owner_repo, "category": cat, "why": why})
    cats = cfg.setdefault("categories", {})
    for e in added:
        cats.setdefault(e["category"], "Harvested from awesome-mcp-servers section `%s`; not yet reviewed by a person."
                        % e["category"][len("harvested-"):])
    print("new candidates:", len(added))
    for e in added:
        print("  %-28s %s" % (e["category"], e["id"]))
    if not a.dry_run and added:
        cfg["sources"] += added
    if not a.dry_run:
        (KB / "sources.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False, width=200, allow_unicode=True))


if __name__ == "__main__":
    main()

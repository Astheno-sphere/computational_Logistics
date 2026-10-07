#!/usr/bin/env python3
"""Build the knowledge bank from knowledge-bank/sources.yaml.

For every source: shallow-clone, detect the license from the repo's own license
files, then either vendor it (permissive licenses, or share-alike when the entry
opts in) or record a link-only pointer (copyleft, unknown, no license).
Nothing is vendored on a guess. Output:
  knowledge-bank/vendor/<category>/<owner>__<repo>/   verbatim snapshot, no .git
  knowledge-bank/MANIFEST.json                        machine-readable record
  knowledge-bank/SOURCES.md, ATTRIBUTION.md           generated
Usage: python3 tools/kb_sync.py [--only ID ...] [--check]
"""
import argparse, datetime, json, os, re, shutil, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
KB = ROOT / "knowledge-bank"
# Keep everything except what GitHub itself refuses: files over its 100 MB hard limit, and (below)
# files with token-shaped strings, which push protection blocks. Compiled caches are regenerable noise.
MAX_FILE = 99 * 1024 * 1024
SKIP_EXT = {".pyc", ".pyo", ".class"}
MAX_REPO = 1500 * 1024 * 1024        # per source; beyond this, use include: paths (push size)
PERMISSIVE = {"MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC",
              "Unlicense", "CC0-1.0", "BSL-1.0", "Zlib", "CC-BY-4.0"}
OPEN_COPYLEFT = {"GPL", "LGPL", "AGPL", "MPL", "EPL", "LLGPL", "CC-BY-SA-4.0"}  # open source: copy verbatim, keep isolated
SECRET_RE = re.compile(
    r"gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{20,}|glpat-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}"
    r"|sk-ant-[A-Za-z0-9_-]{20,}|sk-(?:proj-)?[A-Za-z0-9_-]{32,}|xox[abprs]-[0-9A-Za-z-]{20,}|AIza[0-9A-Za-z_-]{35}"
    r"|[sr]k_live_[0-9A-Za-z]{20,}|npm_[A-Za-z0-9]{36}|SG\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}"
    r"|[sp]k\.eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}"      # Mapbox access tokens
    r"|-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY")


def has_secret(path):
    """Token-shaped strings, even fake test fixtures: GitHub push protection rejects them, and we
    cannot tell a fixture from a leak, so such files are skipped."""
    try:
        return bool(SECRET_RE.search(path.read_text(errors="ignore")))
    except OSError:
        return False


GIT_CONTROL = {".gitignore", ".gitattributes", ".gitmodules"}   # would alter how git treats our repo
LICENSE_FILE = re.compile(r"^(LICEN[SC]E|COPYING|NOTICE|UNLICENSE)([._-].*)?$", re.I)


def classify(text):
    """Return an SPDX-ish id from license text, or 'UNKNOWN'. Order matters."""
    t = " ".join(text.split())
    low = t.lower()
    gnu = [(low.find(k), v) for k, v in (("gnu affero general public license", "AGPL"),
           ("gnu lesser general public license", "LGPL"), ("gnu general public license", "GPL"))
           if k in low]
    if gnu:                              # the license's own title appears first
        return min(gnu)[1]
    if "mozilla public license" in low:
        return "MPL"
    if "eclipse public license" in low:
        return "EPL"
    if "lisp lesser general public license" in low:
        return "LLGPL"
    if "attribution-sharealike 4.0" in low:
        return "CC-BY-SA-4.0"
    if "attribution-noncommercial" in low or "noderivatives" in low:
        return "CC-BY-NC/ND"
    if "attribution 4.0 international" in low:
        return "CC-BY-4.0"
    if "cc0 1.0" in low or "creative commons zero" in low:
        return "CC0-1.0"
    if "apache license" in low and "version 2.0" in low:
        return "Apache-2.0"
    if "boost software license" in low:
        return "BSL-1.0"
    if "this is free and unencumbered software" in low:
        return "Unlicense"
    if "permission is hereby granted, free of charge" in low:
        return "MIT"
    if "redistribution and use in source and binary forms" in low:
        return "BSD-3-Clause" if "neither the name" in low or "the names of" in low else "BSD-2-Clause"
    if "permission to use, copy, modify, and/or distribute" in low or \
       "permission to use, copy, modify, and distribute this software for any purpose with or without fee" in low:
        return "ISC"
    if "zlib" in low and "altered source versions must be plainly marked" in low:
        return "Zlib"
    return "UNKNOWN"


def detect_license(repo):
    found = {}
    for p in sorted(repo.iterdir()):
        if p.is_file() and LICENSE_FILE.match(p.name) and not p.name.upper().startswith("NOTICE"):
            found[p.name] = classify(p.read_text(errors="replace"))
    ids = sorted(set(found.values()) - {"UNKNOWN"})
    if not found:
        return "NONE", found
    if len(ids) == 1:
        return ids[0], found
    if not ids:
        return "UNKNOWN", found
    return "MIXED:" + "+".join(ids), found


def is_copyleft(spdx):
    parts = spdx[6:].split("+") if spdx.startswith("MIXED:") else [spdx]
    return any(p in OPEN_COPYLEFT for p in parts)


def decide(spdx, entry):
    """Open source (permissive or copyleft) is vendored verbatim. No license, all rights
    reserved, non-commercial/no-derivatives or unrecognised terms are not open source:
    copying them would be infringement, so they stay link-only."""
    if entry.get("policy") == "link-only":
        return "link-only", "marked link-only in sources.yaml"
    parts = spdx[6:].split("+") if spdx.startswith("MIXED:") else [spdx]
    if all(p in PERMISSIVE or p in OPEN_COPYLEFT for p in parts):
        return "vendored", "copyleft open source: verbatim, isolated" if is_copyleft(spdx) else "permissive license"
    if spdx == "NONE":
        return "link-only", "no license file: all rights reserved by default"
    return "link-only", "license %s is not open source or not recognised" % spdx


def run(cmd, cwd=None, timeout=600):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                          env=dict(os.environ, GIT_TERMINAL_PROMPT="0"))


def copy_tree(src, dst, include, exclude=()):
    n = bytes_ = 0
    skipped = []
    dst.mkdir(parents=True, exist_ok=True)
    roots = [src / i for i in include] if include else [src]
    for top in roots:
        if not top.exists():
            skipped.append("missing include path: %s" % top.relative_to(src))
            continue
        for dirpath, dirs, files in os.walk(top):
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
            for f in files:
                s = Path(dirpath) / f
                if s.is_symlink() or f in GIT_CONTROL:
                    continue
                size = s.stat().st_size
                rel = s.relative_to(src)
                if s.suffix.lower() in SKIP_EXT or any(str(rel).startswith(x) for x in exclude):
                    skipped.append("%s (excluded type/path)" % rel)
                    continue
                if size > MAX_FILE:
                    skipped.append("%s (%.1f MB > cap)" % (rel, size / 1e6))
                    continue
                d = dst / rel
                d.parent.mkdir(parents=True, exist_ok=True)
                if has_secret(s):
                    # keep the file, replace only the token (push protection blocks the raw string)
                    text = SECRET_RE.sub("REDACTED_TOKEN", s.read_text(errors="ignore"))
                    d.write_text("Asthenosphere knowledge bank: token-shaped strings replaced with REDACTED_TOKEN.\n"
                                 if d.suffix.lower() in (".txt", ".md") else "", errors="ignore")
                    with open(d, "a", errors="ignore") as fh:
                        fh.write(text)
                    skipped.append("%s (token redacted, file kept)" % rel)
                    n += 1
                    bytes_ += size
                    continue
                shutil.copy2(s, d)
                n += 1
                bytes_ += size
    for p in src.iterdir():             # always keep license/notice/readme at root
        if p.is_file() and (LICENSE_FILE.match(p.name) or p.name.lower().startswith("readme")):
            shutil.copy2(p, dst / p.name)
    return n, bytes_, skipped


def process(entry):
    rid, url = entry["id"], entry["url"]
    res = {"id": rid, "url": url, "category": entry["category"], "why": entry.get("why", "")}
    if entry.get("license_note"):
        res["license_note"] = entry["license_note"]
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "r"
        r = run(["git", "clone", "--depth", "1", "-q", url, str(repo)], timeout=900)
        if r.returncode:
            res.update(status="unreachable", reason=r.stderr.strip()[-200:], license="?")
            return res
        res["commit"] = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()
        res["last_commit"] = run(["git", "log", "-1", "--format=%cs"], cwd=repo).stdout.strip()
        if entry.get("per_folder"):
            return per_folder(entry, repo, res)
        spdx, files = detect_license(repo)
        res["license"], res["license_files"] = spdx, files
        status, reason = decide(spdx, entry)
        res["status"], res["reason"] = status, reason
        if status == "vendored":
            dst = KB / "vendor" / entry["category"] / rid
            if dst.exists():
                shutil.rmtree(dst)
            n, b, skipped = copy_tree(repo, dst, entry.get("include"), entry.get("exclude", ()))
            if is_copyleft(spdx):
                res["copyleft"] = True
                (dst / "_KB_COPYLEFT.txt").write_text(
                    "Knowledge-bank notice: this folder is %s open-source code kept verbatim with its license.\n"
                    "Do not copy its code into our own code or link it into our builds without complying with that\n"
                    "license (source disclosure, same-license release). Studying and running it is fine.\n" % spdx)
            if b > MAX_REPO:
                shutil.rmtree(dst)
                res.update(status="link-only", reason="%.0f MB exceeds cap; add `include:` paths" % (b / 1e6))
            else:
                res.update(files=n, bytes=b, skipped=skipped[:50], skipped_count=len(skipped))
    res["fetched"] = datetime.date.today().isoformat()
    return res


def per_folder(entry, repo, res):
    """Repos with no root license whose subfolders each carry their own (e.g. anthropics/skills).
    Each child of `per_folder` is judged on its own license file; only open-source ones are copied."""
    base = repo / entry["per_folder"]
    dst_root = KB / "vendor" / entry["category"] / entry["id"]
    if dst_root.exists():
        shutil.rmtree(dst_root)
    folders, n_tot, b_tot = {}, 0, 0
    for child in sorted(p for p in base.iterdir() if p.is_dir()):
        spdx, _ = detect_license(child)
        status, reason = decide(spdx, {})
        folders[child.name] = {"license": spdx, "status": status}
        if status == "vendored":
            n, b, _ = copy_tree(child, dst_root / entry["per_folder"] / child.name, None)
            n_tot, b_tot = n_tot + n, b_tot + b
    for p in repo.iterdir():            # root README / notices for context and credit
        if p.is_file() and (p.name.lower().startswith("readme") or "notice" in p.name.lower()):
            dst_root.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst_root / p.name)
    ok = sum(1 for f in folders.values() if f["status"] == "vendored")
    res.update(license="per-folder", folders=folders, files=n_tot, bytes=b_tot,
               status="vendored" if ok else "link-only",
               reason="%d of %d folders open source; the rest left out" % (ok, len(folders)))
    res["fetched"] = datetime.date.today().isoformat()
    return res


def write_docs(manifest, cats):
    rows = ["# Knowledge bank: sources and licenses", "",
            "Generated by `tools/kb_sync.py` from `sources.yaml`. Do not edit by hand.",
            "`vendored` = verbatim snapshot with upstream license kept. `link-only` = not copied; "
            "study it at the link or install it as a dependency.", "",
            "| Source | Category | License | Status | Commit | Why / reason |", "|---|---|---|---|---|---|"]
    for m in manifest:
        rows.append("| [%s](%s) | %s | %s | %s | %s | %s |" % (
            m["id"], m["url"], m["category"], m.get("license", "?") + (" (%s)" % m["license_note"] if m.get("license_note") else ""), m["status"],
            m.get("commit", "")[:7], (m["why"] + " " + ("(%s)" % m["reason"] if m["status"] != "vendored" else "")).strip()))
    (KB / "SOURCES.md").write_text("\n".join(rows) + "\n")
    att = ["# Third-party attribution", "",
           "Everything under `knowledge-bank/vendor/` is third-party work kept under its own license.",
           "Each folder contains the upstream LICENSE/NOTICE files. Keep them with any copy or derivative.", ""]
    for m in manifest:
        if m["status"] == "vendored":
            att.append("- `vendor/%s/%s`: %s, %s, commit %s" % (m["category"], m["id"], m["url"], m["license"], m["commit"][:7]))
    att += ["", "Share-alike (CC-BY-SA-4.0) folders: credit the author and release any changes you make "
            "to that material under the same license. Do not merge it into differently licensed code."]
    cl = [m for m in manifest if m.get("copyleft") and m["status"] == "vendored"]
    att += ["", "## Copyleft sources (verbatim, isolated; see `_KB_COPYLEFT.txt` in each)"]
    att += ["- `vendor/%s/%s`: %s" % (m["category"], m["id"], m["license"]) for m in cl]
    (KB / "ATTRIBUTION.md").write_text("\n".join(att) + "\n")
    idx = ["# Knowledge bank index", "", "Generated. Categories run from our core domain outward.", ""]
    for cat, desc in cats.items():
        items = [m for m in manifest if m["category"] == cat]
        if not items:
            continue
        v = sum(1 for m in items if m["status"] == "vendored")
        idx += ["## %s (%d vendored, %d link-only)" % (cat, v, len(items) - v), desc, ""]
        for m in items:
            tag = {"vendored": "vendored" + (", copyleft" if m.get("copyleft") else ""), "link-only": "LINK-ONLY"}.get(m["status"], m["status"])
            where = "`vendor/%s/%s`" % (cat, m["id"]) if m["status"] == "vendored" else m["url"]
            idx.append("- **%s** [%s, %s]: %s. %s" % (m["id"], m.get("license", "?"), tag, m["why"], where))
        idx.append("")
    (KB / "INDEX.md").write_text("\n".join(idx))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--check", action="store_true", help="classify only, vendor nothing")
    a = ap.parse_args()
    cfg = yaml.safe_load((KB / "sources.yaml").read_text())
    entries = [e for e in cfg["sources"] if not a.only or e["id"] in a.only]
    if a.check:
        for e in entries:
            e["policy"] = e.get("policy", "")
    with ThreadPoolExecutor(6) as ex:
        results = list(ex.map(process if not a.check else check_only, entries))
    if a.check:
        for r in results:
            print("%-48s %-22s %s" % (r["id"], r["license"], r["status"]))
        return
    old = {}
    mp = KB / "MANIFEST.json"
    if mp.exists() and a.only:
        old = {m["id"]: m for m in json.loads(mp.read_text())}
    old.update({r["id"]: r for r in results})
    manifest = sorted(old.values(), key=lambda m: (m["category"], m["id"]))
    mp.write_text(json.dumps(manifest, indent=1) + "\n")
    write_docs(manifest, cfg.get("categories", {}))
    for r in results:
        print("%-48s %-22s %-11s %s" % (r["id"], r.get("license", "?"), r["status"], r.get("reason", "")))


def check_only(entry):
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "r"
        r = run(["git", "clone", "--depth", "1", "-q", entry["url"], str(repo)], timeout=900)
        if r.returncode:
            return {"id": entry["id"], "license": "?", "status": "unreachable"}
        spdx, _ = detect_license(repo)
        return {"id": entry["id"], "license": spdx, "status": decide(spdx, entry)[0]}


if __name__ == "__main__":
    main()

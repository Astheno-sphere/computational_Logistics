"""Vendored, unmodified, from mapsmith-ai/manifest-spec `examples/multi_file_digest.py`.

The reference implementation of the digest of a dataset made of several files
(spec section 3.3, draft.9). MapSmith implements the same rule in
`provenance.dataset_sha256`, and `test_dataset_digest.py` holds the two to the
same answers: three implementations of one rule in two repositories are three
chances to disagree, and a test is the only thing that notices. The conformance
agent diffs this against upstream; drift is a finding, not a merge.
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

SHAPEFILE_MEMBERS = (".shp", ".shx", ".dbf", ".prj", ".cpg")
CONTAINER_SUFFIXES = (".gdb",)
NOT_MEMBERS = ("thumbs.db", "desktop.ini")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def listing_sha256(members: dict) -> str:
    """SHA-256 of ``<name>\\0<sha256>\\n`` per member, sorted by the bytes of the name."""
    ordered = sorted(members.items(), key=lambda item: item[0].encode("utf-8"))
    text = "".join(f"{name}\0{sha}\n" for name, sha in ordered)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def shapefile_members(shp: Path) -> dict:
    stem = shp.name[: -len(".shp")].lower()
    found: dict = {}
    for candidate in shp.parent.iterdir():
        if not candidate.is_file() or candidate.is_symlink():
            continue
        lowered = candidate.name.lower()
        for ext in SHAPEFILE_MEMBERS:
            if lowered == stem + ext:
                if ext in found:
                    raise ValueError(
                        f"two files match the {ext} member of {shp.name}: "
                        f"{found[ext].name} and {candidate.name}; section 3.3 forbids choosing"
                    )
                found[ext] = candidate
    if ".shp" not in found:
        raise FileNotFoundError(shp)
    return {ext: file_sha256(path) for ext, path in found.items()}


def container_members(root: Path) -> dict:
    members = {}
    for dirpath, dirs, files in os.walk(root):  # does not follow directory links
        dirs[:] = [d for d in dirs if not (Path(dirpath) / d).is_symlink()]
        for name in files:
            lowered = name.lower()
            if lowered.endswith(".lock") or name.startswith(".") or lowered in NOT_MEMBERS:
                continue  # a lock file is never opened: see section 3.3
            path = Path(dirpath) / name
            if path.is_symlink():
                continue
            members[path.relative_to(root).as_posix()] = file_sha256(path)
    return members


def dataset_sha256(path: str | os.PathLike) -> str:
    p = Path(path)
    if p.suffix.lower() in CONTAINER_SUFFIXES and p.is_dir():
        return listing_sha256(container_members(p))
    if p.suffix.lower() == ".shp":
        return listing_sha256(shapefile_members(p))
    return file_sha256(p)


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        print(dataset_sha256(arg), arg)

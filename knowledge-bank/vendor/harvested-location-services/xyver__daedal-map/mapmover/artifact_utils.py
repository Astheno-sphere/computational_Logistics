"""
Shared pack artifact helpers.

Stdlib-only utilities shared by pack_manager and pack_downloader:
- sha256_file: streaming file hashing
- safe_extract_zip: zip extraction with path traversal guards
"""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path, PurePosixPath


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_extract_zip(zip_path: Path, dest_dir: Path) -> None:
    """
    Extract a zip archive after rejecting unsafe member names.

    Rejects absolute member paths, drive-qualified paths, parent-directory
    (..) components, and any member that would resolve outside dest_dir.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_root = dest_dir.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            member_name = member.filename.replace("\\", "/")
            pure = PurePosixPath(member_name)
            if pure.is_absolute() or pure.drive or (len(member_name) > 1 and member_name[1] == ":"):
                raise RuntimeError(f"Unsafe archive path in pack artifact: {member.filename}")
            if ".." in pure.parts:
                raise RuntimeError(f"Unsafe archive path in pack artifact: {member.filename}")
            member_path = dest_root.joinpath(*pure.parts).resolve()
            if member_path != dest_root and not member_path.is_relative_to(dest_root):
                raise RuntimeError(f"Unsafe archive path in pack artifact: {member.filename}")
        archive.extractall(dest_dir)

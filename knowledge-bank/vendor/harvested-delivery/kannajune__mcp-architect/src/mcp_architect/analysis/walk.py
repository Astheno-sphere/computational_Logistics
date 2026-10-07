"""Filesystem walking utilities shared by the analysis modules."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

# Directories that never contain meaningful source for architecture analysis.
IGNORE_DIRS = {
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "env",
    "__pycache__", ".next", "out", "dist", "build", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "target", "coverage", ".turbo",
    "vendor", ".cache", ".gradle", "bin", "obj", "site-packages",
}

LANG_BY_EXT = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".go": "Go",
    ".rs": "Rust", ".java": "Java", ".rb": "Ruby", ".php": "PHP",
    ".cs": "C#", ".cpp": "C++", ".cc": "C++", ".c": "C", ".h": "C/C++",
    ".kt": "Kotlin", ".swift": "Swift", ".scala": "Scala", ".sh": "Shell",
    ".css": "CSS", ".scss": "CSS", ".less": "CSS", ".html": "HTML",
    ".vue": "Vue", ".svelte": "Svelte", ".sql": "SQL", ".md": "Markdown",
    ".yml": "YAML", ".yaml": "YAML", ".json": "JSON", ".toml": "TOML",
}

# Extensions we treat as "source code" for LOC / complexity purposes.
CODE_EXTS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".rb",
    ".php", ".cs", ".cpp", ".cc", ".c", ".h", ".kt", ".swift", ".scala",
    ".sh", ".vue", ".svelte",
}


def iter_files(root: Path, *, include_hidden: bool = False) -> Iterator[Path]:
    """Yield every file under ``root``, pruning vendored/build directories."""
    root = Path(root)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames
            if d not in IGNORE_DIRS and (include_hidden or not d.startswith("."))
        ]
        for name in filenames:
            if not include_hidden and name.startswith("."):
                continue
            yield Path(dirpath) / name


def read_text(path: Path) -> str:
    """Read a file as UTF-8, ignoring undecodable bytes; '' on failure."""
    try:
        return Path(path).read_text(encoding="utf-8", errors="ignore")
    except (OSError, ValueError):
        return ""


def count_loc(text: str) -> int:
    """Count non-blank lines."""
    return sum(1 for line in text.splitlines() if line.strip())


def rel(path: Path, root: Path) -> str:
    """POSIX-style path relative to root (stable across platforms)."""
    try:
        return Path(path).relative_to(root).as_posix()
    except ValueError:
        return Path(path).as_posix()

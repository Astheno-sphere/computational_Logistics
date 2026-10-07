"""Filesystem sandboxing for file-I/O tools.

When the server is exposed over the network, ``read_file``/``write_file`` must
never touch paths outside a dedicated workspace, otherwise a caller could read
``/etc/passwd`` or overwrite arbitrary files. Every user-supplied path is
resolved (following symlinks) and asserted to stay within the configured
workspace root.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class PathSecurityError(Exception):
    """Raised when a path escapes the allowed workspace."""


def get_workspace_root() -> Path:
    """Return the sandbox root, creating it if needed."""
    from locusync.config import get_config

    root = Path(get_config().workdir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def safe_path(user_path: str, *, must_exist: bool = False) -> Path:
    """Resolve ``user_path`` and guarantee it stays inside the workspace root.

    Args:
        user_path: Path supplied by the caller (absolute or relative).
        must_exist: When ``True``, raise if the resolved path is missing.

    Returns:
        The resolved, sandboxed :class:`~pathlib.Path`.

    Raises:
        PathSecurityError: If the path escapes the workspace or is missing.
    """
    if not user_path or not str(user_path).strip():
        raise PathSecurityError("Path cannot be empty")

    root = get_workspace_root()
    candidate = Path(user_path)
    base = candidate if candidate.is_absolute() else root / candidate

    # ``resolve()`` collapses ``..`` and follows symlinks, defeating traversal.
    resolved = base.resolve()

    if resolved != root and not resolved.is_relative_to(root):
        raise PathSecurityError(
            f"Path '{user_path}' is outside the allowed workspace ({root})"
        )

    if must_exist and not resolved.exists():
        raise PathSecurityError(f"File not found inside workspace: {user_path}")

    return resolved

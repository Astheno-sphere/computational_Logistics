"""Workspace filesystem for agent-local files.

中文：提供受限的 agent workspace 文件访问、搜索和命令执行能力。
English: Provides restricted agent workspace file access, search, and command execution.
"""

from __future__ import annotations

import asyncio
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

RUNTIME_DIR = ".runtime"


@dataclass(frozen=True)
class FileInfo:
    """Workspace file metadata.

    Args:
        path: Path relative to the workspace root.
        size: File size in bytes, or zero for directories.
        is_dir: Whether the path is a directory.
    """

    path: str
    size: int
    is_dir: bool = False


@dataclass(frozen=True)
class FileOpResult:
    """Workspace file operation result.

    Args:
        ok: Whether the operation succeeded.
        path: Path relative to the workspace root.
        bytes_written: Number of bytes written when applicable.
        error: Optional error message.
    """

    ok: bool
    path: str
    bytes_written: int = 0
    error: str = ""


@dataclass(frozen=True)
class GrepMatch:
    """One text search match.

    Args:
        path: Path relative to the workspace root.
        line: One-based line number.
        text: Matched line text.
    """

    path: str
    line: int
    text: str


@dataclass(frozen=True)
class CommandResult:
    """Restricted command execution result.

    Args:
        ok: Whether the command exited successfully.
        exit_code: Process exit code, or -1 for validation/timeout failures.
        stdout: Captured standard output.
        stderr: Captured standard error.
        error_type: Error category.
    """

    ok: bool
    exit_code: int
    stdout: str
    stderr: str
    error_type: str = "none"


class WorkspaceFS:
    """Restricted filesystem facade for one agent workspace."""

    def __init__(
        self,
        root: Path,
        *,
        ignored_dirs: set[str] | None = None,
    ) -> None:
        """Initialize the workspace filesystem.

        Args:
            root: Workspace root directory.
            ignored_dirs: Directory names hidden from recursive listing/search.

        Returns:
            None.
        """
        self.root = root.resolve()
        self.ignored_dirs = ignored_dirs or {RUNTIME_DIR, "__pycache__"}

    def resolve(self, relative_path: str) -> Path:
        """Resolve a path inside the workspace.

        Args:
            relative_path: Path relative to the workspace root.

        Returns:
            Absolute resolved path.
        """
        target = (self.root / str(relative_path or ".")).resolve()
        if target != self.root and self.root not in target.parents:
            raise ValueError(f"Path escapes agent workspace: {relative_path}")
        return target

    def read_text(self, path: str) -> str:
        """Read a UTF-8 text file.

        Args:
            path: Path relative to the workspace root.

        Returns:
            File text, or an empty string when the file does not exist.
        """
        target = self.resolve(path)
        if not target.exists() or not target.is_file():
            return ""
        return target.read_text(encoding="utf-8")

    def write_text(self, path: str, content: str) -> FileOpResult:
        """Write a UTF-8 text file.

        Args:
            path: Path relative to the workspace root.
            content: Text content to write.

        Returns:
            File operation result.
        """
        target = self.resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        text = str(content)
        target.write_text(text, encoding="utf-8")
        return FileOpResult(
            ok=True,
            path=target.relative_to(self.root).as_posix(),
            bytes_written=len(text.encode("utf-8")),
        )

    def append_text(self, path: str, content: str) -> FileOpResult:
        """Append UTF-8 text to a file.

        Args:
            path: Path relative to the workspace root.
            content: Text content to append.

        Returns:
            File operation result.
        """
        target = self.resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        text = str(content)
        with target.open("a", encoding="utf-8") as f:
            f.write(text)
        return FileOpResult(
            ok=True,
            path=target.relative_to(self.root).as_posix(),
            bytes_written=len(text.encode("utf-8")),
        )

    def delete(self, path: str) -> FileOpResult:
        """Delete one file.

        Args:
            path: Path relative to the workspace root.

        Returns:
            File operation result.
        """
        target = self.resolve(path)
        if not target.exists() or target.is_dir():
            return FileOpResult(ok=False, path=path, error="file not found")
        target.unlink()
        return FileOpResult(ok=True, path=target.relative_to(self.root).as_posix())

    def exists(self, path: str) -> bool:
        """Return whether a workspace path exists.

        Args:
            path: Path relative to the workspace root.

        Returns:
            True when the path exists.
        """
        return self.resolve(path).exists()

    def list(
        self,
        path: str = ".",
        *,
        glob: str | None = None,
        limit: int = 200,
    ) -> list[FileInfo]:
        """List files and directories under a workspace path.

        Args:
            path: Path relative to the workspace root.
            glob: Optional glob pattern.
            limit: Maximum number of entries.

        Returns:
            File metadata entries.
        """
        target = self.resolve(path)
        if not target.exists():
            return []
        if target.is_file():
            return [self._file_info(target)]

        candidates = target.rglob(glob or "*")
        result: list[FileInfo] = []
        for item in sorted(candidates):
            rel_parts = item.relative_to(self.root).parts
            if any(part in self.ignored_dirs for part in rel_parts):
                continue
            result.append(self._file_info(item))
            if len(result) >= limit:
                break
        return result

    async def grep(
        self,
        pattern: str,
        path: str = ".",
        *,
        limit: int = 100,
    ) -> list[GrepMatch]:
        """Search text files with ripgrep or grep.

        Args:
            pattern: Search pattern.
            path: Path relative to the workspace root.
            limit: Maximum number of matches.

        Returns:
            Search matches.
        """
        target = self.resolve(path)
        if not target.exists():
            return []

        if sys.platform == "win32":
            return self._grep_python(target, pattern, limit=limit)

        tool = shutil.which("rg")
        if tool:
            argv = [
                tool,
                "--line-number",
                "--no-heading",
                "--color",
                "never",
                "--glob",
                f"!{RUNTIME_DIR}/**",
                "--glob",
                "!__pycache__/**",
                pattern,
                str(target),
            ]
        else:
            grep = shutil.which("grep")
            if not grep:
                return self._grep_python(target, pattern, limit=limit)
            argv = [
                grep,
                "-R",
                "-n",
                "--exclude-dir",
                RUNTIME_DIR,
                pattern,
                str(target),
            ]

        proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(self.root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_b, _ = await proc.communicate()
        if proc.returncode not in {0, 1}:
            return []
        return self._parse_grep_output(stdout_b, limit=limit)

    async def run_command(
        self,
        argv: list[str],
        *,
        timeout_sec: int = 30,
        cwd: str = ".",
        env: dict[str, str] | None = None,
    ) -> CommandResult:
        """Run an allowed command inside the workspace.

        Args:
            argv: Command argument vector.
            timeout_sec: Timeout in seconds.
            cwd: Working directory relative to the workspace root.
            env: Optional process environment.

        Returns:
            Command execution result.
        """
        if not argv:
            return CommandResult(False, -1, "", "empty argv", "validation")
        if Path(argv[0]).name not in {"python", "python3", Path(sys.executable).name}:
            return CommandResult(False, -1, "", "command not allowed", "validation")
        work_dir = self.resolve(cwd)
        if not work_dir.is_dir():
            return CommandResult(False, -1, "", "cwd not found", "validation")

        proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(work_dir),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout_sec,
            )
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return CommandResult(
                False,
                -1,
                "",
                f"command timed out after {timeout_sec}s",
                "timeout",
            )

        stdout = (stdout_b or b"").decode("utf-8", errors="replace")
        stderr = (stderr_b or b"").decode("utf-8", errors="replace")
        exit_code = int(proc.returncode or 0)
        return CommandResult(
            ok=exit_code == 0,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            error_type="none" if exit_code == 0 else "runtime",
        )

    def _file_info(self, path: Path) -> FileInfo:
        """Build metadata for one path.

        Args:
            path: Absolute path inside the workspace.

        Returns:
            File metadata.
        """
        rel = path.relative_to(self.root).as_posix()
        return FileInfo(
            path=rel,
            size=path.stat().st_size if path.is_file() else 0,
            is_dir=path.is_dir(),
        )

    def _grep_python(
        self, target: Path, pattern: str, *, limit: int
    ) -> list[GrepMatch]:
        regex = re.compile(pattern)
        candidates = [target] if target.is_file() else sorted(target.rglob("*"))
        matches: list[GrepMatch] = []
        for path in candidates:
            if not path.is_file():
                continue
            rel_parts = path.relative_to(self.root).parts
            if any(part in self.ignored_dirs for part in rel_parts):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                if not regex.search(line):
                    continue
                matches.append(
                    GrepMatch(
                        path=path.relative_to(self.root).as_posix(),
                        line=lineno,
                        text=line,
                    )
                )
                if len(matches) >= limit:
                    return matches
        return matches

    def _parse_grep_output(self, stdout_b: bytes, *, limit: int) -> list[GrepMatch]:
        """Parse grep-compatible stdout.

        Args:
            stdout_b: Raw grep output bytes.
            limit: Maximum number of matches.

        Returns:
            Parsed search matches.
        """
        matches: list[GrepMatch] = []
        stdout = (stdout_b or b"").decode("utf-8", errors="replace")
        for raw_line in stdout.splitlines():
            path_part, sep, rest = raw_line.partition(":")
            if not sep:
                continue
            line_part, sep, text = rest.partition(":")
            if not sep:
                continue
            try:
                line_no = int(line_part)
            except ValueError:
                continue
            rel_path = self._normalize_match_path(path_part)
            matches.append(GrepMatch(path=rel_path, line=line_no, text=text))
            if len(matches) >= limit:
                break
        return matches

    def _normalize_match_path(self, raw_path: str) -> str:
        """Normalize one matched path to a workspace-relative path.

        Args:
            raw_path: Path string from grep output.

        Returns:
            Workspace-relative path when possible.
        """
        path = Path(raw_path)
        if not path.is_absolute():
            path = self.root / path
        try:
            return path.resolve().relative_to(self.root).as_posix()
        except ValueError:
            return raw_path

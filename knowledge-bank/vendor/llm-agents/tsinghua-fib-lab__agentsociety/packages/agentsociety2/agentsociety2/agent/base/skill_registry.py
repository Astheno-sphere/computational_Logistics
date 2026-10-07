"""Skill registry.

中文：扫描、解析和查询 Agent skill 元数据。
English: Scans, parses, and queries Agent skill metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# Built-in skills live under ``agentsociety2/agent/skills/`` (sibling of this
# ``agent/base/`` package). Compute it from this file's location so the
# registry keeps scanning the real skill content directory regardless of where
# this module itself is imported from / located.
_BUILTIN_ROOT = Path(__file__).resolve().parent.parent / "skills"
_RESOURCE_FILES_CACHE: dict[tuple[str, int], list[str]] = {}


@dataclass(frozen=True)
class SkillDescriptor:
    """Skill metadata.

    Args:
        skill_id: Stable registry skill id.
        name: Display name from SKILL.md.
        namespace: Skill namespace.
        description: Catalog description.
        root: Skill root directory.
        source: Source category.
        source_label: Human-readable source label.
        script: Optional default script path.
        hooks: Lifecycle hook script map.
    """

    skill_id: str
    name: str
    namespace: str
    description: str
    root: Path
    source: str
    source_label: str
    script: str | None
    hooks: dict[str, str]

    def resource_files(self) -> list[str]:
        """List files shipped under this skill root.

        Args:
            None.

        Returns:
            Relative resource file paths under the skill root.
        """
        if not self.root.is_dir():
            return []
        try:
            mtime_ns = self.root.stat().st_mtime_ns
        except OSError:
            mtime_ns = 0
        cache_key = (str(self.root), mtime_ns)
        cached = _RESOURCE_FILES_CACHE.get(cache_key)
        if cached is not None:
            return list(cached)

        resources: list[str] = []
        for path in sorted(
            (item for item in self.root.rglob("*") if item.is_file()),
            key=lambda item: item.relative_to(self.root).as_posix().casefold(),
        ):
            relative = path.relative_to(self.root)
            if _is_hidden_or_cache_path(relative):
                continue
            resources.append(relative.as_posix())
        _RESOURCE_FILES_CACHE[cache_key] = resources
        return list(resources)


class SkillRegistry:
    """Registry for Skill metadata.

    Args:
        None.
    """

    def __init__(self) -> None:
        """Initialize an empty registry.

        Args:
            None.

        Returns:
            None.
        """
        self._skills: dict[str, SkillDescriptor] = {}
        self._builtin_scanned = False

    def scan_builtin(self, root: Path | None = None) -> list[str]:
        """Scan built-in skills once.

        Args:
            root: Optional built-in skill root override.

        Returns:
            Added skill ids.
        """
        if self._builtin_scanned:
            return []
        added = self._scan_root(
            root or _BUILTIN_ROOT,
            namespace="built-in",
            source="built-in",
            source_label="built-in",
        )
        self._builtin_scanned = True
        return added

    def scan_custom(self, skills_root: Path, namespace: str = "custom") -> list[str]:
        """Scan a custom skill root.

        Args:
            skills_root: Directory containing skill subdirectories.
            namespace: Namespace assigned to discovered skills.

        Returns:
            Added skill ids.
        """
        ns = namespace.strip() or "custom"
        return self._scan_root(
            skills_root,
            namespace=ns,
            source="custom",
            source_label=str(skills_root),
        )

    def scan_env(self, skills_dir: Path, env_name: str) -> list[str]:
        """Scan skills provided by an environment module.

        Args:
            skills_dir: Directory containing skill subdirectories.
            env_name: Environment module name.

        Returns:
            Added skill ids.
        """
        namespace = f"env:{env_name.strip() or 'unknown'}"
        return self._scan_root(
            skills_dir,
            namespace=namespace,
            source="env",
            source_label=str(skills_dir),
        )

    def list_all(self) -> list[SkillDescriptor]:
        """List all registered skills.

        Args:
            None.

        Returns:
            Registered skill descriptors.
        """
        return sorted(self._skills.values(), key=lambda item: item.skill_id)

    def get(self, skill_id: str) -> SkillDescriptor | None:
        """Return one skill descriptor by id.

        Args:
            skill_id: Registry skill id.

        Returns:
            Matching descriptor, or None.
        """
        return self._skills.get(skill_id)

    def find_by_name(self, name: str) -> list[SkillDescriptor]:
        """Find skill descriptors by display name.

        Args:
            name: Skill display name.

        Returns:
            Matching descriptors.
        """
        return [item for item in self.list_all() if item.name == name]

    def read_skill_doc(self, skill_id: str) -> str:
        """Read one skill's SKILL.md.

        Args:
            skill_id: Registry skill id.

        Returns:
            Skill document text, or an empty string.
        """
        info = self.get(skill_id)
        if info is None:
            return ""
        path = info.root / "SKILL.md"
        if not path.is_file():
            return ""
        return path.read_text(encoding="utf-8")

    def read_skill_file(self, skill_id: str, relative_path: str) -> str:
        """Read one file inside a skill directory.

        Args:
            skill_id: Registry skill id.
            relative_path: Path relative to the skill root.

        Returns:
            File text, or an empty string.
        """
        info = self.get(skill_id)
        if info is None:
            return ""
        target = self._resolve_inside(info.root, relative_path)
        if target is None or not target.is_file():
            return ""
        return target.read_text(encoding="utf-8")

    def list_hooks(self, hook_type: str) -> list[SkillDescriptor]:
        """List skills declaring one hook.

        Args:
            hook_type: Lifecycle hook name.

        Returns:
            Skill descriptors that declare the hook.
        """
        return [item for item in self.list_all() if item.hooks.get(hook_type)]

    def copy(self) -> SkillRegistry:
        """Copy this registry.

        Args:
            None.

        Returns:
            Shallow registry copy.
        """
        other = SkillRegistry()
        other._skills = dict(self._skills)
        other._builtin_scanned = self._builtin_scanned
        return other

    def _scan_root(
        self,
        root: Path,
        *,
        namespace: str,
        source: str,
        source_label: str,
    ) -> list[str]:
        """Scan one skill root.

        Args:
            root: Directory containing skill subdirectories.
            namespace: Namespace assigned to discovered skills.
            source: Source category.
            source_label: Human-readable source label.

        Returns:
            Added skill ids.
        """
        added: list[str] = []
        base = root.resolve()
        if not base.is_dir():
            return added
        # Ensure the resolved path hasn't escaped via symlink traversal.
        try:
            base.relative_to(root.resolve())
        except ValueError:
            # resolved path is outside the original root — reject
            return added

        for child in sorted(base.iterdir()):
            if not child.is_dir() or child.name.startswith((".", "_")):
                continue
            skill_md = child / "SKILL.md"
            if not skill_md.is_file():
                continue
            meta = _parse_frontmatter(skill_md)
            name = str(meta.get("name") or child.name).strip()
            if not name:
                continue
            skill_id = f"{namespace}@{name}"
            if skill_id in self._skills:
                continue
            description = str(meta.get("description") or "").strip()
            descriptor = SkillDescriptor(
                skill_id=skill_id,
                name=name,
                namespace=namespace,
                description=description,
                root=child.resolve(),
                source=source,
                source_label=source_label,
                script=_clean_relative_script(child, meta.get("script")),
                hooks=_parse_hooks(child, meta),
            )
            self._skills[skill_id] = descriptor
            added.append(skill_id)
        return added

    @staticmethod
    def _resolve_inside(root: Path, relative_path: str) -> Path | None:
        """Resolve a path inside a root directory.

        Args:
            root: Root directory.
            relative_path: Candidate relative path.

        Returns:
            Resolved path when it stays inside root, otherwise None.
        """
        base = root.resolve()
        target = (base / str(relative_path or ".")).resolve()
        if target == base or base in target.parents:
            return target
        return None


def _parse_frontmatter(path: Path) -> dict[str, Any]:
    """Parse YAML frontmatter from a SKILL.md file.

    Args:
        path: SKILL.md path.

    Returns:
        Parsed frontmatter mapping.
    """
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        return {}
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}
    loaded = yaml.safe_load(parts[1]) or {}
    return loaded if isinstance(loaded, dict) else {}


def _clean_relative_script(root: Path, raw: Any) -> str | None:
    """Validate and normalize a script path.

    Args:
        root: Skill root directory.
        raw: Raw script value from frontmatter.

    Returns:
        Normalized relative script path, or None.
    """
    text = str(raw or "").strip()
    if not text:
        return None
    base = root.resolve()
    target = (base / text).resolve()
    if target.is_file() and (target == base or base in target.parents):
        return text.replace("\\", "/")
    return None


def _is_hidden_or_cache_path(relative_path: Path) -> bool:
    """Return whether a relative resource path should be hidden from catalogs.

    Args:
        relative_path: Candidate path relative to a skill root.

    Returns:
        True when the path is hidden, cache-generated, or compiled output.
    """
    parts = relative_path.parts
    if any(part.startswith(".") for part in parts):
        return True
    if "__pycache__" in parts:
        return True
    return relative_path.suffix in {".pyc", ".pyo"}


def _parse_hooks(root: Path, meta: dict[str, Any]) -> dict[str, str]:
    """Parse lifecycle hook declarations.

    Args:
        root: Skill root directory.
        meta: Parsed frontmatter mapping.

    Returns:
        Hook type to script path mapping.
    """
    hooks: dict[str, str] = {}

    raw_hooks = meta.get("hooks")
    if isinstance(raw_hooks, dict):
        for key, value in raw_hooks.items():
            hook_type = str(key or "").strip()
            script = _clean_relative_script(root, value)
            if hook_type and script:
                hooks[hook_type] = script

    hook_type = str(meta.get("hook") or "").strip()
    hook_script = _clean_relative_script(root, meta.get("hook_script"))
    if hook_type and hook_script:
        hooks[hook_type] = hook_script
    return hooks


_registry: SkillRegistry | None = None


def get_skill_registry() -> SkillRegistry:
    """Return the global Skill registry.

    Args:
        None.

    Returns:
        Global registry with built-in skills scanned.
    """
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
        _registry.scan_builtin()
    return _registry


def reset_skill_registry() -> None:
    """Reset the global Skill registry.

    Args:
        None.

    Returns:
        None.
    """
    global _registry
    _registry = None

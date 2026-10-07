"""Detect the technology stack, size, and entry points of a codebase."""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from .walk import LANG_BY_EXT, count_loc, iter_files, read_text, rel

# Manifest file -> (ecosystem, dependency-keys to scan)
_MANIFESTS = {
    "package.json": "Node.js",
    "pyproject.toml": "Python",
    "requirements.txt": "Python",
    "go.mod": "Go",
    "Cargo.toml": "Rust",
    "pom.xml": "Java (Maven)",
    "build.gradle": "Java/Kotlin (Gradle)",
    "Gemfile": "Ruby",
    "composer.json": "PHP",
}

# Library substring -> friendly framework name.
_FRAMEWORK_HINTS = {
    "next": "Next.js", "react": "React", "@angular/core": "Angular",
    "vue": "Vue", "svelte": "Svelte", "express": "Express",
    "@nestjs/core": "NestJS", "fastify": "Fastify", "fastapi": "FastAPI",
    "django": "Django", "flask": "Flask", "starlette": "Starlette",
    "langchain": "LangChain", "langgraph": "LangGraph", "mcp": "MCP",
    "spring-boot": "Spring Boot", "rails": "Ruby on Rails",
    "laravel": "Laravel", "tailwindcss": "Tailwind CSS",
}

_ENTRY_CANDIDATES = (
    "main.py", "app.py", "manage.py", "__main__.py", "server.py",
    "index.js", "index.ts", "main.go", "main.rs", "Program.cs",
    "src/index.ts", "src/index.js", "src/main.ts", "src/main.py",
    "src/app/page.tsx", "cmd",
)


def _scan_frameworks(root: Path) -> tuple[set[str], list[str]]:
    ecosystems: set[str] = set()
    frameworks: set[str] = set()
    for f in iter_files(root):
        name = f.name
        if name not in _MANIFESTS:
            continue
        ecosystems.add(_MANIFESTS[name])
        text = read_text(f)
        if name == "package.json":
            try:
                data = json.loads(text)
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                for dep in deps:
                    for hint, fw in _FRAMEWORK_HINTS.items():
                        if dep == hint or dep.startswith(hint):
                            frameworks.add(fw)
            except (json.JSONDecodeError, AttributeError):
                pass
        else:
            low = text.lower()
            for hint, fw in _FRAMEWORK_HINTS.items():
                if re.search(rf"(^|[^a-z0-9_]){re.escape(hint)}([^a-z0-9_]|$)", low):
                    frameworks.add(fw)
    return ecosystems, sorted(frameworks)


def _find_entry_points(root: Path) -> list[str]:
    found = []
    for cand in _ENTRY_CANDIDATES:
        p = root / cand
        if p.exists():
            found.append(cand)
    return found


def get_overview(root: str | Path) -> dict:
    root = Path(root)
    lang_files: Counter[str] = Counter()
    lang_loc: Counter[str] = Counter()
    total_files = 0
    total_loc = 0
    top_dirs: Counter[str] = Counter()

    for f in iter_files(root):
        total_files += 1
        parts = rel(f, root).split("/")
        if len(parts) > 1:
            top_dirs[parts[0]] += 1
        lang = LANG_BY_EXT.get(f.suffix.lower())
        if lang in (None, "JSON", "YAML", "TOML", "Markdown"):
            continue
        loc = count_loc(read_text(f))
        lang_files[lang] += 1
        lang_loc[lang] += loc
        total_loc += loc

    ecosystems, frameworks = _scan_frameworks(root)
    languages = [
        {"language": lang, "files": lang_files[lang], "loc": lang_loc[lang]}
        for lang, _ in lang_loc.most_common()
    ]
    return {
        "root": str(root),
        "total_files": total_files,
        "total_code_loc": total_loc,
        "languages": languages,
        "ecosystems": sorted(ecosystems),
        "frameworks": frameworks,
        "top_level_dirs": [d for d, _ in top_dirs.most_common(12)],
        "entry_points": _find_entry_points(root),
    }

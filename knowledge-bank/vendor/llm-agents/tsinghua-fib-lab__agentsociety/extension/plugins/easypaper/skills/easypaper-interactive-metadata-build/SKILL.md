---
description: Interactively build EasyPaper metadata from a research-materials folder using Claude Code's file-investigation tools. Output is JSON consumable by the `easypaper-paper-from-metadata` skill.
---

Use this skill when the user has a folder of research materials and wants Claude to co-author the metadata in conversation instead of running the one-shot SDK pipeline silently.

The two paths are complementary:

| Path | Driver | Interaction | Use when |
|------|--------|-------------|----------|
| SDK one-shot (`generate_metadata_from_folder`) | EasyPaper internal LLM | None | Batch, CI, or fast autonomous extraction |
| This skill | Claude Code | High | Single high-value paper, atypical folder, or ambiguity requiring user input |

Both paths produce metadata that can be consumed by `easypaper-paper-from-metadata`.

## Output Contract

The final JSON must validate as `PaperGenerationRequest` and include:

- `title`, `idea_hypothesis`, `method`, `data`, `experiments`
- `references`
- `materials_root`
- `figures`
- `tables`
- optional `template_path`, `style_guide`, `target_pages`, generation flags, and output settings

Each figure/table object follows the SDK shape:

```json
{
  "id": "fig:h<12hex>",
  "caption": "...",
  "description": "...",
  "section": "",
  "file_path": "relative/posix/path/to/asset.png",
  "wide": false,
  "auto_generate": false,
  "generation_prompt": null
}
```

Tables use the same shape with `tab:` ids.

## Path Handling

Folder-derived metadata uses the SDK convention:

- `materials_root`: resolved source-folder path.
- `figures[].file_path` and `tables[].file_path`: relative POSIX paths under `materials_root`.
- Do not convert folder-derived figure/table paths to absolute paths in the saved metadata.
- `template_path` may be omitted or written relative to the saved metadata file location when the template is part of the same portable project.

Downstream generation resolves figure/table assets via `materials_root` first. The generation command or example loader normalizes operational fields such as `template_path` and local `code_repository.path` before calling the SDK.

## ID Generation

When operating in `cold` mode, generate stable ids the same way as the SDK:

```python
import hashlib

def figure_id(rel_posix_path: str) -> str:
    digest = hashlib.sha256(rel_posix_path.lower().encode("utf-8")).hexdigest()[:12]
    return f"fig:h{digest}"

def table_id(rel_posix_path: str) -> str:
    digest = hashlib.sha256(rel_posix_path.encode("utf-8")).hexdigest()[:12]
    return f"tab:h{digest}"
```

Figures lowercase the relative path before hashing; tables do not.

## Modes

The first interaction must present these options and wait for an explicit choice:

```text
Choose how you want to build the metadata:

  [1] cold        — Claude walks the folder alone, no Python SDK call.
                    Best for small folders or when full transparency is required.

  [2] warm-start  — (recommended) Run ep.generate_metadata_from_folder() once
                    to get a draft, then refine each field with Claude.
                    Best signal-to-effort ratio.

  [3] refine      — Load an existing metadata JSON and walk through fixing
                    validation failures and warnings.

Reply with 1 / 2 / 3, or the mode name.
```

Then ask for:
- `cold` / `warm-start`: `materials_root`; verify it exists and is a directory.
- `refine`: existing metadata JSON path; verify it exists.

## Workflow

### Phase 1: Discovery

Use read-only file tools to map the folder:
- top-level entries
- `README*`, root `*.md`, `pyproject.toml`, `requirements.txt`, `setup.py`
- config files, primary scripts, BibTeX files
- likely paper, experiments, data, figures, configs, and references subtrees

Output a concise folder map before drafting fields.

### Phase 2: Field Drafting

Draft and confirm the five prose fields in order:
- `title`
- `idea_hypothesis`
- `method`
- `data`
- `experiments`

For each field, cite the files that support the draft and surface unresolved questions.

### Phase 3: Asset Selection

Glob candidates:
- figures: `**/*.{png,jpg,jpeg,gif,svg,webp,bmp}`
- tables: `**/*.{csv,tsv}` and table-like `.tex`

For each retained asset:
- generate a stable id
- store `file_path` as relative POSIX under `materials_root`
- write a caption and description grounded in available evidence
- set `section` only when placement is clear

### Phase 4: References

Parse BibTeX files when present and store entries as raw BibTeX strings. Empty `references` is a warning, not a save blocker.

### Phase 5: Validate and Save

Before writing, run public schema validation plus explicit checks:

- `PaperGenerationRequest.model_validate(metadata_dict)` succeeds.
- `title`, `idea_hypothesis`, `method`, `data`, and `experiments` are non-empty.
- `materials_root` is set for folder-derived metadata.
- Figure/table paths are relative POSIX under `materials_root`.
- Figure/table counts are within the selected caps.
- Figure ids start with `fig:` and table ids start with `tab:`.
- Empty `references` is reported as a warning.

Only save when the hard checks pass:

```python
import json
from pathlib import Path

out_path = Path(materials_root) / "easypaper_metadata.json"
out_path.write_text(
    json.dumps(metadata_dict, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
```

### Phase 6: Handoff

Report:
- file written and its resolved path
- warnings
- next step: run `/easypaper-paper-from-metadata` and point it at the saved JSON

## Error Handling

- Materials root missing: ask for the correct path.
- EasyPaper not importable: use `easypaper-setup-environment`.
- Warm-start SDK call fails: fall back to `cold` mode and inform the user.
- Validation fails: loop back to the specific failing phase; do not save failing metadata.

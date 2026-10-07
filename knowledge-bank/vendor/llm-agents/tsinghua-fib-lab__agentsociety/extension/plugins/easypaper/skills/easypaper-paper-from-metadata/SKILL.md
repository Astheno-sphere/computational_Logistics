---
description: Generate a full academic paper from metadata using the EasyPaper Python SDK. Collects metadata interactively if not provided, then generates the paper directly.
---

Use this skill when the user wants to generate an academic paper from metadata. It handles both metadata collection and paper generation in one workflow.

## Recommended Input

Have the user prepare a metadata JSON file that follows `examples/meta.json`. Treat that file as a schema/template reference, not as a runnable paper. For a runnable project-local sample, use `examples/template/meta.json`.

Load JSON as `PaperGenerationRequest`, then convert it to SDK inputs:

```python
import json
from pathlib import Path
from easypaper import EasyPaper, PaperGenerationRequest

metadata_path = Path("metadata.json").resolve()
raw = json.loads(metadata_path.read_text(encoding="utf-8"))

def metadata_relative_path(value: str) -> str:
    candidate = Path(value).expanduser()
    if candidate.is_absolute():
        return str(candidate)
    return str((metadata_path.parent / candidate).resolve())

if not raw.get("materials_root"):
    raw["materials_root"] = str(metadata_path.parent)
if raw.get("template_path"):
    raw["template_path"] = metadata_relative_path(raw["template_path"])
if (
    isinstance(raw.get("code_repository"), dict)
    and raw["code_repository"].get("type") == "local_dir"
    and raw["code_repository"].get("path")
):
    raw["code_repository"]["path"] = metadata_relative_path(raw["code_repository"]["path"])

request = PaperGenerationRequest.model_validate(raw)
paper_metadata = request.to_metadata()
options = {
    "output_dir": request.output_dir,
    "save_output": request.save_output,
    "compile_pdf": request.compile_pdf,
    "figures_source_dir": request.figures_source_dir,
    "target_pages": request.target_pages,
    "enable_review": request.enable_review,
    "max_review_iterations": request.max_review_iterations,
    "enable_planning": request.enable_planning,
    "enable_exemplar": request.enable_exemplar,
    "enable_vlm_review": request.enable_vlm_review,
    "enable_user_feedback": request.enable_user_feedback,
    "artifacts_prefix": request.artifacts_prefix or "",
}

ep = EasyPaper(config_path=str(Path("easypaper_config.yaml").resolve()))
result = await ep.generate(paper_metadata, **options)
```

## Workflow

### Phase 1: Check for Existing Metadata

Ask whether the user already has a complete metadata file or JSON object.

If provided:
- Parse and validate it with `PaperGenerationRequest.model_validate(...)`.
- If `materials_root` is missing and the metadata came from a file, set it to the metadata file's parent directory before SDK execution.
- Normalize `template_path` and local `code_repository.path` relative to the metadata file parent when those values are relative.
- If required fields are missing, collect only the missing fields.

If not provided, proceed to interactive collection.

### Phase 2: Collect Metadata

Required fields:

1. `title`: paper title.
2. `idea_hypothesis`: core research question or hypothesis.
3. `method`: methodology, model, algorithm, or study design.
4. `data`: data sources, materials, or validation setup.
5. `experiments`: results, comparisons, ablations, and interpretation.
6. `references`: BibTeX entries or citation strings. Empty references are allowed but should be reported as a quality warning.

Optional fields:

- `style_guide`: venue or writing style such as Nature, ICML, NeurIPS, ICLR, ACL, AAAI, or COLM.
- `target_pages`: target page count.
- `template_path`: LaTeX template zip or directory.
- `compile_pdf`: default `true`.
- `enable_review`: text review/revision loop, default `true`.
- `enable_vlm_review`: VLM/PDF visual review and page-overflow checks, default `false`.
- `max_review_iterations`: default `3`.
- `figures`, `tables`, `code_repository`, `materials_root`, `output_dir`.

### Phase 3: Validate Before Generation

Use public schema validation plus explicit checks:

- `PaperGenerationRequest.model_validate(...)` succeeds.
- Required prose fields are non-empty.
- Figure ids start with `fig:` and table ids start with `tab:`.
- Figure/table counts stay within the selected caps.
- Figure/table file paths resolve using the documented path rules.
- Empty `references` is a warning, not a hard failure.

### Phase 4: Generate

Use `EasyPaper.generate(metadata, **options)` directly. No FastAPI server is needed.

For streaming:

```python
async for event in ep.generate_stream(paper_metadata, **options):
    print(f"{event.get('phase', '')}: {event.get('message', '')}")
```

### Phase 5: Report Results

Show:
- `result.status`
- `result.output_path`
- `result.pdf_path`
- word count and sections when present
- compile or generation errors when present

Final PDF selection priority:
1. `result.pdf_path`
2. `result.output_path/iteration_*_final/**/*.pdf`
3. latest `result.output_path/iteration_*` directory PDF
4. `result.output_path/paper.pdf`

If no PDF is found, explicitly report that the final PDF is unavailable and include compile error context.

## Path Handling Rules

Metadata should use relative paths where practical so examples and generated outputs remain portable.

Hand-written metadata:
- Use `examples/meta.json` for schema shape.
- When loading from a file, set `materials_root` to the metadata file parent if missing.
- Figure/table `file_path` values resolve from `materials_root` first, then current working directory.
- Normalize `template_path` and local `code_repository.path` against the metadata file parent before SDK execution.
- `output_dir` is an optional runtime setting and may be omitted or overridden.

Folder-generated metadata:
- `materials_root` is the resolved source folder.
- Figure/table `file_path` values are relative POSIX paths under `materials_root`.
- Do not rewrite those figure/table paths to absolute paths in the saved metadata.

Config:
- Resolve `config_path` before constructing `EasyPaper`.
- Prefer the setup-generated `./easypaper_config.yaml`. If it is missing,
  run `easypaper-setup-environment` so Claude can create it from the
  synchronized skill-bundled `config.example.yaml` template.

## Alternative: Generate Metadata from a Materials Folder

When the user has a folder of research materials instead of a ready metadata JSON, EasyPaper can synthesize `PaperMetaData`:

```python
from pathlib import Path
from easypaper import EasyPaper

ep = EasyPaper(config_path=str(Path("easypaper_config.yaml").resolve()))

metadata = await ep.generate_metadata_from_folder(
    str(Path("path/to/materials").resolve()),
    max_figures=12,
    max_tables=12,
    vision_enrich_figures=True,
    # vision_model="gpt-4o",
    # max_vision_figures=8,
)

result = await ep.generate(metadata, compile_pdf=True)
```

The folder pipeline stores `materials_root` as the scan root and keeps retained figure/table paths relative to that root. Vision enrichment runs only on retained figures and caches descriptions by image content hash.

Use the `easypaper-interactive-metadata-build` skill or `/easypaper-metadata-build` when the user wants Claude to inspect the folder, ask questions, and co-author the metadata interactively.

## Best Practices

- Reference `examples/meta.json` for schema and `examples/template/meta.json` for a runnable sample.
- Keep path handling explicit and explain the base used for relative paths.
- Prefer `result.pdf_path` when reporting the final PDF.
- Use `from easypaper import EasyPaper, PaperGenerationRequest` directly.
- If EasyPaper is not importable, use `easypaper-setup-environment` first.

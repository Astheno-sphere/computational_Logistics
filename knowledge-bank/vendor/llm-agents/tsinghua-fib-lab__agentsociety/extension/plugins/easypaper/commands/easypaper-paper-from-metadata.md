Generate a paper directly from metadata using the EasyPaper Python SDK.

## Execution Contract

0. Optional pre-step: if the user has a research-materials folder instead of metadata JSON, run:

```python
metadata = await ep.generate_metadata_from_folder(
    folder_path,
    max_figures=12,
    max_tables=12,
    vision_enrich_figures=True,
)
```

Then generate from the returned `PaperMetaData`.

1. For metadata JSON, load it as a request model:

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
metadata = request.to_metadata()
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

result = await EasyPaper(config_path=str(Path("easypaper_config.yaml").resolve())).generate(
    metadata,
    **options,
)
```

2. Validate the metadata before generation:
   - Required prose fields are non-empty: `title`, `idea_hypothesis`, `method`, `data`, `experiments`.
   - `references` may be empty, but warn the user because citation quality will be weaker.
   - Figure ids start with `fig:` and table ids start with `tab:`.
   - Folder-generated metadata has absolute `materials_root` and relative POSIX figure/table paths.
   - Figure/table counts stay within the selected `max_figures` / `max_tables` caps.

## Path Handling

- Metadata should use relative paths where practical.
- Figure/table `file_path` values resolve from `materials_root` first, then current working directory.
- Metadata file loaders should set `materials_root` to the metadata file parent when it is omitted.
- `template_path` and local `code_repository.path` should be normalized against the metadata file parent before SDK execution.
- `output_dir` is an optional runtime setting; use the metadata value or a command-line override.
- Resolve `config_path` before constructing `EasyPaper`.

## Fallback Behavior

- Missing required fields: collect missing information interactively.
- Invalid metadata format: show validation errors and reference `examples/meta.json`.
- Package not installed: use `easypaper-setup-environment`.
- Config missing: use `easypaper-setup-environment` to create
  `easypaper_config.yaml` from the synchronized skill-bundled template, or ask
  for an explicit config path.
- Final PDF selection: prefer `result.pdf_path`, then `iteration_*_final/**/*.pdf`, latest `iteration_*`, then `paper.pdf`.

$ARGUMENTS

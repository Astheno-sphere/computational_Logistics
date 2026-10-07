Run the EasyPaper end-to-end paper generation workflow with guided setup and metadata collection.

## Execution Contract

### Phase 1: Environment setup

1. Check whether EasyPaper is usable:
   - `.easypaper-env` exists, or `python -c "import easypaper"` succeeds
   - A usable EasyPaper config exists at a user-provided path, `AGENT_CONFIG_PATH`,
     `./easypaper_config.yaml`, `./configs/openrouter.yaml`, or `./configs/example.yaml`
   - `pdflatex` is available when the user wants PDF output
2. If not ready, use the `easypaper-setup-environment` skill to create an isolated environment, install EasyPaper, create/validate configuration from the synchronized template, and guide LaTeX setup.

### Phase 2: Choose metadata source

Ask which source applies:

- **Complete metadata file / JSON**: use the `easypaper-paper-from-metadata` skill.
- **Research materials folder, SDK one-shot**: call `EasyPaper.generate_metadata_from_folder(...)`, then generate from the returned metadata.
- **Research materials folder, Claude-guided interactive build**: recommend `/easypaper-metadata-build` or invoke `easypaper-interactive-metadata-build`.
- **No metadata yet**: collect the required fields interactively, then generate.

Required prose fields:
- `title`
- `idea_hypothesis`
- `method`
- `data`
- `experiments`
- `references`

Common optional fields:
- `style_guide`, `target_pages`, `template_path`, `compile_pdf`
- `enable_review`, `enable_vlm_review`, `max_review_iterations`
- `materials_root`, `figures`, `tables`, `code_repository`, `output_dir`

## SDK Generation Pattern

Prefer loading JSON metadata as `PaperGenerationRequest`, then convert to SDK inputs:

```python
import json
from pathlib import Path
from easypaper import EasyPaper, PaperGenerationRequest

config_path = Path("easypaper_config.yaml").resolve()
request = PaperGenerationRequest.model_validate(
    json.loads(Path("metadata.json").read_text(encoding="utf-8"))
)

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

result = await EasyPaper(config_path=str(config_path)).generate(metadata, **options)
```

## Path Handling

- Metadata files should use relative paths where practical.
- Figure and table `file_path` values resolve from `materials_root` when set; otherwise they resolve from the current working directory.
- When loading metadata from a file, set `materials_root` to that metadata file's parent directory if it is missing.
- Normalize `template_path` and local `code_repository.path` relative to the metadata file parent before calling the SDK, because those fields are not resolved through `materials_root`.
- `output_dir` is an optional runtime output location and can be omitted or overridden at generation time.
- Keep `config_path` as a resolved local path.

## Review Flags

- `enable_review`: text review/revision loop, default `true`.
- `enable_vlm_review`: VLM/PDF visual review and page-overflow checks, default `false`.

## Final PDF Selection Rule

1. Use `result.pdf_path` first.
2. If missing, search `result.output_path` in order:
   - `iteration_*_final/**/*.pdf`
   - latest `iteration_*` directory PDF
   - root `paper.pdf`
3. If still missing, report final PDF unavailable and include compile error summary.

## User Experience Guidelines

- First-time users: trigger environment setup automatically.
- Use `examples/meta.json` as the schema/template reference.
- Use `examples/template/meta.json` as the self-contained runnable metadata example.
- Use the Python SDK directly; no API server is needed for normal generation.

$ARGUMENTS

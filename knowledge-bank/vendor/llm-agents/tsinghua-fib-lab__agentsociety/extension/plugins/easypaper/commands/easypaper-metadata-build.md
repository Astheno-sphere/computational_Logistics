Interactively build EasyPaper metadata from a research-materials folder using Claude Code's file-investigation tools. Output is JSON consumable by `/easypaper-paper-from-metadata`.

Use this command when the user wants Claude to co-author metadata instead of running the SDK one-shot `ep.generate_metadata_from_folder(...)` pipeline silently.

## Execution Contract

1. Present the three modes and wait for an explicit choice:
   - `[1] cold` — Claude walks the folder alone, no Python SDK call.
   - `[2] warm-start` (recommended) — call `ep.generate_metadata_from_folder(materials_root, max_figures=12, max_tables=12, vision_enrich_figures=False)` once, then review/edit every field with the user.
   - `[3] refine` — load an existing metadata JSON, validate it with the inline checks below, then walk the user through fixes and warnings.
2. Ask for the corresponding input:
   - `cold` / `warm-start`: `materials_root`; resolve it and verify it is an existing directory.
   - `refine`: existing metadata JSON path; verify it exists.
3. Ask for optional style/template settings:
   - `style_guide`: target venue or style guide.
   - `template_path`: path to the LaTeX template zip if known. If relative, interpret it relative to the saved metadata file location during generation.
4. Hand off to the `easypaper-interactive-metadata-build` skill for the detailed 6-phase workflow.
5. Save to `<materials_root>/easypaper_metadata.json` by default and tell the user to run `/easypaper-paper-from-metadata` next.

## Inline Validation Rules

Before saving, validate the in-memory metadata with public SDK/Pydantic plus explicit checks:

- `PaperGenerationRequest.model_validate(metadata_dict)` succeeds.
- `title`, `idea_hypothesis`, `method`, `data`, and `experiments` are non-empty strings.
- `materials_root` is set to a resolved directory for folder-derived metadata.
- `figures[].file_path` and `tables[].file_path` are relative POSIX paths under `materials_root`.
- Figure ids use the `fig:` prefix; table ids use the `tab:` prefix.
- Figure and table counts are within the selected caps.
- Empty `references` is a warning, not a hard failure.

## Output Rules

- `materials_root` is an absolute path to the source folder.
- Figure/table paths are relative POSIX paths under `materials_root`.
- Do not convert folder-derived figure/table paths to absolute paths in the saved metadata.
- `template_path` may be omitted or written relative to the metadata file location when it is part of the same portable project.

$ARGUMENTS

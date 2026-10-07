Set up EasyPaper environment including Python dependencies and LaTeX toolchain.

## Execution contract

1. Use the `easypaper-setup-environment` skill to:
   - Create isolated virtual environment (prefer `uv`, fallback to `venv`)
   - Install easypaper package
   - Create or validate `easypaper_config.yaml` from the skill-bundled
     `config.example.yaml` template when the user does not already have config
   - Check LaTeX installation and provide installation instructions if missing
   - Verify all components are working

2. After setup, provide clear instructions on:
   - How to activate the environment
   - How to use EasyPaper as Python SDK: `from easypaper import EasyPaper, PaperMetaData`
   - Which config path will be used for generation
   - Next steps for using the plugin

$ARGUMENTS

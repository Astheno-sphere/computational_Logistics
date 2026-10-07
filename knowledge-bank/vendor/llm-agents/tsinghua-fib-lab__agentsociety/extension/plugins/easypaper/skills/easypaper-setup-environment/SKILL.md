---
description: Automatically set up EasyPaper environment including Python dependencies and LaTeX toolchain in an isolated environment.
---

Use this skill when the plugin is first installed or when environment setup is needed.

## Setup Workflow

### 1. Check Python Environment

- Detect if `uv` is available (preferred) or `python`/`python3`
- If `uv` is available, use it to create an isolated virtual environment
- If not, check for `venv` or `virtualenv` and create a virtual environment
- Environment should be created in a project-local directory (e.g., `.venv` or `.easypaper-env`)

### 2. Install EasyPaper Package

- If `uv` is available:
  ```bash
  uv venv .easypaper-env
  source .easypaper-env/bin/activate  # or .easypaper-env/Scripts/activate on Windows
  uv pip install -e .  # if in repo root
  # OR
  uv pip install easypaper[server]  # if installing from PyPI
  ```
- If using standard Python:
  ```bash
  python -m venv .easypaper-env
  source .easypaper-env/bin/activate
  pip install -e .  # or pip install easypaper[server]
  ```

### 3. Check LaTeX Installation

- Check for LaTeX distribution:
  - On macOS: Check for `pdflatex` command, suggest `brew install --cask mactex` or `brew install basictex`
  - On Linux: Check for `pdflatex`, suggest `sudo apt-get install texlive-full` or `texlive-base`
  - On Windows: Check for `pdflatex`, suggest installing MiKTeX or TeX Live
- Verify installation by running: `pdflatex --version`
- If not installed, provide clear installation instructions for the user's OS

### 4. Create or Validate Configuration

- Check for an existing EasyPaper YAML config in this order:
  - User-provided path in the conversation
  - `AGENT_CONFIG_PATH`
  - `./easypaper_config.yaml`
  - `./configs/openrouter.yaml`
  - `./configs/example.yaml`
- If no usable config exists, create `./easypaper_config.yaml` from the bundled
  sibling template file `config.example.yaml`.
- The bundled `config.example.yaml` must stay byte-for-byte synchronized with
  the repository source template `configs/example.yaml`; do not hand-write a
  partial config in this skill.
- After creating the file, ask the user for the required LLM API key/provider
  value and replace only the placeholder values they explicitly provide
  (for example `YOUR_OPENROUTER_KEY`). Do not invent credentials.
- Keep the generated config path explicit for later SDK calls, either by using
  `EasyPaper(config_path="<absolute path to easypaper_config.yaml>")` or by
  setting `AGENT_CONFIG_PATH` for commands that call `load_config()`.
- The template enables the skills system. Users do not need a local `./skills`
  folder: EasyPaper loads packaged built-in skills first, then overlays user
  skills from `skills_dir` when that directory exists.

### 5. Verify Setup

- Test EasyPaper import: `python -c "import easypaper; from easypaper import EasyPaper, PaperMetaData; print('EasyPaper imported successfully')"`
- Test LaTeX: `pdflatex --version`
- Test config parsing when a config path exists:
  `python -c "from easypaper import EasyPaper; EasyPaper(config_path='easypaper_config.yaml'); print('EasyPaper config loaded successfully')"`

### 6. Create Environment Activation Script

Create a helper script (`.easypaper-activate.sh` or `.easypaper-activate.bat`) that:
- Activates the virtual environment
- Sets up PATH if needed
- Provides instructions for using EasyPaper as Python SDK
- Exports `AGENT_CONFIG_PATH` to the generated config path when practical

## Error Handling

- If Python version < 3.11, inform user and suggest upgrade
- If package installation fails, show error and suggest manual installation
- If LaTeX is missing, provide OS-specific installation commands
- If the config template file is missing from the installed skill directory,
  report the plugin installation as incomplete and ask the user to reinstall
  the EasyPaper Claude Code plugin.
- Always verify each step before proceeding to the next

## Post-Setup Instructions

After successful setup, inform the user:
1. Environment is ready in `.easypaper-env`
2. To activate: `source .easypaper-env/bin/activate` (or equivalent for Windows)
3. EasyPaper can now be used directly as a Python SDK: `from easypaper import EasyPaper, PaperMetaData`
4. The environment is isolated and won't affect system Python
5. The active config file path, normally `./easypaper_config.yaml`

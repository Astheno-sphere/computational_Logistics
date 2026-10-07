# Installation

[简体中文](installation_zh.md) · [Back to README](../README.md)

Clone the repository:

```bash
git clone https://github.com/Yinsongxu/LLM2Jev.git
cd LLM2Jev
```

SGLang is the recommended backend on Linux with a supported NVIDIA GPU. It also
installs its Transformers dependency:

```bash
uv sync --extra sglang
```

For a Transformers-only environment:

```bash
uv sync --extra transformers
```

For an editable pip installation, use the corresponding extra:

```bash
python -m pip install -e ".[sglang]"
# Or: python -m pip install -e ".[transformers]"
```

After installing with uv, activate the virtual environment:

```bash
source .venv/bin/activate
```

After installation, follow the [Usage guide](usage.md) to run Python examples or start the HTTP service.

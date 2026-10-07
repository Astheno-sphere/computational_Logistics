# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import tomllib
from datetime import datetime
from pathlib import Path

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

# Read version from package pyproject.toml
# docs live at packages/agentsociety/docs/ (not repo-root docs/)
_DOCS_DIR = Path(__file__).resolve().parent
_PKG_ROOT = _DOCS_DIR.parent
_pyproject = _PKG_ROOT / "pyproject.toml"
with open(_pyproject, "rb") as f:
    _version = tomllib.load(f)["project"]["version"]

project = "AgentSociety"
copyright = f"{datetime.now().year}, FIBLAB"
author = "严宇威, 闫珺博, 张钧"

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
version = ".".join(_version.split(".")[:2])  # e.g., "1.5"
release = _version

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "myst_parser",
    "autodoc2",
]

autodoc2_packages = [
    # relative to this conf.py (packages/agentsociety/docs/)
    "../agentsociety",
]
autodoc2_render_plugin = "myst"

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Internationalization options --------------------------------------------
# 设置国际化支持
locale_dirs = ["locale/"]  # 翻译文件所在的路径

# 默认语言设置为中文
language = "zh"

# 多语言配置
html_context = {
    "current_language": language,
    "languages": {
        "zh": "中文",
        "en": "English",
    },
}

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_title = "AgentSociety"
html_theme = "furo"
html_theme_options = {
    "top_of_page_buttons": ["view", "edit"],
    "source_repository": "https://github.com/tsinghua-fib-lab/agentsociety/",
    "source_branch": "main",
    "source_directory": "packages/agentsociety/docs/",
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/tsinghua-fib-lab/agentsociety/",
            "html": """
                <svg stroke="currentColor" fill="currentColor" stroke-width="0" viewBox="0 0 16 16">
                    <path fill-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z"></path>
                </svg>
            """,
            "class": "",
        },
    ],
}

# 添加侧边栏logo
html_logo = "_static/logo/1.png"

# 添加favicon
html_favicon = "_static/logo/square.png"

# 添加自定义CSS
html_css_files = ["css/custom.css"]

html_static_path = ["_static"]

# -- Options for LaTeX output ------------------------------------------------
latex_elements = {
    # The paper size ('letterpaper' or 'a4paper').
    "papersize": "a4paper",
    # The font size ('10pt', '11pt' or '12pt').
    "pointsize": "11pt",
    # Additional stuff for the LaTeX preamble.
    "preamble": r"""
    \usepackage{xeCJK}
    \setCJKmainfont{SimSun}
    """,
}

# -- Options for Epub output -------------------------------------------------
epub_title = project
epub_exclude_files = ["search.html"]

# -- Extension configuration -------------------------------------------------

# autodoc2 emits ambiguous short refs like ``type`` across many models.
nitpick_ignore_regex = [
    (r"py:.*", r"type"),
]
suppress_warnings = [
    "ref.python",
]

# -- Options for intersphinx extension ---------------------------------------
# Example configuration for intersphinx: refer to the Python standard library.
intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
}

# -- Options for MyST parser -------------------------------------------------
myst_enable_extensions = [
    "amsmath",
    "attrs_block",
    "attrs_inline",
    "colon_fence",
    "deflist",
    "dollarmath",
    "html_admonition",
    "html_image",
    "linkify",
    "replacements",
    "smartquotes",
    "substitution",
    "tasklist",
]
# Auto-generate heading anchors; custom ``{#id}`` also works with attrs_* above.
myst_heading_anchors = 2

from __future__ import annotations

import ast
import re
from pathlib import Path

from agentsociety2.skills.analysis.harness.models import ValidationResult
from agentsociety2.skills.analysis.harness.validators._helpers import (
    CHART_NAME_RE,
    FIGURE_NAME_RE,
    blocked,
    issue,
    passed,
)

_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_FORBIDDEN_CMAPS = {"jet", "rainbow", "gist_rainbow", "nipy_spectral"}
_GENERIC_TITLES = {"result", "results", "figure", "chart", "analysis"}


def _attribute_path(node: ast.AST | None) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _attribute_path(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _string_literals(node: ast.AST | None) -> list[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        values: list[str] = []
        for item in node.elts:
            values.extend(_string_literals(item))
        return values
    return []


def _constant_strings(node: ast.AST | None) -> set[str]:
    return set(_string_literals(node))


def _collect_import_aliases(tree: ast.AST) -> tuple[set[str], set[str], set[str]]:
    matplotlib_aliases: set[str] = set()
    pyplot_aliases: set[str] = set()
    seaborn_aliases: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "matplotlib":
                    matplotlib_aliases.add(alias.asname or alias.name)
                elif alias.name == "matplotlib.pyplot":
                    pyplot_aliases.add(alias.asname or alias.name)
                elif alias.name == "seaborn":
                    seaborn_aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module == "matplotlib":
                for alias in node.names:
                    if alias.name == "pyplot":
                        pyplot_aliases.add(alias.asname or alias.name)
                    elif alias.name == "use":
                        matplotlib_aliases.add(alias.asname or alias.name)
            elif node.module == "matplotlib.pyplot":
                for alias in node.names:
                    pyplot_aliases.add(alias.asname or alias.name)
            elif node.module == "seaborn":
                seaborn_aliases.add(alias.asname or alias.name)
    return matplotlib_aliases, pyplot_aliases, seaborn_aliases


def validate_chart_script(code: str) -> ValidationResult:
    issues = []
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return blocked(
            [
                issue(
                    "invalid_python",
                    phase="refine",
                    message=str(exc),
                    fix_hint="Fix syntax in chart script",
                )
            ]
        )

    matplotlib_aliases, pyplot_aliases, seaborn_aliases = _collect_import_aliases(tree)
    if not (matplotlib_aliases or pyplot_aliases or seaborn_aliases):
        return passed()

    has_agg = False
    has_svg_fonttype = False
    has_font_family = False
    has_sans_serif = False
    has_save = False
    has_xlabel = False
    has_ylabel = False
    has_specific_title = False
    has_tight_layout = False
    forbidden_cmaps: set[str] = set()
    non_english_legend: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            path = _attribute_path(node.func)
            func_name = path.rsplit(".", 1)[-1]

            if (
                path in matplotlib_aliases
                or path == "use"
                or any(path == f"{alias}.use" for alias in matplotlib_aliases)
                or any(path == f"{alias}.switch_backend" for alias in pyplot_aliases)
            ):
                if node.args and "Agg" in _constant_strings(node.args[0]):
                    has_agg = True

            if func_name in {"savefig", "save_chart_bundle"}:
                has_save = True
            if func_name in {"set_xlabel", "xlabel"}:
                has_xlabel = True
            if func_name in {"set_ylabel", "ylabel"}:
                has_ylabel = True
            if func_name in {"tight_layout", "subplots_adjust"}:
                has_tight_layout = True
            if func_name in {"set_title", "title", "suptitle"} and node.args:
                titles = [s.strip().lower() for s in _string_literals(node.args[0])]
                if any(t and t not in _GENERIC_TITLES for t in titles):
                    has_specific_title = True

            rcparams_aliases = pyplot_aliases | matplotlib_aliases
            if any(path == f"{alias}.rcParams.update" for alias in rcparams_aliases):
                dict_nodes = [arg for arg in node.args if isinstance(arg, ast.Dict)]
                for dict_node in dict_nodes:
                    for key_node, value_node in zip(dict_node.keys, dict_node.values):
                        keys = _constant_strings(key_node)
                        values = _constant_strings(value_node)
                        if "font.family" in keys:
                            has_font_family = True
                        if "font.sans-serif" in keys or "sans-serif" in values:
                            has_sans_serif = True
                        if "svg.fonttype" in keys and "none" in values:
                            has_svg_fonttype = True

            for keyword in node.keywords:
                if keyword.arg in {"cmap", "palette"}:
                    forbidden_cmaps.update(
                        s
                        for s in _string_literals(keyword.value)
                        if s.lower() in _FORBIDDEN_CMAPS
                    )
                if keyword.arg not in {"label", "labels", "title"}:
                    continue
                if keyword.arg == "title" and func_name != "legend":
                    continue
                for literal in _string_literals(keyword.value):
                    if _CJK_RE.search(literal):
                        non_english_legend.add(literal)

            if func_name == "legend" and node.args:
                for literal in _string_literals(node.args[0]):
                    if _CJK_RE.search(literal):
                        non_english_legend.add(literal)

        if isinstance(node, ast.Assign):
            targets = node.targets
            if len(targets) == 1 and isinstance(targets[0], ast.Subscript):
                sub = targets[0]
                if _attribute_path(sub.value).endswith("rcParams"):
                    if isinstance(sub.slice, ast.Constant):
                        key = str(sub.slice.value)
                        if (
                            key == "svg.fonttype"
                            and isinstance(node.value, ast.Constant)
                            and str(node.value.value) == "none"
                        ):
                            has_svg_fonttype = True
                        if key == "font.family":
                            has_font_family = True
                        if key == "font.sans-serif":
                            has_sans_serif = True

    if not has_agg:
        issues.append(
            issue(
                "missing_agg_backend",
                phase="refine",
                message='matplotlib.use("Agg") not found',
                fix_hint='Add matplotlib.use("Agg") at top of script',
            )
        )
    if not has_svg_fonttype:
        issues.append(
            issue(
                "missing_svg_fonttype",
                phase="refine",
                message='rcParams["svg.fonttype"] = "none" not found',
                fix_hint='Set plt.rcParams["svg.fonttype"] = "none"',
            )
        )
    if not has_font_family:
        issues.append(
            issue(
                "missing_font_family",
                phase="refine",
                message="sans-serif font family not configured",
                fix_hint="Set font.family and font.sans-serif in rcParams",
            )
        )
    if not has_sans_serif:
        issues.append(
            issue(
                "missing_sans_serif_stack",
                phase="refine",
                message="font.sans-serif stack not configured",
                fix_hint="Set rcParams['font.sans-serif'] to Arial/Helvetica/DejaVu Sans fallback list",
            )
        )
    if not has_save:
        issues.append(
            issue(
                "chart_not_saved",
                phase="refine",
                message="No savefig or save_chart_bundle call found",
                fix_hint="Save a PNG output under charts/ before validate-chart --chart-path",
            )
        )
    if not has_xlabel:
        issues.append(
            issue(
                "x_axis_unlabeled",
                phase="refine",
                message="No x-axis label call found",
                fix_hint="Call ax.set_xlabel(...) or plt.xlabel(...) with metric/scope",
            )
        )
    if not has_ylabel:
        issues.append(
            issue(
                "y_axis_unlabeled",
                phase="refine",
                message="No y-axis label call found",
                fix_hint="Call ax.set_ylabel(...) or plt.ylabel(...) with units where possible",
            )
        )
    if not has_specific_title:
        issues.append(
            issue(
                "chart_title_generic",
                phase="refine",
                message="No specific chart title found",
                fix_hint="Use a title that names the metric and comparison, not just 'Results'",
            )
        )
    if not has_tight_layout:
        issues.append(
            issue(
                "layout_not_tightened",
                phase="refine",
                message="No tight_layout or subplots_adjust call found",
                fix_hint="Call fig.tight_layout() or adjust subplot spacing before saving",
            )
        )
    if forbidden_cmaps:
        issues.append(
            issue(
                "forbidden_rainbow_palette",
                phase="refine",
                message=f"Forbidden colormap/palette used: {sorted(forbidden_cmaps)}",
                fix_hint="Use Okabe-Ito, viridis, cividis, plasma, PuOr, RdBu, or BrBG",
            )
        )
    if non_english_legend:
        issues.append(
            issue(
                "legend_not_english",
                phase="refine",
                message=f"Legend text must be English-only: {sorted(non_english_legend)}",
                fix_hint="Keep legend labels in English; explain bilingually in captions/report prose",
            )
        )

    if issues:
        return blocked(issues)
    return passed()


def validate_chart_file(
    chart_path: Path,
    *,
    max_charts: int,
    current_count: int,
) -> ValidationResult:
    issues = []
    if not chart_path.exists():
        issues.append(
            issue(
                "chart_missing",
                phase="refine",
                message=f"Chart file not found: {chart_path}",
                fix_hint="Generate the missing chart",
            )
        )
        return blocked(issues)

    name = chart_path.name
    if not (CHART_NAME_RE.match(name) or FIGURE_NAME_RE.match(name)):
        issues.append(
            issue(
                "chart_naming",
                phase="refine",
                message=f"Chart name does not match convention: {name}",
                fix_hint="Use chart_NN_slug.png or figure_NN_slug.png",
            )
        )

    if chart_path.suffix.lower() == ".png" and chart_path.stat().st_size < 100:
        issues.append(
            issue(
                "chart_empty_file",
                phase="refine",
                message=f"Chart file too small: {chart_path}",
                fix_hint="Regenerate chart; output may be blank",
            )
        )

    if max_charts > 0 and current_count >= max_charts:
        issues.append(
            issue(
                "chart_budget_exceeded",
                phase="refine",
                message=f"Chart count {current_count} >= cap {max_charts}",
                fix_hint="Remove a chart or set max_charts to 0 in state.yaml (no cap)",
            )
        )

    if issues:
        return blocked(issues)
    return passed()

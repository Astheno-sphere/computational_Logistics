"""Compatibility helpers for custom environment modules."""

from __future__ import annotations

import inspect
import os
from pathlib import Path
from typing import Any

from agentsociety2.agent.base import AgentBase
from agentsociety2.backend.services.custom.models import (
    CompatibilityIssue,
    ScanDiagnostic,
)
from agentsociety2.env.base import EnvBase

ENV_COMPATIBILITY_RULES = [
    "最终自定义环境模块必须落在 custom/envs/*.py。",
    "类定义必须在目标文件内，不能只做 re-export。",
    "环境类必须继承 EnvBase，注册 key 保持 class_name。",
    "至少提供一个合法 @tool 方法。",
    "必须实现 step()，并且默认支持无参实例化 cls()。",
    "description() 必须可调用且返回非空短说明。",
    "init_description() 必须可调用且返回非空初始化参数说明。",
    "若模块需要观察能力，应通过 readonly 的 kind='observe' 工具提供。",
]

AGENT_COMPATIBILITY_RULES = [
    "最终自定义 agent 必须落在 custom/agents/*.py。",
    "类定义必须在目标文件内，不能只做 re-export。",
    "Agent 类必须继承 AgentBase，注册 key 保持 class_name。",
    "必须实现三个抽象方法：to_workspace、ask、step（均为 async）。",
    "构造函数必须无参（cls() 可实例化），真实初始化在 restore() 中完成。",
    "description() 必须可调用且返回非空短说明。",
    "init_description() 必须可调用且返回非空初始化参数说明。",
]


def ensure_relative_to_workspace(workspace_path: Path, target_path: Path | str) -> str:
    """Return a normalized path relative to its workspace."""

    resolved_workspace = os.path.realpath(os.fspath(workspace_path))
    resolved_target = os.path.realpath(os.fspath(target_path))
    normalized_workspace = os.path.normcase(resolved_workspace)
    normalized_target = os.path.normcase(resolved_target)
    workspace_prefix = (
        normalized_workspace
        if normalized_workspace.endswith(os.sep)
        else normalized_workspace + os.sep
    )
    if normalized_target != normalized_workspace and not normalized_target.startswith(
        workspace_prefix
    ):
        raise ValueError("Target path escapes workspace")
    return os.path.relpath(resolved_target, resolved_workspace)


def get_registered_tool_names(obj: Any) -> list[str]:
    """Return registered tool names for a class or instance."""

    tools = getattr(obj, "_registered_tools", {}) or {}
    return list(tools.keys())


def is_no_arg_constructible(cls: type[Any]) -> tuple[bool, list[str]]:
    """Check whether a class can be instantiated with cls()."""

    signature = inspect.signature(cls)
    required_params: list[str] = []
    for parameter in signature.parameters.values():
        if parameter.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        if parameter.default is inspect.Parameter.empty:
            required_params.append(parameter.name)
    return not required_params, required_params


def overrides_base_method(
    cls: type[Any], base_cls: type[Any], method_name: str
) -> bool:
    """Return True when cls resolves method_name to an override beyond base_cls."""

    cls_method = inspect.getattr_static(cls, method_name, None)
    base_method = inspect.getattr_static(base_cls, method_name, None)
    return cls_method is not None and cls_method is not base_method


def build_env_scan_diagnostic(
    *,
    workspace_path: Path,
    module_path: str,
    file_path: Path,
    cls: type[Any],
) -> ScanDiagnostic:
    """Build structured compatibility diagnostics for an env class."""

    issues: list[CompatibilityIssue] = []
    tool_names = get_registered_tool_names(cls)
    has_step = overrides_base_method(cls, EnvBase, "step")
    is_no_arg, required_params = is_no_arg_constructible(cls)

    if not has_step:
        issues.append(
            CompatibilityIssue(
                code="missing_step",
                check="step_method",
                message=f"{cls.__name__} 缺少 step() 方法",
            )
        )

    if not tool_names:
        issues.append(
            CompatibilityIssue(
                code="missing_tools",
                check="registered_tools",
                message=f"{cls.__name__} 没有注册任何 @tool 方法",
            )
        )

    if not is_no_arg:
        issues.append(
            CompatibilityIssue(
                code="non_default_constructor",
                check="default_constructor",
                message=(
                    f"{cls.__name__} 不能直接通过 cls() 实例化，"
                    f"缺少默认值的参数: {required_params}"
                ),
                details={"required_parameters": required_params},
            )
        )

    try:
        description = cls.description() if hasattr(cls, "description") else ""
        if not description:
            issues.append(
                CompatibilityIssue(
                    code="empty_description",
                    check="description",
                    message=f"{cls.__name__} 的 description() 为空",
                )
            )
    except Exception as exc:
        issues.append(
            CompatibilityIssue(
                code="description_error",
                check="description",
                message=f"{cls.__name__} 的 description() 调用失败: {exc}",
            )
        )

    try:
        init_description = (
            cls.init_description() if hasattr(cls, "init_description") else ""
        )
        if not init_description:
            issues.append(
                CompatibilityIssue(
                    code="empty_init_description",
                    check="init_description",
                    message=f"{cls.__name__} 的 init_description() 为空",
                )
            )
    except Exception as exc:
        issues.append(
            CompatibilityIssue(
                code="init_description_error",
                check="init_description",
                message=f"{cls.__name__} 的 init_description() 调用失败: {exc}",
            )
        )

    accepted = not any(issue.severity == "error" for issue in issues)
    return ScanDiagnostic(
        module_kind="env_module",
        module_path=module_path,
        file_path=str(file_path),
        class_name=cls.__name__,
        accepted=accepted,
        issues=issues,
        metadata={
            "tool_names": tool_names,
            "tool_count": len(tool_names),
            "has_step": has_step,
            "default_constructible": is_no_arg,
            "type": cls.__name__,
            "class_name": cls.__name__,
            "workspace_module_path": ensure_relative_to_workspace(
                workspace_path, file_path
            ),
        },
    )


def build_agent_scan_diagnostic(
    *,
    workspace_path: Path,
    module_path: str,
    file_path: Path,
    cls: type[Any],
) -> ScanDiagnostic:
    """Build structured compatibility diagnostics for an agent class."""

    issues: list[CompatibilityIssue] = []
    has_to_workspace = overrides_base_method(cls, AgentBase, "to_workspace")
    has_ask = overrides_base_method(cls, AgentBase, "ask")
    has_step = overrides_base_method(cls, AgentBase, "step")
    is_no_arg, required_params = is_no_arg_constructible(cls)

    for name, present in (
        ("to_workspace", has_to_workspace),
        ("ask", has_ask),
        ("step", has_step),
    ):
        if not present:
            issues.append(
                CompatibilityIssue(
                    code=f"missing_{name}",
                    check=f"{name}_method",
                    message=(
                        f"{cls.__name__} 缺少 {name}() 抽象方法实现"
                        "（AgentBase 的三个必需抽象方法：to_workspace/ask/step）"
                    ),
                )
            )

    if not is_no_arg:
        issues.append(
            CompatibilityIssue(
                code="non_default_constructor",
                check="default_constructor",
                message=(
                    f"{cls.__name__} 不能直接通过 cls() 实例化，"
                    f"缺少默认值的参数: {required_params}（agent 构造必须无参，"
                    "真实初始化在 restore() 中完成）"
                ),
                details={"required_parameters": required_params},
            )
        )

    try:
        description = cls.description() if hasattr(cls, "description") else ""
        if not description:
            issues.append(
                CompatibilityIssue(
                    code="empty_description",
                    check="description",
                    message=f"{cls.__name__} 的 description() 为空",
                )
            )
    except Exception as exc:
        issues.append(
            CompatibilityIssue(
                code="description_error",
                check="description",
                message=f"{cls.__name__} 的 description() 调用失败: {exc}",
            )
        )

    try:
        init_description = (
            cls.init_description() if hasattr(cls, "init_description") else ""
        )
        if not init_description:
            issues.append(
                CompatibilityIssue(
                    code="empty_init_description",
                    check="init_description",
                    message=f"{cls.__name__} 的 init_description() 为空",
                )
            )
    except Exception as exc:
        issues.append(
            CompatibilityIssue(
                code="init_description_error",
                check="init_description",
                message=f"{cls.__name__} 的 init_description() 调用失败: {exc}",
            )
        )

    accepted = not any(issue.severity == "error" for issue in issues)
    return ScanDiagnostic(
        module_kind="agent",
        module_path=module_path,
        file_path=str(file_path),
        class_name=cls.__name__,
        accepted=accepted,
        issues=issues,
        metadata={
            "has_to_workspace": has_to_workspace,
            "has_ask": has_ask,
            "has_step": has_step,
            "default_constructible": is_no_arg,
            "type": cls.__name__,
            "class_name": cls.__name__,
            "workspace_module_path": ensure_relative_to_workspace(
                workspace_path, file_path
            ),
        },
    )


def build_import_error_diagnostic(
    *,
    module_kind: str,
    file_path: Path,
    module_path: str,
    error: Exception,
) -> ScanDiagnostic:
    """Build a diagnostic entry for import-time failures."""

    return ScanDiagnostic(
        module_kind=module_kind,  # type: ignore[arg-type]
        module_path=module_path,
        file_path=str(file_path),
        accepted=False,
        issues=[
            CompatibilityIssue(
                code="import_error",
                check="import",
                message=f"{file_path.name} 导入失败: {error}",
            )
        ],
        metadata={},
    )

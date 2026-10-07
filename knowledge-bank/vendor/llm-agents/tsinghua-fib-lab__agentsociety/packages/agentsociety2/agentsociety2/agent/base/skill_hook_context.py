"""Context exposed to no-arg skill lifecycle-hook functions.

中文：为无入参的 skill 生命周期 hook 函数提供运行上下文。
English: Runtime context for no-arg skill lifecycle-hook functions.

When the skill runtime detects a hook function (e.g. ``pre_step``) in a skill
script module, it activates a :class:`HookContext` via a contextvar before
calling the function. The function reads it with :func:`get_hook_context`
instead of taking arguments — keeping the signature no-arg (sync or async).
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class HookContext:
    """Active hook context.

    Args:
        workspace_root: The agent workspace root (replaces AGENT_WORK_DIR).
        skill_dir: The skill package root (replaces SKILL_DIR).
        skill_id: Registry skill id (``namespace@name``).
        hook_type: Lifecycle hook name (``pre_step`` / ``post_step``).
        payload: The lifecycle payload dict (``time``, ``agent_id``,
            ``step_count``, ``tick``, ...).
    """

    workspace_root: Path
    skill_dir: Path
    skill_id: str
    hook_type: str
    payload: dict[str, Any]


_hook_ctx: contextvars.ContextVar[HookContext | None] = contextvars.ContextVar(
    "skill_hook_ctx", default=None
)


def get_hook_context() -> HookContext:
    """Return the active hook context (raises if called outside a hook).

    Args:
        None.

    Returns:
        The active :class:`HookContext`.

    Raises:
        RuntimeError: When no hook is active.
    """
    ctx = _hook_ctx.get()
    if ctx is None:
        raise RuntimeError("get_hook_context() called outside a lifecycle hook")
    return ctx


def _set_hook_context(ctx: HookContext) -> contextvars.Token[HookContext | None]:
    """Activate a hook context (internal — used by the runtime).

    Args:
        ctx: The hook context to activate.

    Returns:
        A token to pass to :func:`_reset_hook_context`.
    """
    return _hook_ctx.set(ctx)


def _reset_hook_context(token: contextvars.Token[HookContext | None]) -> None:
    """Deactivate a hook context (internal — used by the runtime).

    Args:
        token: The token returned by :func:`_set_hook_context`.

    Returns:
        None.
    """
    _hook_ctx.reset(token)

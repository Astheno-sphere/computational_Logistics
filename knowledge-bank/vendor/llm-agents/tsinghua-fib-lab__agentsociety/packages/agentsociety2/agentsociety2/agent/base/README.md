# AgentBase — Agent 基类开发指南

> 本文档面向 **子类开发者**。``AgentBase`` 位于
> ``agentsociety2.agent.base.agent``，是所有 agent 的基类。本文描述的是
> **重构后（公开 API）** 的接口 —— 子类面向的方法/属性已去掉 ``_`` 前缀，
> 通用机器全部由基类直接拥有，子类不再需要 mixin。

---

## 1. 概述

``AgentBase`` 是所有 agent 的基类。它 **直接拥有** 以下通用能力（无 mixin、
无多继承）：

- **workspace 绑定**：``AgentBase`` 负责读取/写入 ``config.json`` 与
  ``AGENT.json``，挂载 ``WorkspaceFS``、trace writer，并把 workspace 绑定
  到 skill runtime。
- **skill runtime**：``AgentBase`` 持有 ``AgentSkillRuntime`` 实例
  （``self.skill_runtime``），负责 skill 注册表、可见/激活 skill 集合、
  skill 脚本执行与生命周期 hook 调度。
- **ReAct 循环**：``run_react_loop`` 是通用的 ReAct 编排 —— 构造提示词、
  调用 LLM、解析工具决策、执行工具、循环直至 ``finish`` 或回合上限。
- **LLM 调用**：通过注入的 ``self._dispatcher`` 调用默认 LLM，并自带一次
  参数错误重试。
- **工具调度**：``dispatch_react_tool`` 处理 workspace 文件、skill 与
  ``ask_env`` 工具；子类可覆盖以增加前缀（如 ``memory_*`` / ``todo_*``）。
- **TODO 状态**：``dispatch_todo_tool`` + 一组 TODO 归一化/存储 helper。
- **trace**：``trace_span`` 上下文管理器写 agent 级 trace span。
- **AGENT.json 持久化**：``persist_agent_json`` 把 agent 自描述快照写入
  ``AGENT.json``；``build_agent_json`` 构造其内容（子类可扩展字段）。
  面向提示词的投影是 ``build_prompt_agent_view``（剥掉 ``initialized_at`` /
  ``current_time`` / ``tick`` / ``step_count`` / 绝对 ``workspace.root``，保留
  子类扩展字段）与 ``build_prompt_turn_state``（每步状态，单独成块）——
  两者都由同一份 ``build_agent_json`` 派生，避免漂移。
- **构造模型**：``create`` / ``from_workspace`` / 无参 ``__init__``。

子类只需实现 **person / 业务专属逻辑**（如 memory、game 状态、自定义
prompt），其余全部继承自基类。

---

## 2. 构造模型

``AgentBase`` 不通过 ``__init__(...)`` 传参构造。请使用以下两个类方法：

| 入口 | 说明 |
| --- | --- |
| ``AgentBase.create(workspace_path, profile, config)`` | **静态写一次**：把 ``config.json`` + 初始 ``AGENT.json`` + 标准空目录写入 workspace。**不返回** agent 实例。 |
| ``await AgentBase.from_workspace(workspace_path, service_proxy)`` | 重建 ready agent：``agent = cls()``（无参）→ ``await agent.restore(ws, proxy)`` → 返回。 |
| ``AgentBase.__init__(self)`` | 无参。只设置空 slot，不做任何 profile 解析、不要求 id。真正初始化发生在 ``restore()``。 |
| ``await agent.restore(workspace_path, service_proxy)`` | **真正的初始化**：读 ``config.json`` + ``AGENT.json``；设置 ``_id`` / ``_profile`` / ``_name`` / ``_config``；调用内部 ``_bind_services`` + ``_bind_workspace``；恢复 visible/activated skill 与计数器。**子类覆盖此方法** 在 ``await super().restore(...)`` 之后追加业务状态。 |

> 子类 **不要** 直接重写 ``__init__`` / ``create`` / ``from_workspace``
> （除非确有需要，例如 game-agent 自定义 workspace 结构）。最常见的扩展点
> 是覆盖 ``restore``。

---

## 3. 子类必须实现 / 覆盖的方法

| 方法 | 说明 | 是否必须 |
| --- | --- | --- |
| ``to_workspace(self, workspace_path)`` | 把当前动态状态写回 workspace（``AGENT.json`` 等）。 | **必须实现**（abstract） |
| ``ask(self, message, readonly=True, *, t=None)`` | 通过 agent 的推理流程回答外部问题。 | **必须实现**（abstract） |
| ``step(self, tick, t)`` | 执行一个仿真步。 | **必须实现**（abstract） |
| ``restore(self, workspace_path, service_proxy)`` | 在 ``await super().restore(...)`` 之后追加业务专属状态恢复。基类有具体实现，**推荐覆盖**。 | 推荐覆盖 |
| ``build_react_messages(self, *, tick, t, observations, question=None, readonly=False, skill_hooks=None)`` | 构造 ReAct 提示词（OpenAI 风格 chat messages）。基类实现 ``raise NotImplementedError`` —— **若复用基类的 ``run_react_loop`` 则必须覆盖**。 | 视情况必须 |
| ``build_agent_json(self, *, tick, t)`` | 构造 ``AGENT.json`` 内容。基类已有默认实现；子类可覆盖以扩展字段（如 memory / 自定义 skill 集合），记得 ``data = super().build_agent_json(...)`` 再追加。 | 推荐覆盖 |
| ``build_prompt_agent_view(self, *, tick, t)`` | 由 ``build_agent_json`` 派生面向提示词的 ``<agent>`` 视图：剥掉逐轮字段（``current_time`` / ``tick`` / ``step_count`` / ``initialized_at``）与绝对 ``workspace.root``，保留子类扩展字段。这些剥掉的字段不会丢——时间走单独的 ``<turn_state>`` 块。 | 一般不用覆盖 |
| ``build_prompt_turn_state(self, *, tick, t)`` | 构造每步 ``<turn_state>`` 块（``current_time`` / ``tick`` / ``step_count``）。 | 一般不用覆盖 |
| ``dispatch_react_tool(self, action, args, *, readonly=False)`` | 分发单个 ReAct 工具。基类已处理 ``read`` / ``write`` / ``append`` / ``list`` / ``grep`` / ``activate_skill`` / ``deactivate_skill`` / ``read_skill_file`` / ``execute_skill_script`` / ``ask_env``。子类可覆盖以增加前缀（如 ``memory_*`` / ``todo_*``），未命中的转发给 ``await super().dispatch_react_tool(...)``。 | 推荐覆盖 |

> ``create`` 与 ``from_workspace`` 在基类已有 **具体实现**，子类一般直接
> 继承即可（PersonAgent 即如此，已删除纯转发的薄包装）。

---

## 4. 子类可调用的通用方法 / 属性

下表是子类在实现 ``step`` / ``ask`` / ``restore`` 等时常调用的公开 API：

| 方法 / 属性 | 用途 |
| --- | --- |
| ``await self.run_react_loop(*, tick, t, observations=None, question=None, readonly=False, skill_hooks=None)`` | 运行通用 ReAct 循环直至 ``finish`` 或回合上限，返回最终字符串。 |
| ``await self.acompletion(messages, stream=False, **kwargs)`` | 一次性 LLM 补全（经绑定的 default-role dispatcher）。需要单次 LLM 调用（而非完整 ReAct 循环）时使用，返回 litellm ``ModelResponse``。 |
| ``await self.run_lifecycle_hooks(hook_type, *, tick, t)`` | 对当前激活的 skill 跑 ``pre_step`` / ``post_step`` 生命周期 hook，返回 hook 摘要列表。 |
| ``self.discover_skill_sources(env)`` | 扫描 custom 与 env 提供的 skill 源，刷新 visible skill 集合并应用 default activated。返回 ``{源标签: [skill_id]}``。 |
| ``self.persist_agent_json(*, tick=None, t=None)`` | 把 ``build_agent_json`` 的结果写入 ``AGENT.json``，返回写入的 dict。 |
| ``self.trace_span(name, *, trace_id=None, parent_span_id=None, attributes=None, end_attributes=None)`` | agent 级 trace span 上下文管理器（``with self.trace_span(...) as span:``）。 |
| ``self.workspace_root_path()`` | 返回 agent workspace 根路径（未初始化时抛 ``RuntimeError``）。 |
| ``self.dispatch_todo_tool(action, args)`` | 分发内置 TODO 工具（``todo_list`` / ``todo_add`` / ``todo_update`` / ``todo_start`` / ``todo_complete`` / ``todo_defer`` / ``todo_clear_completed``）。 |
| ``await self.ask_env(ctx, message, readonly, template_mode=False, trace_id=None, parent_span_id=None)`` | 向环境 router 发请求，返回 ``(ctx, answer)``。 |
| ``self.get_profile()`` | 返回 profile dict（自动处理 dict / pydantic model / 其他）。 |
| ``self.skill_runtime`` （属性） | 当前的 ``AgentSkillRuntime`` 实例。 |
| ``self.id`` / ``self.name`` / ``self.logger`` （属性） | agent id、显示名、agent-scoped logger。 |
| ``self.env_ask_env_ctx_overlay()`` | 返回稳定的 identity overlay（``id`` / ``agent_id`` / ``person_id``），用于 ``ask_env`` context。 |
| ``await self.close()`` | 释放资源（基类默认 no-op，子类可覆盖）。 |
| ``self.description()`` / ``self.init_description()`` （classmethod） | 注册表说明 / AI 可读初始化指引，子类覆盖以提供业务说明。 |

---

## 5. 服务注入

``from_workspace`` 在内部调用 ``_bind_services(service_proxy)``，把共享
service 容器注入到 agent slot：

| slot | 来源 | 用途 |
| --- | --- | --- |
| ``self._service_proxy`` | ``service_proxy`` 参数 | 原始容器（env / llm / trace / replay）。 |
| ``self._env`` | ``service_proxy.env`` | 环境 router（``RouterBase``）。 |
| ``self._dispatcher`` | ``service_proxy.llm.default`` | 默认 LLM dispatcher（``call(...)``）。 |
| ``self._model_name`` | ``dispatcher.model_name`` | 默认 LLM 模型名。 |

子类通过 ``self._env`` / ``self._dispatcher`` / ``self.skill_runtime``
使用这些服务。``_bind_services`` 本身是内部 helper（下划线，不应直接调用）。

---

## 6. 内部实现（下划线前缀，子类 **不应** 依赖）

以下为基类内部实现，**接口可能变动**，子类不要直接调用：

- 服务 / workspace 绑定：``_bind_services``、``_bind_workspace``、
  ``_maybe_proxy_sharded_writer``、``_derive_name``。
- skill runtime 装配：``_setup_skill_runtime``、``_refresh_visible_skills``、
  ``_resolve_skill_id_from_args``。
- ReAct 内部：``_execute_react_tool``（trace 包裹的工具执行）、
  ``_call_react_llm_with_messages``（原地扩展 thread）、``_append_react_turn``、
  ``_complete_react_once``、``_parse_react_turn``、``_parse_react_responses``
  （``_parse_react_turn`` 的薄委托）、``_append_context_refresh``。
- workspace 路径 helper：``_workspace``（property）、
  ``_is_core_owned_workspace_path``、``_normalize_workspace_read_path``、
  ``_build_env_tool_context``、``_build_env_skill_instruction``。
- trace 低层：``_trace``（property）、``_current_trace_span``、
  ``_start_trace_span``、``_end_trace_span``。
- TODO 内部：``_todo_store``、``_ensure_todo_state``、
  ``_build_todo_context``、``_current_simulation_time``、
  ``_normalize_todo_due_value``、``_normalize_todo_tool_args``。

> 经验法则：``_`` 前缀 = 内部实现，可能变动；无 ``_`` 前缀 = 公开 API，
> 子类可放心依赖。

---

## 7. 最小子类示例

下面是一个极简的 ``AgentBase`` 子类：实现三个 abstract 方法，并覆盖
``restore`` 与 ``build_react_messages`` 以接入自定义状态与 ReAct 提示词。

```python
"""最小 AgentBase 子类示例（中文注释）。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from agentsociety2.agent.base import AgentBase


class MinimalAgent(AgentBase):
    """最小子类：自定义状态 + 复用基类 ReAct 循环。"""

    # ---- restore 覆盖：在基类恢复之后追加业务状态 ----
    async def restore(
        self,
        workspace_path: Path,
        service_proxy: Any,
    ) -> None:
        # 1) 先让基类恢复 workspace / skill runtime / 服务 / 计数器
        await super().restore(workspace_path, service_proxy)
        # 2) 再追加业务专属状态（这里只设一个简单计数器）
        self._custom_counter: int = 0

    # ---- build_react_messages 覆盖：提供 ReAct 提示词 ----
    # 复用基类的 run_react_loop 就必须实现这个钩子。
    def build_react_messages(
        self,
        *,
        tick: int,
        t: datetime,
        observations: list[dict[str, Any]],
        question: str | None = None,
        readonly: bool = False,
        skill_hooks: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, str]]:
        system = (
            f"You are agent {self.name} (id={self.id}). "
            f"Current tick={tick}, time={t.isoformat()}."
        )
        # 把最近的 observation 拼进 user 消息
        obs_text = "\n".join(
            f"- [{o.get('action')}] {o.get('observation')}" for o in observations
        )
        user = question or f"Observations:\n{obs_text}\nDecide next action."
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    # ---- to_workspace：把动态状态写回 AGENT.json ----
    async def to_workspace(self, workspace_path: Path) -> None:
        # 直接复用基类的 persist_agent_json（它会调 build_agent_json）
        self.persist_agent_json(tick=None, t=self._current_time)

    # ---- ask：复用基类 ReAct 循环回答外部问题 ----
    async def ask(
        self,
        message: str,
        readonly: bool = True,
        *,
        t: datetime | None = None,
    ) -> str:
        now = t or self._current_time or datetime.now()
        # run_react_loop 是基类提供的通用编排
        return await self.run_react_loop(
            tick=0,
            t=now,
            observations=[],
            question=message,
            readonly=readonly,
        )

    # ---- step：每 tick 跑一次 ReAct 循环 ----
    async def step(self, tick: int, t: datetime) -> str:
        self._step_count += 1
        self._current_time = t
        # 跑 pre_step hook、构造 observation、跑 react loop、跑 post_step hook
        # 这里只演示最小路径：直接调 run_react_loop。
        return await self.run_react_loop(tick=tick, t=t)
```

要点回顾：

1. **不要** 重写 ``__init__``；状态在 ``restore`` 里设。
2. ``restore`` 永远先 ``await super().restore(...)``，再追加业务状态。
3. 复用 ``run_react_loop`` 就必须覆盖 ``build_react_messages``。
4. ``persist_agent_json`` / ``trace_span`` / ``run_lifecycle_hooks`` /
   ``discover_skill_sources`` / ``skill_runtime`` 都是公开 API，直接用。
5. 需要扩展 ``AGENT.json`` 字段就覆盖 ``build_agent_json``（先调 super）；
   需要加工具前缀就覆盖 ``dispatch_react_tool``（未命中转 super）。

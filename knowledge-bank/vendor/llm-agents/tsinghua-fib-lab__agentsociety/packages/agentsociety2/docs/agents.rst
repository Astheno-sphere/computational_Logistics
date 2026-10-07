使用智能体
===================

LLM 智能体模拟为计算社会科学提供了一种新的研究范式：研究者可以把个体、群体、制度与环境机制放入可运行的模拟系统中，观察微观行为如何汇聚为宏观社会现象。它让许多过去只能停留在理论讨论或小规模问卷中的问题，变成可以迭代、对照和复盘的实验对象。

但这种范式的实际使用仍然有较高技术门槛。一个完整实验通常要求研究者把高层次的社会科学想法转化为可执行代码：定义 agent 画像、行为逻辑、环境工具、实验步骤、运行配置和分析产物。AgentSociety 2 中的 **AI Social Scientist** 试图在研究想法与可执行仿真之间提供一个交互式编排层，让研究者更多关注研究问题、理论机制和实验逻辑，系统辅助完成实验结构化、配置生成、运行管理和结果分析。

``PersonAgent`` 就是这个流程中面向“人”的默认智能体抽象：它把人物画像、行为能力、工作记忆和环境互动组织成可检查、可替换、可复盘的运行单元。本部分先从研究者如何理解 ``PersonAgent`` 开始，再介绍需要调参、扩展或调试时会用到的工程细节。

.. note::

   本页描述的是 **Ray 重构后** 的智能体架构（``AgentBase`` 直接拥有 workspace / 技能运行时 /
   ReAct 循环 / TODO / trace；智能体作为 workspace 绑定的无状态 record，由 Ray Task 流式驱动）。
   系统级执行模型、``ServiceProxy`` 与 trace 见 :doc:`architecture`；技能子系统见
   :doc:`agent_skills`。


类继承层次
-----------

当前智能体体系的类继承关系：

.. code-block:: text

   AgentBase (ABC)          # agent/base/agent.py — 所有智能体的基类
     └── PersonAgent        # agent/person.py — 面向人物仿真的默认智能体（薄编排器）

* ``AgentBase`` **直接拥有** 所有通用能力：workspace 绑定、技能运行时（``AgentSkillRuntime``）、
  ReAct 工具循环、LLM 调用、TODO 状态、trace、``AGENT.json`` 持久化。它**没有 mixin、没有多继承**。
* ``PersonAgent`` 只实现面向人物的逻辑（memory、person prompt、daily-guidance 等行为），其余全部继承自基类。
* ``contrib/agent/`` 下提供若干实验性 Agent（如博弈论场景），核心框架只依赖 ``AgentBase`` 和 ``PersonAgent``。


构造模型（workspace 绑定的无状态 record）
--------------------------------------------

智能体通过 workspace 入口构造。``AgentBase`` 提供两个类方法入口 + 一个无参
``__init__``：

.. list-table::
   :widths: 32 68
   :header-rows: 1

   * - 入口
     - 说明
   * - ``AgentBase.create(workspace_path, profile, config)``
     - **静态写一次**：把 ``config.json`` + 初始 ``AGENT.json`` + 标准空目录写入 workspace。**不返回** agent 实例。
   * - ``await AgentBase.from_workspace(workspace_path, service_proxy)``
     - 重建 ready agent：``agent = cls()``（无参）→ ``await agent.restore(ws, proxy)`` → 返回。
   * - ``AgentBase.__init__(self)``
     - 无参。只设置空 slot，不做任何 profile 解析、不要求 id。真正初始化发生在 ``restore()``。

跨 tick 的动态状态全部落在 workspace；``step()`` 每次都从 workspace 重建上下文，因此 agent 本身是
**无状态的 record**，可以被 Ray Task 当作数据流式调度到任意 worker（见 :doc:`architecture`）。

绝大多数研究者并不直接调 ``create`` / ``from_workspace``，而是通过 ``AgentSociety`` + ``InitConfig``
声明 agent，由编排器在实验启动时批量创建（见下方 :ref:`agent-config` 与 :doc:`cli`）。下面仅展示
底层契约，便于理解与扩展：

.. code-block:: python

   from pathlib import Path
   from agentsociety2 import PersonAgent
   from agentsociety2.agent.service_proxy import ServiceProxy

   workspace = Path("run/agents/agent_0001")

   # 1) 写一次 workspace（config.json + 初始 AGENT.json）
   PersonAgent.create(
       workspace,
       profile={"name": "Alice", "age": 28, "bio": "A software engineer."},
       config={},
   )

   # 2) 重建 ready agent（需要 ServiceProxy 注入 env/llm/trace/replay）
   agent = await PersonAgent.from_workspace(workspace, service_proxy)


服务注入：ServiceProxy
-----------------------

``from_workspace`` 内部调用 ``_bind_services(service_proxy)``，把一个共享服务容器注入 agent：

.. list-table::
   :widths: 28 72
   :header-rows: 1

   * - slot
     - 来源 / 用途
   * - ``self._service_proxy``
     - 原始容器，持有 ``env`` / ``llm`` / ``trace`` / ``replay`` 句柄。
   * - ``self._env``
     - 环境 router（``RouterBase``），经 ``ask_env`` 访问。
   * - ``self._dispatcher``
     - 默认 LLM dispatcher（``service_proxy.llm.default``）。
   * - ``self._model_name``
     - 默认 LLM 模型名。

``ServiceProxy`` 把 env / LLM clients / trace / replay 收口为单一对象，是 Ray Task 并行执行的关键。
LLM client 只携带连接参数，worker 在本地事件循环中按需创建 litellm Router。


ReAct 工具循环
----------------

``PersonAgent.step()`` / ``ask()`` 的核心是基类提供的 ``run_react_loop``：每轮让模型提交一个结构化
工具决策，运行时校验、执行并把结果写回上下文，循环直至 ``finish`` 或回合上限。这把 LLM 的自由生成
限制在可审计的工具结果里，也方便 replay 复盘。

基类 ``dispatch_react_tool`` 处理以下工具（``PersonAgent`` 在此之上按需追加 ``memory_*`` 等前缀）：

.. list-table::
   :widths: 26 74
   :header-rows: 1

   * - 工具
     - 说明
   * - ``read`` / ``write`` / ``append`` / ``list`` / ``grep``
     - 读写 agent 工作区文件（带越界保护）。
   * - ``activate_skill`` / ``deactivate_skill``
     - 把某 skill 的 ``SKILL.md`` 注入 / 移出上下文。
   * - ``read_skill_file``
     - 读取 skill 目录内文件（渐进式披露）。
   * - ``execute_skill_script``
     - 执行 skill 脚本（默认进程内 ``entrypoint``，见 :doc:`agent_skills`）。
   * - ``ask_env``
     - 向环境 router 发请求（查询或修改环境），返回 ``(ctx, answer)`` 二元组。
   * - ``finish``
     - 结束当前仿真步（可附 summary）。

模型每轮的输出被解析为一个结构化决策（工具名 + 参数 + 是否结束）。无效工具名会被纠正或返回可恢复错误，
不会直接崩溃。

一次 ``run_react_loop`` 只构建**一个** thread：首条消息由 ``build_react_messages`` 产出（system +
含各上下文档的 user），之后每轮的 assistant 工具调用与其结果**追加**到末尾，不再重建。这样每个请求
都是上一个的严格前缀扩展，provider 的 prompt 前缀缓存能随轮次增长而不是每轮归零（实测聚合命中率
从约 52% 提升到约 85%）。因此**不要**在轮内重建或从头部截断 thread —— 两者都会摧毁缓存前缀。
工具结果以 ``role: "tool"`` 消息返回（失败时带 ``ERROR:`` 前缀）；模型若以文本而非原生 tool call
发起调用，结果则作为 ``<recent_observations>`` user 块追加。步内改动了
``<todo_context>`` / 激活 skill 时，会追加一条刷新块而不是重渲染（见
``AgentBase.build_context_refresh_message``）。工具结果同时写入磁盘 JSONL 供 replay 复盘。

.. note::

   agent 层**没有** ``bash`` / ``glob`` / ``codegen`` / ``batch`` 这类工具。环境交互统一走
   ``ask_env``，由环境侧的 router（如 ``CodeGenRouter``）决定如何调用环境模块工具（见 :doc:`env_modules`）。


TODO 状态
~~~~~~~~~

基类内置一组 TODO 工具（``todo_list`` / ``todo_add`` / ``todo_update`` / ``todo_start`` /
``todo_complete`` / ``todo_defer`` / ``todo_clear_completed``），让 agent 可以显式维护待办清单。
TODO 条目用 UUID 标识，自动归档，可通过 ``dispatch_todo_tool`` 分发；目的是让多步计划在跨 tick 之间
可追踪、可恢复。


工作区布局
~~~~~~~~~~

每个 agent 拥有独立工作区，是它的唯一持久状态来源：

.. code-block:: text

   <run_dir>/agents/agent_XXXX/
   ├── config.json            # 静态配置（create 时写一次，不再重写）
   ├── AGENT.json             # 动态自描述快照（每步 to_workspace 时更新）
   ├── state/                 # 状态文件
   │   ├── emotion.json
   │   ├── intention.json
   │   ├── needs.json
   │   └── plan_state.json
   ├── AGENT_MEMORY.md        # 跨 step 运行时记忆摘要
   ├── custom/skills/         # 自定义技能目录（热加载）
   └── .runtime/logs/
       ├── session_state.json
       ├── thread_messages.jsonl
       ├── tool_calls.jsonl
       └── step_replay.jsonl

``config.json`` 是静态的；``AGENT.json`` 由 ``persist_agent_json``（调 ``build_agent_json``）在
``to_workspace`` 时写回，是 agent 对自己的自描述快照（含 ``world_description`` 等字段，供 Ray
重建时从磁盘恢复；注入 prompt 的 ``<agent>`` 视图会剥离该字段以免与 ``<world>`` 重复）。
线程与工具日志位于 ``.runtime/logs/``。跨 step 的运行时摘要见 ``AGENT_MEMORY.md``。


.. _agent-config:

智能体配置（AgentConfig）
-------------------------

实验级的智能体配置由 ``AgentConfig`` 描述（:mod:`agentsociety2.society.models`），字段精简：

.. list-table::
   :widths: 25 75
   :header-rows: 1

   * - 字段
     - 说明
   * - ``agent_id`` (int)
     - 智能体唯一标识符。
   * - ``agent_type`` (str)
     - 智能体类型（注册表中的类名，如 ``PersonAgent``）。
   * - ``kwargs`` (dict)
     - 传给该 agent 的所有初始化参数，包含 ``profile`` 等。

它出现在 ``InitConfig.agents`` 列表里，由 CLI 的 ``--config`` JSON 提供。模型 / LLM 的选择走全局
``config``，见 :doc:`installation` 的环境变量与 :doc:`api/config`。

与智能体交互
-----------------------

``ask()`` 方法
~~~~~~~~~~~~~~~~~

.. code-block:: python

   response = await agent.ask(
       "What's your opinion on renewable energy?",
       readonly=True,   # 仅查询，无副作用
   )

``readonly`` 控制智能体是否可以修改环境：``True`` 只查询；``False`` 可能调用修改状态的环境工具。
``ask`` 走 ReAct 循环，但只暴露只读工具子集。

``step()`` 方法
~~~~~~~~~~~~~~~~~

``AgentSociety`` 在仿真期间自动调用（``tick`` 为本步时间跨度秒，``t`` 为本步结束时的仿真时间）：

.. code-block:: python

   action_description = await agent.step(tick=3600, t=datetime.now())

在编排器层面，``AgentSociety.step(tick)`` / ``run(num_steps, tick)`` 会驱动所有 agent 的 ``step``，
并支持以 Ray Task 批式并行（见 :doc:`architecture`）。外部问答/干预则经 ``AgentSociety.ask(question)``
与 ``AgentSociety.intervene(instruction)``。

自定义智能体
~~~~~~~~~~~~~

.. note::

   扩展 ``PersonAgent`` 的认知能力，优先使用 Agent Skills（见 :doc:`agent_skills`）。
   只有需要完全不同的智能体架构时，才创建自定义智能体类。

要创建自定义智能体，继承 ``AgentBase`` 并实现抽象方法，覆盖 ``restore`` 追加业务状态。不要重写
``__init__``；状态在 ``restore`` 里设。

AgentBase 抽象 / 推荐覆盖的方法
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 40 60
   :header-rows: 1

   * - 方法
     - 说明
   * - ``ask(self, message, readonly=True, *, t=None)``
     - **必须实现**。通过 agent 的推理流程回答外部问题。
   * - ``step(self, tick, t)``
     - **必须实现**。执行一个仿真步。
   * - ``to_workspace(self, workspace_path)``
     - **必须实现**。把当前动态状态写回 workspace。
   * - ``restore(self, workspace_path, service_proxy)``
     - 推荐覆盖：在 ``await super().restore(...)`` 之后追加业务状态恢复。
   * - ``build_react_messages(...)``
     - 复用基类 ``run_react_loop`` 时**必须覆盖**：构造 ReAct 提示词（chat messages）。
   * - ``build_agent_json(*, tick, t)``
     - 推荐覆盖：扩展 ``AGENT.json`` 字段（先 ``data = super().build_agent_json(...)`` 再追加）。
   * - ``dispatch_react_tool(action, args, *, readonly=False)``
     - 推荐覆盖：增加工具前缀（如 ``memory_*`` / ``todo_*``），未命中转发给 ``super()``。

最小子类示例：

.. code-block:: python

   from datetime import datetime
   from pathlib import Path
   from typing import Any

   from agentsociety2.agent.base import AgentBase


   class MinimalAgent(AgentBase):
       """最小子类：自定义状态 + 复用基类 ReAct 循环。"""

       async def restore(self, workspace_path: Path, service_proxy: Any) -> None:
           await super().restore(workspace_path, service_proxy)  # 先恢复 workspace / 服务 / 技能
           self._custom_counter: int = 0                          # 再追加业务状态

       def build_react_messages(self, *, tick, t, observations, question=None,
                                readonly=False, skill_hooks=None):
           system = f"You are agent {self.name} (id={self.id}). tick={tick}, t={t.isoformat()}."
           user = question or "Decide next action."
           return [{"role": "system", "content": system},
                   {"role": "user", "content": user}]

       async def to_workspace(self, workspace_path: Path) -> None:
           self.persist_agent_json(tick=None, t=self._current_time)

       async def ask(self, message: str, readonly: bool = True, *, t=None) -> str:
           return await self.run_react_loop(tick=0, t=t, observations=[], question=message, readonly=readonly)

       async def step(self, tick: int, t: datetime) -> str:
           return await self.run_react_loop(tick=tick, t=t)

子类可直接调用的基类公开 API 还包括：``run_react_loop``、``acompletion``、``run_lifecycle_hooks``、
``discover_skill_sources``、``persist_agent_json``、``trace_span``、``ask_env``、``get_profile``、
``skill_runtime``，以及 ``self.id`` / ``self.name`` / ``self.logger`` 等属性。完整清单见
:doc:`/api/agent` 与源码 ``agent/base/README.md``。


智能体记忆
------------

``PersonAgent`` 的记忆分几层：

1. **Thread（对话线程）**：短期上下文，维护最近工具调用与 LLM 交互，过长时压缩。
2. **AgentMemory（运行时持久化记忆）**：跨 step 的运行时摘要，位于 ``AGENT_MEMORY.md``，由 thread
   压缩与显式 handoff 更新，主要服务长线程压缩、恢复与错误连续性。
3. **Event memory**：``PersonMemoryRuntime`` 根据 step-mode ``finish`` 携带的 ``memories`` 写入
   ``memory/episodes.jsonl`` ，保存社会关系、地点、承诺、计划结果等可检索事实（是否写入由工具循环决定，
   不是每步固定）。
4. Workspace 状态文件：skill 脚本写入的 ``state/*.json``，例如情绪、意图、计划等。

``MEMORY.md`` 与 ``memory/episodes.jsonl`` 不是一回事：前者是压缩后的长期背景摘要，后者是 append-only
事件流。要替换/扩展记忆策略，优先扩展 ``PersonMemoryRuntime`` 或相关工具边界，而不是恢复旧的
``memory`` 内置 skill。


参考
------

* :doc:`agent_skills` - Agent Skills 子系统（发现、entrypoint 执行、生命周期 hook）
* :doc:`architecture` - Ray 执行模型、``ServiceProxy``、trace、路由器
* :doc:`api/agent` - ``AgentBase`` / ``PersonAgent`` API 参考
* 源码 ``agentsociety2/agent/base/README.md`` - AgentBase 子类开发指南（最权威）

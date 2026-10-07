架构与可扩展性
======================

本页介绍 AgentSociety 2 的运行时架构，以及它如何在较大规模的仿真中组织智能体、环境、LLM 调用、
trace 和 replay 存储。

AgentSociety 2 将智能体状态放在独立 workspace 中，执行时再由 Ray Task 按批重建和推进智能体。
环境路由、LLM 调度、trace、replay 等运行时组件作为共享服务存在，通过 ``ServiceProxy`` 注入到每个
智能体。这样做的目标是让智能体数量可以随实验规模增长，而不是为每个智能体长期保留一个进程或 actor。


执行模型
-----------------------------------

每个 ``AgentBase`` 子类的持久状态都保存在自己的 workspace 中，包括 ``config.json``、``AGENT.json``、
``state/*`` 和 ``.runtime/logs/*``。智能体对象只是在一次任务执行期间从这些文件重建出来的运行时对象；
一次 ``step()`` 结束后，新的状态会写回 workspace。

这一模型对应 :doc:`agents` 中的 ``create`` / ``from_workspace`` / ``to_workspace`` 契约。对调度器来说，
一个智能体可以表示为轻量的执行说明：workspace 路径、智能体类型、智能体 id，以及共享的
``ServiceProxy`` 句柄。Ray worker 收到任务后在本地调用 ``from_workspace``，运行 ``step``，再调用
``to_workspace`` 持久化结果。智能体对象本身不会在 Ray object store 中来回传递。

环境模块使用一套对称的持久化契约：``EnvBase.to_workspace()`` 负责写出动态状态，
``restore()`` 负责恢复。每个模块可以选择自己的状态格式，通常把文件放在
``<workspace_root>/state/ENV_STATE.json``。路由会在每步结束时调用 ``to_workspaces()``；
使用 ``--resume`` 时，actor 的 ``init()`` 会通过 ``from_workspaces()`` 重建各模块。恢复发生在
模块 ``init()`` 之后，因此 checkpoint 中的状态会覆盖初始化时的重置。``AgentSociety`` 自身的状态
写入 ``SOCIETY.json`` 和 ``SOCIETY_STEP.json``。详见 :doc:`env_modules` 与 :doc:`cli` 的
resume 说明。

``AgentSociety`` 在每个 tick 中执行以下流程：

1. 将智能体 id 切成若干批。
2. 为每一批提交一个 ``step_agent_batch`` Ray Task。
3. 每个 task 在批内用 ``asyncio.gather`` 并发推进智能体；批之间由 Ray 调度到不同 worker。
4. 所有批次完成后，调用环境的 ``step``，再推进仿真时钟。

默认批大小为 ``AGENTSOCIETY_BATCH_SIZE=256``（CLI ``--batch-size`` 可覆盖）。每 tick 的
Ray Task 数 = ⌈N / 批大小⌉，受 ``AGENTSOCIETY_LLM_RAY_MAX_WORKERS``（默认机器 CPU 核数）封顶；
单个 task 内的并发 fan-out 由批大小决定，每进程的 LLM 并发则由本地 ``LLMClient`` 的 AIMD
自适应控制（无人工上下限）。

.. graphviz::

   digraph exec_model {
       rankdir=LR;
       node [shape=box, style=rounded];

       Driver [label="AgentSociety (driver)"];
       Batch [label="step_agent_batch\nRay Task × 批", shape=note];
       Agent [label="agent.from_workspace()\n无状态重建 + step"];
       WS [label="workspace\n(磁盘状态)", shape=cylinder];

       Services [label="共享服务\nenv / llm / trace / replay", style=filled, color=lightyellow];

       Driver -> Batch [label="切批提交"];
       Batch -> Agent;
       Agent -> WS [label="读写状态"];
       Agent -> Services [label="经 ServiceProxy"];
   }


ServiceProxy
----------------------------

智能体不直接创建或持有 LLM dispatcher、环境 router、trace actor 或 replay actor。``from_workspace``
接收一个 ``ServiceProxy``，并在 ``_bind_services(service_proxy)`` 中把相关句柄绑定到智能体实例。

.. list-table::
   :widths: 22 36 42
   :header-rows: 1

   * - slot
     - 来源
     - 用途
   * - ``_service_proxy``
     - 入参
     - 原始服务容器，包含 env / llm / trace / replay 句柄。
   * - ``_env``
     - ``service_proxy.env``
     - 环境 router（``RouterBase`` / ``EnvRouterProxy``）。
   * - ``_dispatcher``
     - ``service_proxy.llm.default``
     - 默认 LLM dispatcher（``call(...)``）。
   * - ``_trace``
     - ``service_proxy.trace``
     - trace writer 句柄（通常是 ``TraceProxy``）。

``ServiceProxy`` 只保存可序列化的句柄和配置，不保存锁、连接池或后台线程。Ray Task 因此只需要接收
一个服务容器；环境 router、trace 与 replay 由 driver 或 CLI 统一创建，LLM client 只携带连接参数，
worker 在自己的事件循环中按需创建 litellm Router 和并发控制器。

环境路由
---------------------------

环境状态由环境路由统一管理。生产运行时，CLI 会通过 ``get_env_router_actor_class`` 创建专用的 Ray
actor，并把 ``EnvRouterProxy`` 放入 ``ServiceProxy``。智能体通过该 proxy 调用 ``ask``、
``step``、``init`` 和 ``get_world_description`` 等接口；所有智能体看到的是同一份环境状态。

actor 的 ``max_concurrency`` 取决于挂载模块是否全部声明 ``is_concurrency_safe()``：全部安全时使用
``AGENTSOCIETY_ENV_ACTOR_MAX_CONCURRENCY``（默认 8），否则为 ``1``。详见 :doc:`env_modules`。

路由器（``RouterBase`` 子类）负责把智能体的自然语言请求映射到环境模块暴露的 ``@tool`` 方法：

.. list-table::
   :widths: 30 70
   :header-rows: 1

   * - 路由器
     - 特点
   * - ``CodeGenRouter`` (默认)
     - 从环境模块提取工具签名，生成调用代码并在受限环境中执行；AST 守卫；
       **仅** ``template_mode=True`` 时启用 FAISS 指令模板缓存；无 observe/statistics
       工具时 init 不跑空桩 LLM 代码生成。
   * - ``ReActRouter``
     - ReAct 式工具选择。
   * - ``PlanExecuteRouter``
     - 先规划再执行。
   * - ``TwoTierReActRouter`` / ``TwoTierPlanExecuteRouter``
     - 两级路由，适合大工具集。
   * - ``SearchToolRouter``
     - 以搜索/检索方式选择工具。

环境模块与 ``@tool`` 装饰器见 :doc:`env_modules` 与 :doc:`concepts`。

LLM 调度
--------------------

LLM 调用由 :mod:`agentsociety2.config.llm_dispatcher` 统一封装。当前实现使用 per-process
dispatcher：``LLMClient`` 是可序列化的连接配置，只携带 ``model_name``、``base_url`` 和
``api_key``；它可以随 ``ServiceProxy`` 进入 Ray Task 或 env router actor。
每个消费者在自己的事件循环中第一次调用 ``call()`` 时，本地创建 litellm ``Router`` 与
``AdaptiveSemaphore``。这样可以避免跨 Ray task 复用 asyncio 对象导致的 event-loop 绑定问题。

并发控制发生在每个进程 / 事件循环内部：``AdaptiveSemaphore`` 根据近期延迟和 rate-limit 错误做
AIMD（加性增、乘性减）调整，用于控制该进程内 LLM 请求 fan-out。token usage 也按
``LLMClient`` 实例本地累计，再通过 Ray Task 返回值合并。

默认配置可直接使用；需要调参时主要关注以下环境变量（详见 :doc:`installation`）：

.. list-table::
   :widths: 42 18 40
   :header-rows: 1

   * - 环境变量
     - 默认
     - 含义
   * - ``AGENTSOCIETY_LLM_RAY_MAX_WORKERS``
     - 机器 CPU 核数
     - ``ray.init(num_cpus=...)`` 的 CPU 预算，封顶每 tick 同时运行的 ``step_agent_batch`` Ray Task 数。
   * - ``AGENTSOCIETY_LLM_RAY_CONCURRENCY``
     - 16
     - 每个本地 ``LLMClient`` 的 AIMD 初始并发；无人工上下限，自动逼近 API 真实容量。
   * - ``AGENTSOCIETY_BATCH_SIZE``
     - 256
     - 每个 ``step_agent_batch`` Ray Task 处理的 agent 数；CLI ``--batch-size`` 可覆盖。
   * - ``AGENTSOCIETY_LLM_LATENCY_DEGRADE_FACTOR``
     - 4.0
     - AIMD 的相对退避因子。调用延迟明显高于近期健康基线时触发降并发。
   * - ``AGENTSOCIETY_LLM_SLOW_LATENCY_MS``
     - 未设置
     - 可选的绝对延迟阈值（毫秒）。未设置时只使用相对因子。
   * - ``AGENTSOCIETY_LLM_THINKING``
     - 未设置
     - 推理（thinking）总开关，``on`` / ``off``。**未设置时不发送任何新参数**。仅适用于 OpenAI 兼容 chat-completions 接口。
   * - ``AGENTSOCIETY_LLM_REASONING_EFFORT``
     - 未设置
     - 显式 ``reasoning_effort``。``off`` 时缺省回退 ``minimal``；``on`` 时仅在显式设置后发送。
   * - ``AGENTSOCIETY_LLM_EXTRA_BODY``
     - 未设置
     - JSON 对象字符串，合并进请求的 ``extra_body``，用于网关私有开关（如 ``{"enable_thinking": false}``）。配了它时 ``off`` 只发 ``extra_body``、不发 ``reasoning_effort``。
   * - ``AGENTSOCIETY_CODER_LLM_THINKING`` / ``_REASONING_EFFORT`` / ``_EXTRA_BODY``
     - 回退默认组
     - 上述三项的 coder 角色（env router 代码生成）覆盖。

``init_dispatchers()`` 只负责初始化 Ray（用于 env router actor 和 agent Ray Tasks）。
``shutdown_dispatchers()`` 对 LLM 侧是 no-op；本地 Router 随所在进程退出释放。

Trace
-----------

:mod:`agentsociety2.trace` 提供分布式追踪：

* ``ShardedTraceWriter`` 按 ``trace_id`` 分片写入，并通过后台线程批量落盘。
* ``JsonlTraceWriter`` 提供 ``start_span``、``trace_span``、``record_event``、``end_span`` 和
  ``TraceSpan``。
* ``TraceActor`` 是常驻 Ray actor；``TraceProxy`` 是放入 ``ServiceProxy`` 的轻量句柄。

智能体执行、memory、环境调用和 LLM 调用都可以记录为 span。运行完成后，trace 数据可用于分析慢调用、
长尾任务和环境工具调用瓶颈。

Replay 与存储
--------------------------

Replay 数据由 ``ReplaySink`` / ``ReplayWriter`` 以 append-only JSONL 写入
``run/replay/``，dataset catalog 和列元数据保存在 ``_schema.json``。``ReplayProxy``
只携带 replay 目录和启用标志；env router、society 和 agent task 各自在本进程内创建
``ReplaySink`` 并并发 append，不再经过中心 SQLite actor。读取侧由
``ReplayReader`` 使用 DuckDB 将 JSONL shard 注册为 view，表结构与数据集注册机制见
:doc:`storage`。


扩展点
--------

AgentSociety 2 的主要扩展点包括：

* 新增智能体能力：编写 Agent Skill，放入 ``custom/skills/``，见 :doc:`agent_skills`。
* 新增环境模块：继承 ``EnvBase`` 并用 ``@tool`` 暴露可调用方法，见 :doc:`env_modules`。
* 自定义智能体类型：继承 ``AgentBase`` 并通过注册表发现，见 :doc:`agents`。
* 分析运行结果：读取 trace span 或 replay dataset，见 :doc:`storage`。


参考
------

* :doc:`agents`：智能体构造模型、workspace 布局与 ReAct 工具循环。
* :doc:`agent_skills`：Agent Skill 的目录结构、加载与执行方式。
* :doc:`env_modules`：环境模块与 ``@tool`` 装饰器。
* :doc:`storage`：replay 数据集、``_schema.json`` catalog、JSONL 写入与 DuckDB 读取。
* :doc:`api/env` / :doc:`api/storage`：router、proxy、writer API。

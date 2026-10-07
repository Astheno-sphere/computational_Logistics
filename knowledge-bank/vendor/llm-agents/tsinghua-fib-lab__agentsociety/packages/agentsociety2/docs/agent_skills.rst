Agent Skills（智能体技能）
=================================

概述
------

Agent Skills 是 ``PersonAgent`` 的能力组织方式。``PersonAgent`` 是一个轻量的 ReAct 编排器，其能力
由**可插拔的 Skill 流水线**提供。它解决的问题不只是“如何写插件”，而是如何把社会科学中的行为机制拆
成可以检查的仿真环节：一个人看到了什么，如何解释这个情境，形成了什么意图，采取了什么行动，又把哪些
经历带到后续决策中。

Skill 遵循 **metadata-first、selected-only** 模型：

1. **选择阶段**：LLM 只看到 Skill 目录（``name`` + ``description``），据此决定激活哪些。
2. **执行阶段**：只有被 LLM 选中的 Skill 才会被加载、读取、执行（惰性加载）。

好处是提示词体积可控（未选中的 Skill 不进上下文），且 Skill 可独立演进、热加载。一个 Skill 是一个
自包含目录，至少含一个 ``SKILL.md``，包含 YAML frontmatter 和行为文档；可选地含
``scripts/`` 可执行脚本和 ``references/`` 参考资料。

.. note::

   本页描述的是 **Ray 重构后** 的技能子系统。旧的内置 ``observation`` / ``cognition`` / ``plan`` /
   ``memory`` 四技能已被移除；技能基础设施（registry / runtime）从 ``agent/skills/`` 下沉到
   :mod:`agentsociety2.agent.base`；Skill 脚本默认在 agent 进程内经 ``entrypoint`` 执行，而不再是
   每步 fork 子进程。当前唯一内置技能是 :ref:`daily-guidance`。最权威的工程说明见源码
   ``agentsociety2/agent/skills/README.md``。


设计目标
---------

* **按需加载**：降低每步不必要的上下文占用与执行开销。
* **可解释选择**：选择依据来自 catalog 中的简短描述，便于调试和复盘。
* **热更新友好**：支持运行时扫描、激活/停用与重载（自定义 skill 放进 ``custom/skills/`` 即被发现）。
* **文件约定解耦**：技能通过 workspace 文件交换状态，而不是互相直接调用。
* **进程内执行**：脚本默认走 ``entrypoint``，复用热解释器，毫秒级、完全并发安全。


Skill 目录结构
----------------

内置技能位于 ``agentsociety2/agent/skills/``，自定义技能位于工作区 ``custom/skills/``，环境模块技能
由环境提供。``SkillRegistry`` 按目录扫描，用 ``namespace@name`` 作为稳定 ``skill_id``。

.. code-block:: text

   # 内置技能（命名空间 built-in）
   agentsociety2/agent/skills/
   └── daily-guidance/
       ├── SKILL.md            # frontmatter（name/description/script/hooks）+ 行为说明
       ├── scripts/
       │   └── daily_guidance.py
       └── references/

   # 自定义技能（命名空间 custom，热加载）
   {workspace}/custom/skills/
   └── my-skill/
       ├── SKILL.md
       └── scripts/
           └── my_skill.py

   # 环境模块技能（命名空间 env）
   {env_module}/skills/
   └── weather-query/
       └── SKILL.md

扫描规则：每个子目录必须含 ``SKILL.md``，否则跳过；以 ``.`` 或 ``_`` 开头的目录被忽略；同名（同
``skill_id``）先到先得。agent 启动时通过 ``default_activated_skill_ids`` 配置默认激活哪些 skill。


SKILL.md 格式
--------------

每个 skill 目录必须含 ``SKILL.md``，头部用 YAML frontmatter 描述元数据：

.. code-block:: markdown

   ---
   name: daily-guidance
   description: 强制使用：凡是时间尺度在小时及以下的日常行为模拟，必须使用本 Skill ...
   script: scripts/daily_guidance.py
   hooks:
     pre_step: scripts/daily_guidance.py
   ---

   # Daily Guidance

   （激活后被注入 system prompt 的行为说明……）

frontmatter 字段：

.. list-table::
   :widths: 22 78
   :header-rows: 1

   * - 字段
     - 说明
   * - ``name``
     - 显示名，与命名空间组合成 ``skill_id``（``namespace@name``）。
   * - ``description``
     - **目录描述**——选择阶段 LLM 唯一可见的文本，决定是否激活。务必精炼、可操作。
   * - ``script``
     - 可选，默认脚本相对路径（如 ``scripts/daily_guidance.py``）。
   * - ``hooks``
     - 可选，生命周期 hook 脚本映射，键为 hook 类型（``pre_step`` / ``post_step``），值为相对脚本路径。

.. note::

   frontmatter 之后的 Markdown 正文，是 skill 被 **激活后** 注入 system prompt 的行为说明。未激活时
   不进上下文。激活时支持 ``$ARGUMENTS`` / ``$1`` / ``$2`` 占位符替换与 ``!cmd`` 命令输出注入。


可见性与激活
-------------

* **可见（visible）**：skill 出现在目录里，LLM 能看到、能选择激活。
* **激活（activated）**：skill 的 ``SKILL.md`` 正文被注入 system prompt，其脚本 / hook 可被调用。

LLM 通过下列工具操作 skill：

.. list-table::
   :widths: 26 74
   :header-rows: 1

   * - 工具
     - 作用
   * - ``activate_skill``
     - 加载某 skill 的 ``SKILL.md`` 进上下文。
   * - ``deactivate_skill``
     - 从上下文移除某 skill。
   * - ``read_skill_file``
     - 读取 skill 内文件（渐进式披露）。
   * - ``execute_skill_script``
     - 执行 skill 脚本。

ReAct 主循环每个 ``step()`` 开始前会刷新可见 skill 集合；``ask`` 模式（外部问答）下只暴露只读工具子集。


脚本执行模型（进程内 entrypoint）⭐
--------------------------------------

这是当前实现的**核心**。历史上 skill 脚本以子进程方式执行（``python script.py <argv>``），每个 agent
每步都 fork 一个新解释器，冷启动开销巨大。改版后 skill 脚本默认**在 agent 进程内执行**，分三档优先级：

.. code-block:: text

   ① entrypoint(argv, ctx)        ← 首选：缓存 import 后直接调用，毫秒级，完全并发安全
   ② 动态包装器（exec）             ← 兜底：无 entrypoint 时，以 __name__=="__main__" 就地执行
   ③ 子进程（python script.py）    ← 最后回退：模块无法 import 时

entrypoint 契约（推荐所有 skill 脚本遵循）
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Skill 脚本可在模块顶层定义一个 ``entrypoint``，runtime 会优先调用它：

.. code-block:: python

   def entrypoint(argv: list[str], ctx) -> str:
       """进程内入口。

       Args:
           argv: 命令行参数（去掉脚本名之后的部分），与子进程方式的 sys.argv[1:] 一致。
           ctx:  SkillScriptContext，携带本 agent 的运行上下文。
       Returns:
           str: 脚本原本会打印到 stdout 的文本（通常是 YAML/JSON 结果块）。
       """

要点：

* **签名兼容**：runtime 检测形参数量，``entrypoint(argv)`` 与 ``entrypoint(argv, ctx)`` 都支持，
  **强烈建议接受 ``ctx``**。
* **返回 stdout**：不要依赖 ``print`` 被 capture；直接 ``return`` 结果字符串。
* **异常即失败**：``entrypoint`` 抛异常 → 记为失败（``exit_code=1``）。不要用 ``sys.exit()``；逻辑
  失败在返回文本里写 ``ok: false``。
* **幂等加载**：runtime 按 ``(路径, mtime)`` 缓存模块，模块顶层代码只执行一次。

SkillScriptContext
~~~~~~~~~~~~~~~~~~

进程内执行时上下文通过 ``ctx`` 显式传入（定义在 ``agent/base/runtime.py``）：

.. list-table::
   :widths: 28 72
   :header-rows: 1

   * - 字段
     - 说明
   * - ``ctx.workspace_root``
     - 本 agent 的工作区根目录（子进程时代对应环境变量 ``AGENT_WORK_DIR``）。
   * - ``ctx.skill_dir``
     - 本 skill 的包根目录。
   * - ``ctx.skill_id`` / ``ctx.skill_name``
     - 注册 id（``namespace@name``）/ 显示名。
   * - ``ctx.env``
     - 子进程方式本会设置的 env 快照（dict）。

并发安全要求（重要）
~~~~~~~~~~~~~~~~~~~~

一次模拟里多个 agent 在**同一个进程**内并发跑各自的 skill 脚本。下列进程级状态是**共享**的，绝不能在
entrypoint 里直接读写，否则产生数据竞争：

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - ❌ 禁止
     - ✅ 替代方案
   * - ``os.environ["AGENT_WORK_DIR"] = ...``
     - 用 ``ctx.workspace_root``
   * - ``os.chdir(workspace)``
     - 用绝对路径（``ctx.workspace_root / ...``）
   * - ``print(...)`` 并依赖 stdout 捕获
     - 在 entrypoint 里 ``return`` 字符串
   * - 模块级可变全局当作“本次调用状态”
     - 用 ``contextvars.ContextVar`` （任务级隔离）

动态包装器
~~~~~~~~~~

无 ``entrypoint`` 的脚本由动态包装器就地执行：以 ``__name__ == "__main__"`` 在全新命名空间 ``exec``
脚本源码——语义等价子进程，但复用热解释器、无 fork。由于临时设置 ``os.environ`` / ``os.chdir`` /
捕获 stdout 这些进程级状态，动态包装器由一把全局锁 **串行** 执行。因此推荐所有热路径脚本提供
``entrypoint``，享受完全并发。

.. _daily-guidance:

内置技能：daily-guidance
-------------------------

当前唯一内置技能是 ``daily-guidance``（``built-in@daily-guidance``），面向**时间尺度在小时及以下**的
日常行为模拟。它让 agent 先形成一天的完整 Story（``state/daily_guidance/YYYY-MM-DD/story.yaml``），
再按 Story 指导每个仿真步的行为：

* **用 ``plan --json`` 提交一天的安排**：脚本校验后写入 story.yaml。
* **执行状态由时钟推导**：``completed_segments`` / ``current_segment_id`` 是 ``(segments, 当前仿真时间)``
  的函数，由脚本在读取时计算。
* **``pre_step`` hook 每步注入当前 segment**：含 ``activity`` 和 ``location_policy``，agent 据此移动与
  回答问卷。
* 内含 needs-decay 模型与 story revision 能力，用于评估和修正每日安排。

daily-mobility 等实验默认激活该 skill。它也是“进程内 entrypoint + pre_step hook 注入”的参考实现
（见 ``agent/skills/daily-guidance/scripts/daily_guidance.py``）。

旧的 ``observation`` / ``cognition`` / ``plan`` / ``memory`` 四技能已被移除；这些认知/行为能力现在通过
自定义 skill + workspace 状态文件 + ``ask_env`` 组合实现。


生命周期 Hook（pre_step / post_step）
--------------------------------------

在 ``SKILL.md`` 的 ``hooks:`` 里声明，每个仿真步自动触发：

* ``pre_step``：``agent.step()`` 开头、ReAct 循环之前运行。典型用途：根据仿真时钟推导当前状态，
  **注入到首轮上下文**。
* ``post_step``：ReAct 循环之后运行。典型用途：记录实际行为、收尾。

hook 以 ``--args-json`` 形式接收 payload（含 ``hook_type`` / ``tick`` / ``time`` / ``agent_id`` /
``step_count``）。**改版后**，``pre_step`` 的输出渲染为**专用的 ``<skill_hooks>`` XML 分块**，出现在
ReAct 首条 user 消息中——而不是被塞进通用 observation dump（那容易被 LLM 忽略）。例如：

.. code-block:: xml

   <skill_hooks>
   <skill_hook skill="built-in@daily-guidance" hook="pre_step" ok="true">
   active_segment:
     activity: sleep
     location_policy: home_aoi
   </skill_hooks>

这样 agent 不必再花一轮观察去“重新发现”状态。


环境类 Skill（``env:`` 前缀）
------------------------------

以 ``env:`` 开头的 ``skill_id`` 会被 ``execute_skill_script`` 重定向到 ``ask_env``（走环境路由
``RouterBase``），而非执行脚本。用于把“查询/操作仿真环境”包装成 skill 暴露给 LLM。这类 skill 不需要
``entrypoint``。


SkillRegistry API
-------------------

``SkillRegistry`` 是技能的发现中心（位于 :mod:`agentsociety2.agent.base.skill_registry`）。在大规模仿真下
它是共享只读单例（不再每 agent 复制）。

.. list-table::
   :widths: 38 62
   :header-rows: 1

   * - 方法
     - 说明
   * - ``scan_builtin(root=None)``
     - 扫描内置技能。
   * - ``scan_custom(skills_root, namespace="custom")``
     - 扫描自定义技能。
   * - ``scan_env(skills_dir, env_name)``
     - 扫描环境模块提供的技能。
   * - ``list_all()``
     - 返回所有 ``SkillDescriptor``。
   * - ``get(skill_id)`` / ``find_by_name(name)``
     - 按 id / 名称查询。
   * - ``read_skill_doc(skill_id)`` / ``read_skill_file(skill_id, relative_path)``
     - 读取 ``SKILL.md`` 正文 / skill 内文件。
   * - ``list_hooks(hook_type)``
     - 返回声明了某 hook 的技能。
   * - ``copy()``
     - 复制一份 registry（一般无需调用）。

``SkillDescriptor`` 是每个 skill 的元数据（``skill_id`` / ``name`` / ``description`` / ``script`` /
``hooks`` / 来源路径等）。激活、脚本执行与 hook 调度由 ``AgentSkillRuntime``（见 :doc:`/api/skills`）
负责，``AgentBase`` 持有其实例 ``self.skill_runtime``。


自定义 Skill 最小示例
----------------------

目录：

.. code-block:: text

   {workspace}/custom/skills/hello-skill/
   ├── SKILL.md
   └── scripts/
       └── hello_skill.py

``SKILL.md``：

.. code-block:: markdown

   ---
   name: hello-skill
   description: Add a short greeting into the step log when greeting is relevant
   script: scripts/hello_skill.py
   ---

   # Hello Skill

   Write a greeting to the workspace.

``scripts/hello_skill.py``（``entrypoint`` + CLI 共用派发）：

.. code-block:: python

   import contextvars
   import json
   from pathlib import Path
   from typing import Any

   _WORKSPACE_ROOT: contextvars.ContextVar[Path | None] = contextvars.ContextVar(
       "hello_workspace_root", default=None
   )

   def entrypoint(argv: list[str], ctx: Any) -> str:
       root = Path(str(getattr(ctx, "workspace_root"))).resolve()
       _WORKSPACE_ROOT.set(root)
       (root / "hello.txt").write_text("hello-skill: greeted", encoding="utf-8")
       return json.dumps({"ok": True, "summary": "greeted"}, ensure_ascii=False)

   if __name__ == "__main__":
       # 子进程回退路径仍可用
       raise SystemExit(0 if entrypoint([], type("C", (), {"workspace_root": "."})()) else 1)

放进 ``custom/skills/`` 即被热加载；激活后主 LLM 会在合适上下文选择它执行。


编写 Skill 的检查清单
-----------------------

* 内置目录放在 ``agent/skills/<name>/``；自定义目录放在工作区 ``custom/skills/<name>/``。
* 有 ``SKILL.md``：frontmatter 含 ``name``、精炼可操作的 ``description``、可选 ``script`` / ``hooks``。
* 若有脚本：提供 ``def entrypoint(argv, ctx) -> str`` 并接受 ``ctx``；工作区根取自
  ``ctx.workspace_root``；结果用 ``return`` 返回；用 ``contextvars`` 承载调用状态；CLI 派发与
  ``entrypoint`` 共用同一函数。
* 若声明 ``pre_step`` hook，输出要自包含、可直接作为 agent 指引（会被包进 ``<skill_hooks>``）。
* 参考资料放 ``references/``，``SKILL.md`` 里点名引用，按需被读取。


参考
------

* :doc:`agents` - ``PersonAgent`` 使用说明
* :doc:`architecture` - Ray 执行模型与 ``ServiceProxy``
* :doc:`api/skills` - ``SkillRegistry`` / ``AgentSkillRuntime`` API
* 源码 ``agentsociety2/agent/skills/README.md`` - 技能子系统最权威说明
* ReAct: Yao et al. (2022), https://arxiv.org/abs/2210.03629

.. toctree::
   :maxdepth: 1
   :hidden:

   skill_guide

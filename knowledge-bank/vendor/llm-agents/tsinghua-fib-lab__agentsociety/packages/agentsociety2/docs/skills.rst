研究技能
========================================

AgentSociety 2 包含一组 LLM 原生的研究技能，用于自动化科学研究工作流。

概述
------------

研究技能模块提供以下功能：

* **学术文献检索**: 通过 MCP 网关搜索和管理学术论文
* **假设生成**: 从研究问题生成可测试的假设
* **实验设计**: 设计完整的实验配置
* **论文撰写**: 通过独立 paper-toolkit 工作流完成，不再由 ``agentsociety2.skills`` 包内模块提供
* **数据分析**: 分析实验数据并生成报告

当前 Python 包内公开的 research skills 模块为
``agentsociety2.skills.literature``、``agentsociety2.skills.hypothesis``、
``agentsociety2.skills.experiment``、``agentsociety2.skills.analysis``。

Claude Code Skills
--------------------

研究工作流主要通过 Claude Code 的“skills-first”方式提供：

- AgentSociety 内置研究 skills：随 VSCode 插件打包，可在插件树视图中浏览（只读）。
- Agent(Person) 扩展 skills：由后端 `/api/v1/agent-skills/*` 管理，支持扫描/导入/热重载。

* **agentsociety-literature-search** - 学术文献检索
* **agentsociety-hypothesis** - 假设管理（add, get, list, delete）
* **agentsociety-experiment-config** - 实验配置生成与验证
* **agentsociety-run-experiment** - 实验执行与监控
* **agentsociety-analysis** - 数据分析与跨实验综合
* **agentsociety-create-agent** - 自定义 Agent 生成与校验
* **paper-toolkit** - 独立论文写作工具链入口

.. note::

   本页中的 ``.agentsociety/bin/ags.py`` 命令面向**已初始化的工作区**。
   如果当前目录尚未生成 ``.agentsociety/``，请先执行：

   .. code-block:: bash

      agentsociety-workspace init --target-dir .

   等价入口是 ``python -m agentsociety2.society.workspace init --target-dir .``。

create-agent 技能
~~~~~~~~~~~~~~~~~~~

``agentsociety-create-agent`` 用于创建或修订工作区里的自定义 Agent 类型。它不是 PersonAgent 内置认知技能，而是研究工作流中的开发辅助 skill：当实验需要一个当前不存在的 Agent class 时，通常由 ``agentsociety-experiment-config`` 分支调用。

**文件位置与扫描规则**:

- 新 Agent 模块应放在 ``custom/agents/`` 下，例如 ``custom/agents/research/lab_agent.py``。
- 扫描器会读取该目录下的 ``*.py``，但跳过路径片段包含 ``examples/`` 的文件。
- 推荐一个文件一个主要 Agent class；一个文件中存在多个 ``AgentBase`` 子类时，扫描器也能发现。

**基类选择**:

.. list-table::
   :widths: 25 75
   :header-rows: 1

   * - 基类
     - 适用场景
   * - ``AgentBase``
     - 简单实验、博弈/基准场景，开发者自行管理状态。
   * - ``PersonAgent``
     - 需要 skills-first 工具循环、workspace、checkpoint/WAL 与持久化记忆。

**本地校验**:

.. code-block:: bash

   agentsociety-workspace init --target-dir .
   PYTHON_PATH=$(grep "^PYTHON_PATH=" .env | cut -d'=' -f2)
   PYTHON_PATH=${PYTHON_PATH:-.venv/bin/python}
   $PYTHON_PATH .agentsociety/bin/ags.py create-agent --file custom/agents/my_agent.py
   $PYTHON_PATH .agentsociety/bin/ags.py create-agent --file custom/agents/my_agent.py --json

校验器会检查：目标文件为 Python 文件、至少有一个直接继承 ``AgentBase`` 或 ``PersonAgent`` 的类、``ask`` / ``step`` / ``to_workspace`` 均为 ``async def``（另需实现 ``create`` / ``from_workspace`` 工作区契约）、模块可动态导入、目标类不是 abstract class。创建完成后，在 VS Code 扩展中执行 **Scan Custom Modules** 让后端重新发现模块。


实验工作流
~~~~~~~~~~~~

研究 pipeline 的主干是：

``literature-search → hypothesis → experiment-config → run-experiment → analysis → paper-toolkit``

实验相关的两个核心 skill 是：

.. list-table::
   :widths: 30 35 35
   :header-rows: 1

   * - Skill
     - 主要输入
     - 主要输出
   * - ``agentsociety-experiment-config``
     - ``SIM_SETTINGS.json``、已有 Agent/Env/Dataset 信息
     - ``init_config.json``、``steps.yaml``、``config_params.py``
   * - ``agentsociety-run-experiment``
     - ``init_config.json`` + ``steps.yaml``
     - ``run/replay/``、日志、artifacts、``pid.json``

推荐流程：

1. 先确认工作区中已经具备 ``init_config.json``、``steps.yaml`` 与所需模块信息。
2. 在 ``experiment-config`` 阶段先扫描模块；如果缺少 Agent 或 Env，先补充对应自定义模块，再重新扫描。
3. 运行 ``experiment-config check`` 或等价校验，确认配置和步骤文件可用。
4. 启动实验时使用 ``run-experiment``；后台执行必须指定日志文件，避免丢失 verbose 输出。
5. 实验完成后检查 ``run/replay/_schema.json``、日志与 artifacts，再进入分析阶段。


分析工作流
~~~~~~~~~~~~

``agentsociety-analysis`` 面向已完成实验的数据解释、图表和报告生成。当前 replay 数据位于
``run/replay/``，可通过 ``ReplayReader`` / DuckDB 读取；如果 ``_schema.json`` 不存在，
应回到 ``run-experiment`` 或配置修复阶段。

推荐流程：

1. **加载上下文**：读取 hypothesis、experiment config、steps 和 run 元数据。
2. **确认问题**：明确本次分析是验证假设、解释异常、比较组间差异，还是生成报告。
3. **探索数据**：列出 replay dataset，查看 schema、行数、关键字段和缺失情况。
4. **提出发现**：先给出可检验发现，再决定需要哪些图表。
5. **生成图表**：单实验默认最多 5 张图；每张图在报告中必须有一句说明。
6. **写报告**：单实验输出到 ``presentation/hypothesis_{id}/``，跨实验综合输出到 ``synthesis/``。

报告与状态目录约定：用户可见报告写在 ``presentation/`` 与 ``synthesis/``；harness 机器状态在 ``.agentsociety/analysis/``；不要在 ``presentation/`` 下再建旧式 ``analysis/`` 目录。

常用命令：

.. code-block:: bash

   $PYTHON_PATH .agentsociety/bin/ags.py analysis load-context --workspace . --hypothesis-id 1 --experiment-id 1
   python - <<'PY'
   from agentsociety2.storage import ReplayReader
   reader = ReplayReader("hypothesis_1/experiment_1/run/replay")
   for dataset in reader.load_dataset_catalog():
       print(dataset["dataset_id"], dataset["table_name"])
   reader.close()
   PY


学术文献检索
~~~~~~~~~~~~~~

``agentsociety-literature-search`` 通过统一的远程检索服务收集学术文献，并把结果保存到工作区 ``papers/`` 目录。默认检索所有已配置数据源：``local``、``arxiv``、``crossref``、``openalex``。

配置项：

.. code-block:: bash

   LITERATURE_SEARCH_MCP_URL=https://llmapi.fiblab.net/mcp/
   LITERATURE_SEARCH_API_KEY=your-literature-search-key

搜索命令示例：

.. code-block:: bash

   $PYTHON_PATH .agentsociety/bin/ags.py literature-search "agent-based modeling social networks"
   $PYTHON_PATH .agentsociety/bin/ags.py literature-search "urban mobility simulation LLM agents" --year-from 2020 --year-to 2026 --multi-query

输出约定：

- ``papers/literature_index.json`` 是稳定索引，记录标题、作者、年份、来源、query、分数和本地 ``file_path``。
- 每篇文献保存为 ``papers/<title>_<timestamp>.md``，这是后续 hypothesis、analysis 与外部 ``paper-toolkit`` 写作流程引用的主要本地笔记。
- 检索完成后会自动尝试下载开放获取 PDF 到 ``papers/full_texts/``，路径写入 ``extra_fields.full_text.file_path``；不要把索引中的 ``file_path`` 从 Markdown 笔记替换成 PDF。
- 文献检索不会自动绕过出版商权限。PDF 下载只处理开放获取或用户授权的文件；没有开放 PDF 时，可以补充本地 Markdown 笔记并记录来源。

Python API
--------------------

研究技能也可以通过 Python API 直接调用。

文献技能 (literature)
~~~~~~~~~~~~~~~~~~~~~~~

文献技能通过 **MCP 协议** 连接学术文献检索网关，使用工作区 ``.env`` 中的
``LITERATURE_SEARCH_MCP_URL`` 和 ``LITERATURE_SEARCH_API_KEY``（无需单独配置
Claude ``mcp.json``）。网关上的其他 MCP 工具不会被文献技能调用。推荐优先使用
``search_literature_and_save``，而不是直接调用底层 ``search_literature``：
前者会把检索结果落到工作区中，确保后续 Agent、Claude Code 和论文写作技能
都能通过本地文件继续引用这些文献。

.. code-block:: python

   from agentsociety2.skills.literature import search_literature_and_save, load_literature_index

   # 搜索并保存文献（默认 10 篇、所有数据源，并更新 papers/literature_index.json）
   result = await search_literature_and_save(
       workspace_path=Path("./workspace"),
       query="agent-based modeling social networks",
       year_from=2020,      # 可选：年份筛选
       year_to=2024,
       enable_multi_query=True,  # 可选：启用多查询模式
   )

   # 指定数据源搜索
   await search_literature_and_save(
       workspace_path=Path("./workspace"),
       query="machine learning",
       sources=["local", "arxiv"],  # 可选：指定数据源
   )

   # 加载文献索引
   index = load_literature_index(workspace_path=Path("./workspace"))

**保存结果**:

- 每篇检索结果都会保存为 ``papers/<title>_<timestamp>.md``。
  这个 Markdown 文件是稳定的本地文献笔记，包含标题、检索词、年份、期刊、
  DOI/URL、摘要、作者和相关内容片段。
- ``papers/literature_index.json`` 会同步更新。索引中的 ``file_path``
  指向本地 Markdown 文献笔记，因此插件中的 ``@引用`` 可以复制为
  ``@papers/<title>_<timestamp>.md``，供 Claude Code 或 Agent 读取。
- 重复运行检索时会生成新的本地文献笔记，并追加到索引中，便于保留不同检索轮次的上下文。

**原文下载（由 Claude/Agent 按需执行）**:

文献技能不会在 Python API 中硬编码下载策略。检索结果会尽量保留
``doi``、``url``、``pdf_url``、``full_text_url``、``download_url``、
``open_access``、``best_oa_location`` 等元信息；Claude Code 或 Agent
可以基于这些线索按需下载开放获取原文。

建议的下载约定：

- 原文 PDF 放在 ``papers/full_texts/*.pdf``。
- 优先使用 API 返回的 PDF 直链；arXiv 论文可从 ``/abs/<id>`` 转为
  ``https://arxiv.org/pdf/<id>.pdf``。
- DOI 仅作为落地页线索，不保证能直接得到 PDF；如果需要下载，应确认最终响应确实是 PDF。
- 下载完成后，可在对应索引条目的 ``extra_fields["full_text"]`` 中记录:

  .. code-block:: json

     {
       "status": "downloaded",
       "file_path": "papers/full_texts/example.pdf",
       "source_url": "https://arxiv.org/pdf/2401.01234.pdf"
     }

  如果没有找到开放原文，也可以记录 ``{"status": "no_candidate"}`` 或
  ``{"status": "failed", "reason": "..."}``，便于插件页面显示状态。

.. note::

   许多 CrossRef/OpenAlex 结果只提供 DOI 或落地页，不一定有开放 PDF。
   Claude/Agent 不应绕过出版商权限，也不应把 HTML 落地页当作 PDF 保存。

**数据源**:
- ``local``: RAGFlow 本地知识库
- ``arxiv``: arXiv 预印本平台
- ``crossref``: CrossRef DOI 元数据库
- ``openalex``: OpenAlex 学术图谱 (2.5亿+ 论文)

**配置**:
在 workspace ``.env`` 中配置 MCP（无需 Claude ``mcp.json``，除非要让 Claude 独立连接同一网关）:

.. code-block:: bash

   LITERATURE_SEARCH_MCP_URL=https://llmapi.fiblab.net/mcp/
   LITERATURE_SEARCH_API_KEY=your-literature-search-key

假设技能 (hypothesis)
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from agentsociety2.skills.hypothesis import add_hypothesis, get_hypothesis, list_hypotheses

   # 添加假设
   add_hypothesis(
       workspace_path=Path("./workspace"),
       hypothesis="网络密度越高，信息传播速度越快"
   )

   # 列出假设
   hypotheses = list_hypotheses(workspace_path=Path("./workspace"))

实验技能 (experiment)
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from agentsociety2.skills.experiment import (
       start_experiment, get_experiment_status,
       get_available_env_modules, get_available_agent_modules
   )

   # 获取可用模块
   env_modules = get_available_env_modules()
   agent_modules = get_available_agent_modules()

   # 启动实验
   await start_experiment(
       workspace_path=Path("./workspace"),
       hypothesis_id="1",
       experiment_id="1"
   )

分析技能 (analysis)
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from pathlib import Path

   from agentsociety2.storage import ReplayReader
   from agentsociety2.skills.analysis import ContextLoader

   workspace = Path("./workspace")
   context = ContextLoader(workspace).load_context("1", "1")
   reader = ReplayReader(workspace / "hypothesis_1" / "experiment_1" / "run" / "replay")
   datasets = reader.load_dataset_catalog()
   rows = reader.fetch_dataset_rows(
       reader.get_dataset_by_id("core.agent_profile"),
       limit=5,
   )
   reader.close()

跨实验对比不再使用独立综合 skill，而是作为
``agentsociety-analysis`` 的 Stage 5 在 Claude Code 中完成。

论文写作
~~~~~~~~~~~~

论文写作已从 ``agentsociety2.skills`` 包内移出，后续通过独立
``paper-toolkit`` 工作流承载。核心模拟、实验、分析链路仍由本页上方的
research skills 提供；需要论文交付时，在完成分析报告和图表审计后进入
外部论文工具链。

完整工作流示例
------------------------

下面是一个使用 Claude Code Skills 的典型研究工作流：

1. **定义研究话题** - 编辑 ``TOPIC.md``
2. **文献检索** - 使用 ``/agentsociety-literature-search``
3. **创建假设** - 使用 ``/agentsociety-hypothesis add``
4. **配置实验** - 使用 ``/agentsociety-experiment-config validate/prepare/run``
5. **执行实验** - 使用 ``/agentsociety-run-experiment start``
6. **分析结果** - 使用 ``/agentsociety-analysis``
7. **生成论文** - 使用独立 ``paper-toolkit`` 工作流

配置
------------------------

研究技能使用相同的 LLM 配置。可以通过环境变量为特定技能配置不同的模型：

.. code-block:: bash

   # 默认 LLM
   export AGENTSOCIETY_LLM_MODEL="gpt-5.5"

   # 代码生成（实验设计、分析）
   export AGENTSOCIETY_CODER_LLM_MODEL="gpt-5.5"

   # 高频操作（智能体生成）
   export AGENTSOCIETY_NANO_LLM_MODEL="gpt-5.5"

Agent Skills
--------------------

AgentSociety 2 还支持 Agent Skills。当前 ``PersonAgent`` 使用 metadata-first、selected-only
模型：LLM 先看到 skill 的 name / description，只有被选择的 skill 才会被激活和读取。
唯一内置 skill 是 ``daily-guidance``；旧的 ``observation`` / ``cognition`` / ``plan`` /
``memory`` 四技能已经移除。自定义 skill 放在 ``custom/skills/``，脚本默认通过进程内
``entrypoint(argv, ctx)`` 执行。

* **daily-guidance** - 日常行为、需求衰减与短时程行动指导
* **custom skills** - 工作区级自定义能力，按需激活并可访问 agent workspace

详见 :doc:`agent_skills`。

参考
------------------------

* :doc:`cli` - 使用 CLI 运行实验
* :doc:`agent_skills` - Agent Skills 详解
* :doc:`custom_modules` - 创建自定义模块
* :doc:`development` - 开发指南

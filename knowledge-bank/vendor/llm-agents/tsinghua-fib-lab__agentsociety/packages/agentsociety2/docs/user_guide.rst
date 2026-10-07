AI Social Scientist 使用指南
================================

**AI Social Scientist** 是 AgentSociety 2 的交互式研究助手，以 VSCode 扩展的形式提供可视化配置、后端管理和研究编排能力。它支持两种使用方式：

- **在线工作空间**：通过网页平台直接使用，无需本地安装，适合快速上手。
- **本地开发**：在本地安装扩展和依赖，适合需要自定义环境的高级用户。

.. _online-workspace:

在线工作空间
------------

我们推荐使用在线平台进行实验，平台已预装 agentsociety2 库、AI Social Scientist 插件和 Claude Code CLI。

平台地址：https://agentsociety2.fiblab.net/

注册与登录
~~~~~~~~~~

1. 打开平台主页，点击"登录"。

.. image:: _static/images/user_guide/platform_login.png
   :alt: 平台登录页面
   :width: 80%

2. 如果没有账号，点击"注册"完成注册流程。已有 FIBLAB 账号的用户可直接登录。

.. image:: _static/images/user_guide/platform_register.png
   :alt: 注册页面
   :width: 80%

.. note::

   登录成功后，您可能需要联系平台管理员审批账号权限，审批通过后刷新页面即可。

创建工作空间
~~~~~~~~~~~~

1. 进入工作区管理页面，点击"创建工作空间"，输入名称后确认。

.. image:: _static/images/user_guide/workspace_create.png
   :alt: 创建工作空间
   :width: 80%

2. 等待工作空间状态从"创建中"变为"运行中"。

.. image:: _static/images/user_guide/workspace_running.png
   :alt: 工作空间运行中
   :width: 80%

3. 点击工作空间可查看 **Coder 账号密码**、 **免费 LLM API 端点**和 **API Key** 等信息，请妥善保存。

.. image:: _static/images/user_guide/workspace_password.png
   :alt: 工作空间账号与 API 信息
   :width: 80%

4. 复制页面上方的 Coder 账号信息，点击"打开"进入开发环境。

.. image:: _static/images/user_guide/coder_login.png
   :alt: Coder 登录
   :width: 80%

5. 在 Coder 页面中选择 **code-server** （推荐）或 **VS Code Desktop** 打开开发环境。

.. image:: _static/images/user_guide/coder_open.png
   :alt: 选择 code-server 或 VSCode Desktop
   :width: 80%

.. image:: _static/images/user_guide/codeserver_interface.png
   :alt: code-server 界面
   :width: 80%

.. _local-setup:

本地环境安装
------------

前置条件
~~~~~~~~

- **操作系统**：macOS 或 Linux（Windows 用户建议使用 WSL）
- **Python**：3.11 或更高版本，推荐使用 `uv <https://docs.astral.sh/uv/>`_ 管理

.. code-block:: bash

   # 安装 uv（macOS/Linux）
   curl -LsSf https://astral.sh/uv/install.sh | sh

安装 agentsociety2
~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # 使用 uv
   uv venv && source .venv/bin/activate
   uv pip install agentsociety2

   # 或使用 pip
   pip install agentsociety2

.. important::

   请确保安装的是最新版本。查看当前最新版本：https://pypi.org/project/agentsociety2/

安装 AI Social Scientist 插件
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. 从 `Release <https://github.com/tsinghua-fib-lab/AgentSociety/releases>`_ 下载最新版本的 VSIX 文件。
2. 在 VSCode 中按 ``Cmd/Ctrl + Shift + P``，输入 ``Extensions: Install from VSIX...``。
3. 选择下载的 VSIX 文件完成安装。

配置 Coding Agent
~~~~~~~~~~~~~~~~~

插件初始化工作区时会自动同步 AI Social Scientist 的技能到 ``.claude/skills/`` 目录下。您也可以点击侧边栏的"同步 AI 助手资源"手动同步。

.. image:: _static/images/user_guide/sync_skills.png
   :alt: 同步 AI 助手资源
   :width: 60%

Claude Code（推荐）：

.. code-block:: bash

   npm install -g @anthropic-ai/claude-code

配置第三方中转服务时，创建 ``~/.claude/settings.json``：

.. code-block:: json

   {
     "env": {
       "ANTHROPIC_AUTH_TOKEN": "YOUR_API_KEY",
       "ANTHROPIC_BASE_URL": "YOUR_BASE_URL",
       "ANTHROPIC_MODEL": "claude-sonnet-4-6"
     }
   }

也可以通过 AI Social Scientist 插件的 **高级配置 → Claude / Codex 路由**
打开图形化配置页，使用内置的本地 AI Gateway 统一管理供应商（见下文）。

.. _ai-gateway:

本地 AI Gateway
^^^^^^^^^^^^^^^^^

**AI Gateway** 是插件内置的本地 HTTP 代理，运行在 ``127.0.0.1:15721-15820``
端口范围内。它拦截 Claude Code 和 Codex CLI 的 API 请求，将其转发到你
配置的上游供应商，并自动完成协议格式转换与模型名映射。

它的核心价值在于：**让你用任意第三方 LLM 供应商（OpenAI 兼容、智谱、
DeepSeek 等）来驱动 Claude Code / Codex**，无需每个供应商都去申请
官方 Anthropic / OpenAI 账号。

简单说，请求流是这样的：

.. code-block:: text

   Claude Code ─┐                         ┌─► Anthropic 原生供应商
   (Anthropic   │   本地 AI Gateway        │     (直通)
    协议)       ├─► 127.0.0.1:<port>    ───┤
                │   · 协议翻译            ├─► OpenAI 兼容供应商
   Codex CLI  ──┘   · 模型名映射          │     (翻译为 Chat Completions)
   (Responses      · 故障转移 / 用量统计   │
    协议)                                └─► …更多供应商

Gateway 对 Claude Code 始终呈现一个标准的 Anthropic Messages 端点
（``/v1/messages``），对 Codex 始终呈现一个标准的 OpenAI Responses 端点
（``/v1/responses``）。因此这两个 CLI 不需要知道背后其实是哪家供应商、
哪种协议——Gateway 会在中间完成所有转换。

供应商与路由
""""""""""""""

Gateway 提供一个**共享供应商池**——供应商只保存一份，但可以在供应商
卡片上分别「激活」到 Claude Code 或 Codex CLI 角色：

- **Anthropic 原生供应商** （如 ``api.anthropic.com``、DeepSeek 的 ``/anthropic`` 端点）：直接服务 Claude Code，请求直通转发。
- **OpenAI 兼容供应商** （如 ``api.openai.com``、智谱 ``paas/v4``、DeepSeek ``/v1``）：可同时服务 Claude Code 和 Codex CLI。
  - 服务 Claude Code 时，Gateway 会把 Claude Code 发出的 **Anthropic Messages** 请求实时翻译成 **OpenAI Chat Completions**，再把返回的 SSE 流翻译回去。
  - 服务 Codex CLI 时，Gateway 会把 Codex 发出的 **OpenAI Responses** 请求翻译成 **OpenAI Chat Completions**。

添加供应商时需要选择正确的接口类型：

- 若供应商提供 Anthropic Messages 协议（``/v1/messages``），选择 **Anthropic**。
- 若供应商只提供 OpenAI Chat 协议（``/v1/chat/completions``），选择 **OpenAI 兼容**。

内置预设已覆盖常见供应商（Anthropic、DeepSeek、智谱、Kimi、MiniMax、
火山引擎、OpenRouter、阿里百炼、Moonshot、SiliconFlow 等），可直接选用。

协议格式转换
""""""""""""""

Gateway 在转发过程中会做以下转换，确保第三方模型的行为尽可能贴近原生体验：

- **请求方向**：``system`` 提示、``tools`` 工具定义、``tool_choice``、
  ``thinking``（扩展思考，会映射为 ``reasoning_effort``）、``max_tokens``
  等都会按目标协议规范化。
- **响应方向**：第三方模型的 ``reasoning_content``（思考过程）会被翻译成
  Anthropic 的 ``thinking`` 内容块；``tool_calls`` 会被翻译成 ``tool_use``
  内容块，保证 Claude Code 能正确识别工具调用（这是保证工具调用 / 多轮
  对话不中断的关键）。
- **模型名映射**：Claude Code 发出的 ``claude-sonnet-*`` / ``claude-opus-*`` /
  ``claude-haiku-*`` / ``claude-fable-*`` 会自动映射为供应商配置的对应角色
  模型；``[1M]`` 等本地能力标记会在转发前剥离，避免泄漏给供应商。

故障转移与用量统计
"""""""""""""""""""

- **故障转移**：可为 Claude 和 Codex 分别开启多供应商优先级，单点失败后
  自动切换到下一个候选供应商，并由断路器（circuit breaker）抑制反复
  失败的上游。切换成功后会更新活跃供应商，UI 会同步反映。
- **用量统计**：面板按天展示请求趋势，区分 Claude 与 Codex 来源，支持
  7 天 / 30 天 / 全部 筛选。会分别统计输入、输出、缓存读取、缓存写入 token。
- **费用估算**：定价来源优先级为 **自定义 > 远程（OpenRouter / LiteLLM）> 内置**，
  远程定价 24 小时缓存。对 Codex / OpenAI 兼容记录，会先从可计费输入中
  扣除缓存命中再计费，缓存读取单独计价。
- **状态栏**：启用 Gateway 后，VS Code 状态栏会显示 Gateway 端口及路由状态（Claude / Codex / Claude + Codex），点击可打开后端状态菜单或回到配置页。

Gateway 排错
"""""""""""""

- **查看日志**：打开 ``AI CLI Gateway`` 输出通道，每行记录请求路径、
  上游地址、HTTP 状态码、耗时与模型名，形如
  ``POST /v1/messages → 200 (4183ms) [deepseek-v4-pro] [https://...]``。
- **日志显示 ``in:0 out:0``**：表示该次响应未提取到 token 用量，常见于流
  式响应提前中断或上游未返回 usage 字段。
- **请求中断 / 对话到一半停止**：通常是对话中触发了工具调用，但旧版本
  网关未正确翻译 ``tool_calls``。请确认使用的是已修复该问题的扩展版本。
- **403 key_model_access_denied**：上游拒绝该 API Key 访问请求的模型，
  说明模型名映射未生效或供应商未开通该模型权限，请在供应商卡片核对模型。
- **手动校验健康状态**：``curl http://127.0.0.1:<port>/health`` 应返回
  ``{"ok": true, ...}``。

也可以安装 Claude Code 的 VSCode 插件，点击扩展侧边栏的"AI 对话"后会直接弹出 Claude Code 对话页面：

.. image:: _static/images/user_guide/claude_vscode.png
   :alt: Claude Code VSCode 集成
   :width: 80%

.. note::

   同步到 ``.claude/skills/`` 的技能可被 Claude Code 和 Cursor 自动识别。插件也会自动为 CodeX 创建符号链接（``.codex``），无需手动操作。

.. _env-config:

环境配置
--------

新建工作区
~~~~~~~~~~

在线工作空间中，在左侧文件树新建一个文件夹作为工作区（如 ``demo``），然后通过 ``File → Open Folder`` 打开。

.. image:: _static/images/user_guide/new_workspace_folder.png
   :alt: 新建工作区文件夹
   :width: 80%

配置向导
~~~~~~~~

首次打开工作区且尚未完成初始配置时，扩展会 **自动打开配置页** 并显示 **5 步向导** （不会同时弹出额外的欢迎 Toast）。向导步骤如下：

**步骤 1：仿真 LLM** — 填写默认大模型 API 信息并点击验证：

.. list-table::
   :widths: 25 50 25
   :header-rows: 1

   * - 参数
     - 说明
     - 是否必填
   * - LLM API 密钥
     - 大模型服务的 API Key，用于默认对话、分析等核心功能
     - 是
   * - LLM API 基础 URL
     - API 的 base URL，如 ``https://api.openai.com/v1``
     - 是
   * - LLM 模型名称
     - 使用的模型名称，默认 ``gpt-5.5``
     - 是
   * - 推理（thinking）
     - 配置页下拉：跟随网关默认 / 开 / 关；写入 ``AGENTSOCIETY_LLM_THINKING``（``on`` / ``off``）。留空则不发送该参数
     - 否

验证通过后会自动进入下一步。AgentSociety 支持任何 OpenAI 接口兼容的大模型 API。更多环境变量见 :doc:`installation`。

**步骤 2：保存配置** — 查看摘要并保存到工作区 ``.env``。必须包含有效的 API Key 才会标记为「已完成初始配置」。

**步骤 3：启动后端** — 选择或自动检测 ``PYTHON_PATH``，点击「保存并启动后端」。成功后状态栏显示 Backend 端口；向导会自动进入可选步骤。

.. list-table::
   :widths: 25 50 25
   :header-rows: 1

   * - 参数
     - 说明
     - 推荐值
   * - Python 路径
     - Python 运行环境路径，留空则自动检测已安装 ``agentsociety2`` 的环境
     - ``uv sync`` 后的 ``.venv/bin/python``

**步骤 4：文献检索（可选）** — 配置学术文献 MCP 网关，可跳过。

**步骤 5：CLI 网关（可选）** — 配置 Claude Code / Codex 本地 AI Gateway 供应商与路由，可跳过。

完成或退出向导后，可随时通过配置页「打开向导」重新进入。向导退出状态保存在扩展全局状态中（非 Webview localStorage）。

高级配置
~~~~~~~~

在配置页切换到完整模式后，可展开 **专用与运行** 标签页，按需填写（均可留空，沿用默认 LLM）：

- **专用模型**：代码生成（Coder）、Embedding；Coder 也可单独设置推理开关（``AGENTSOCIETY_CODER_LLM_THINKING``）
- **Python 环境**：扫描并选择解释器
- **文献检索**：MCP URL 与 API Key
- **Claude / Codex 路由**：本地 AI Gateway 供应商池

.. list-table::
   :widths: 25 50 25
   :header-rows: 1

   * - 参数
     - 说明
     - 推荐值
   * - Embedding 模型
     - 文本嵌入模型
     - ``text-embedding-3-large``（维度 ``1024``）
   * - 学术文献检索
     - 学术文献检索 MCP 网关地址
     - ``https://llmapi.fiblab.net/mcp/``

状态栏与输出
~~~~~~~~~~~~

- **状态栏**：Backend（端口）、Gateway（路由状态/成功率）、LLM（验证通过时显示模型名）
- **输出通道**：``AI Social Scientist``（主通道，含 ``[API]`` ``[Chat]`` 等前缀）、``AI Social Scientist Backend``、``AI CLI Gateway``
- 扩展默认启用 ``python.terminal.useEnvFile``，集成终端会自动加载工作区 ``.env``

启动后端
~~~~~~~~

配置向导第 3 步或配置页中的「保存并启动后端」会自动保存配置并启动后端服务。也可通过状态栏 Backend 菜单或命令面板启动。从配置页启动时，成功/失败提示仅在配置页内显示，避免与命令 Toast 重复。

右下角状态栏显示后端运行状态（含端口号）表示启动成功。

.. _start-research:

开始研究
--------

初始化工作区
~~~~~~~~~~~~~~

后端启动成功后，在插件页面点击"初始化工作区"，输入研究话题（如 "polarization"）并回车。系统会自动创建 ``TOPIC.md`` 和相关目录结构。

.. image:: _static/images/user_guide/init_topic.png
   :alt: 初始化工作区
   :width: 60%

``TOPIC.md`` 是贯穿整个研究流程的核心文档，您可以随时手动编辑来补充研究描述、背景信息和研究方向。

与 Claude Code 协作
~~~~~~~~~~~~~~~~~~~~

点击插件侧边栏的"AI 对话"按钮进入 Claude Code：

.. image:: _static/images/user_guide/claude_login.png
   :alt: Claude Code 登录
   :width: 80%

进入对话界面后，用自然语言描述研究需求即可。平台会将研究流程中的关键操作封装为技能（Skill），Claude Code 会自动识别并调用。

.. image:: _static/images/user_guide/claude_chat.png
   :alt: Claude Code 对话界面
   :width: 80%

推荐的研究流程
~~~~~~~~~~~~~~

我们推荐按以下顺序进行研究，但每个阶段都可以随时回退或跳过：

.. code-block:: text

   初始化研究话题 → 文献检索 → 假设管理 → 实验配置
        │
        ▼
   运行实验 → 数据分析 → 综合报告 → 论文生成

各阶段说明见 :doc:`skills`。

工作区目录结构
~~~~~~~~~~~~~~

随着研究推进，工作区会逐步形成以下结构（无需手动创建）：

.. code-block:: text

   工作区/
   ├── TOPIC.md                          # 研究叙事中心文档
   ├── .env                              # 环境配置
   ├── papers/
   │   ├── literature_index.json         # 文献索引
   │   ├── <title>_<timestamp>.md        # 文献笔记
   │   └── full_texts/                   # 全文 PDF（如有）
   ├── user_data/                        # 用户数据
   ├── datasets/                         # 数据集
   ├── hypothesis_1/
   │   ├── HYPOTHESIS.md                 # 假设描述
   │   ├── SIM_SETTINGS.json             # 模块配置
   │   ├── experiment_1/                 # 实验 1（对照组）
   │   │   ├── init/
   │   │   │   ├── init_config.json      # 智能体与环境配置
   │   │   │   └── steps.yaml            # 仿真步骤
   │   │   └── run/                      # 运行产出
   │   └── experiment_2/                 # 实验 2（处理组）
   ├── presentation/                     # 分析报告
   │   └── hypothesis_1/
   │       └── experiment_1/
   │           ├── report.md
   │           ├── report.html
   │           └── charts/
   ├── synthesis/                        # 综合报告
   └── custom/                           # 自定义模块
       └── envs/

分享工作区
~~~~~~~~~~

研究进行到可交接时，可在扩展侧边栏使用 **导出工作区**，把当前项目打包成压缩包发给同事：

- 导出列表会展示研究问题、假设与实验、文献、数据、分析报告、项目设置和技能；已有的关键内容默认勾选
- ``hypothesis_*`` 会完整包含实验配置（``init/``）和运行结果（``run/``），体积较大时可取消勾选
- **始终排除**：密钥与 ``.env``、虚拟环境、Git 历史，以及本地 IDE 状态（``.cursor`` / ``.vscode``）等
- 发出去之前，请确认你有权分享其中的论文、数据和第三方技能

对方在扩展中选择 **导入工作区** 后，依次选择分享包和保存位置，再输入新项目文件夹名。扩展会显示最终路径并新建目录，不会覆盖已有项目；导入后需要在配置页填写自己的模型密钥，才能继续运行。

文献库：上传 PDF 与标识符补全
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

侧边栏 **文献库** 用于管理本地论文资产（与 CLI ``literature-search`` 主题检索互补）：

- 可 **上传 PDF**；扩展会尽量从文件内容扫描 DOI / arXiv ID，并调用公开接口补全标题、作者等元数据
- 也可 **粘贴 DOI 或 arXiv ID** 直接入库并查找元数据
- 索引与笔记写在 ``papers/``（如 ``literature_index.json``）；全文 PDF 通常落在 ``papers/full_texts/``
- 按主题批量检索、开放获取下载仍走文献技能 / MCP，见 :doc:`skills`

.. _user-guide-faq:

常见问题
--------

code-server 显示 unhealthy
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

初次创建工作空间时，后端服务可能正在启动中。稍等片刻后刷新页面，等待状态变为绿色的 "Running"。如果持续出现，可以尝试重启工作区。

打开 code-server 后显示 502 错误
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

后端服务未正确启动，请耐心等待后刷新页面。如果问题持续存在，请查看后端日志或联系平台管理员。

本地 Python 环境路径问题
~~~~~~~~~~~~~~~~~~~~~~~~~~

在线平台预装了 Python 环境，本地使用时（尤其是通过 uv 创建的虚拟环境），需要在高级配置中指定正确的 Python 路径：

.. code-block:: bash

   source .venv/bin/activate
   which python3

将输出的路径填入配置向导"后端服务"步骤的 Python 路径字段。

实验运行失败
~~~~~~~~~~~~

常见原因：

- **LLM API 连接失败**：检查 ``.env`` 中的 API 配置是否正确
- **模块实例化失败**：检查 ``init_config.json`` 中的参数是否与模块要求一致
- **内存不足**：减少智能体数量或仿真步数

导入别人的工作区后无法运行
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

分享包不含密钥。请打开配置页，填写你自己的模型 API Key 后再启动后端或运行实验。

更多 CLI 使用方法见 :doc:`cli`，研究技能详见 :doc:`skills`。

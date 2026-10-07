安装
============

系统要求
------------

AgentSociety 2 需要 Python 3.11 或更高版本。

从 PyPI 安装
-----------------

最简单的安装 AgentSociety 2 的方法是使用 pip：

.. code-block:: bash

   pip install agentsociety2

这将安装核心包。如果要安装开发依赖：

.. code-block:: bash

   pip install "agentsociety2[dev]"

对于文档依赖：

.. code-block:: bash

   pip install "agentsociety2[docs]"

安装所有内容：

.. code-block:: bash

   pip install "agentsociety2[all]"

从源码安装
-------------------

要从最新的源代码安装：

.. code-block:: bash

   git clone https://github.com/tsinghua-fib-lab/agentsociety.git
   cd agentsociety/packages/agentsociety2
   pip install -e .

验证安装
-------------------

要验证您的安装，运行：

.. code-block:: python

   import agentsociety2
   print(agentsociety2.__version__)

您应该能看到版本号被打印出来。

配置
-------------

AgentSociety 2 需要 LLM API 凭证。设置以下环境变量：

**必需配置**

.. code-block:: bash

   # Default LLM (Required - for most operations)
   export AGENTSOCIETY_LLM_API_KEY="your-api-key"
   export AGENTSOCIETY_LLM_API_BASE="https://api.openai.com/v1"
   export AGENTSOCIETY_LLM_MODEL="gpt-5.5"

**高级配置**

对于专门的任务，您可以配置单独的 LLM 实例。如果未设置这些选项，
它们将回退到默认 LLM 配置：

.. code-block:: bash

   # Coder LLM (for code-related tasks)
   # Falls back to: AGENTSOCIETY_LLM_API_KEY, AGENTSOCIETY_LLM_API_BASE
   export AGENTSOCIETY_CODER_LLM_API_KEY="your-coder-api-key"      # Optional
   export AGENTSOCIETY_CODER_LLM_API_BASE="https://api.openai.com/v1"  # Optional
   export AGENTSOCIETY_CODER_LLM_MODEL="gpt-5.5"                    # Optional

   # Nano LLM (for high-frequency, low-latency operations)
   # Falls back to: AGENTSOCIETY_LLM_API_KEY, AGENTSOCIETY_LLM_API_BASE
   export AGENTSOCIETY_NANO_LLM_API_KEY="your-nano-api-key"        # Optional
   export AGENTSOCIETY_NANO_LLM_API_BASE="https://api.openai.com/v1"  # Optional
   export AGENTSOCIETY_NANO_LLM_MODEL="gpt-5.5"                     # Optional

   # Embedding model (for text embedding and semantic search)
   # Falls back to: AGENTSOCIETY_LLM_API_KEY, AGENTSOCIETY_LLM_API_BASE
   export AGENTSOCIETY_EMBEDDING_API_KEY="your-embedding-api-key"  # Optional
   export AGENTSOCIETY_EMBEDDING_API_BASE="https://api.openai.com/v1"  # Optional
   export AGENTSOCIETY_EMBEDDING_MODEL="text-embedding-3-large"   # Optional
   export AGENTSOCIETY_EMBEDDING_DIMS="1024"                      # Optional

**推理（thinking）开关**

仅适用于 OpenAI 兼容 chat-completions 接口。**全部留空时不发送任何新参数**，
出站请求与不启用该功能时完全一致。

.. code-block:: bash

   # on / off (also accepts 1/0/true/false). Unset = send nothing.
   export AGENTSOCIETY_LLM_THINKING="off"

   # Explicit reasoning_effort. When thinking=off and this is unset, "minimal"
   # is used. When thinking=on, it is only sent if explicitly set here.
   export AGENTSOCIETY_LLM_REASONING_EFFORT=""

   # Gateway-specific OpenAI-compatible switch, a JSON object merged into the
   # request's extra_body, e.g. {"enable_thinking": false} or
   # {"thinking": {"type": "disabled"}}. When set, thinking=off sends ONLY this
   # (no reasoning_effort), so the gateway never sees two conflicting switches.
   export AGENTSOCIETY_LLM_EXTRA_BODY=""

   # Per-role overrides for the coder model (env-router code generation);
   # each falls back to the corresponding AGENTSOCIETY_LLM_* value.
   export AGENTSOCIETY_CODER_LLM_THINKING=""            # Optional
   export AGENTSOCIETY_CODER_LLM_REASONING_EFFORT=""    # Optional
   export AGENTSOCIETY_CODER_LLM_EXTRA_BODY=""          # Optional

**数据目录**

.. code-block:: bash

   # Directory for storing agent data, memory and persistence files
   # Default: ./agentsociety_data
   export AGENTSOCIETY_HOME_DIR="/path/to/your/data"

**使用 .env 文件**

您也可以在项目目录中创建 ``.env`` 文件：

.. code-block:: bash

   # 推荐：从仓库根目录复制模板（若你在源码仓库内）
   cp .env.example .env
   # 然后编辑 .env 填入 API Key

.. code-block:: bash

   # Required - LLM API Configuration
   AGENTSOCIETY_LLM_API_KEY=your-api-key
   AGENTSOCIETY_LLM_API_BASE=https://api.openai.com/v1
   AGENTSOCIETY_LLM_MODEL=gpt-5.5

   # Optional - Agent Behavior Configuration
   AGENT_MODEL=gpt-5.5                  # Override model for agents
   AGENT_CONTEXT_WINDOW=200000          # Model context window
   AGENT_MAX_TOOL_ROUNDS=24             # Max tool loop rounds

   # Optional - Specialized LLM instances (fallback to default)
   AGENTSOCIETY_CODER_LLM_MODEL=gpt-5.5
   AGENTSOCIETY_NANO_LLM_MODEL=gpt-5.5
   AGENTSOCIETY_EMBEDDING_MODEL=text-embedding-3-large
   AGENTSOCIETY_EMBEDDING_DIMS=1024
   AGENTSOCIETY_HOME_DIR=./agentsociety_data

.. note::

   **环境变量区分**：

   - ``AGENTSOCIETY_LLM_*``: 全局 LLM API 配置，用于模型调用
   - ``AGENT_*``: Agent 行为配置，如上下文窗口大小、工具循环轮数等

LLM 调度与本地并发控制
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

LLM 调度由可序列化的 ``LLMClient`` 完成。每个 Ray task、env router actor 或 driver 进程在自己的
事件循环中首次调用 LLM 时，本地创建 litellm Router 与 ``AdaptiveSemaphore``。
``AdaptiveSemaphore`` 基于近期延迟和 rate-limit 错误做 AIMD 自适应并发。

.. code-block:: bash

   # Ray CPU 预算（ray.init 的 num_cpus）：封顶每 tick 同时运行的 step_agent_batch
   # Ray Task 数。默认取机器 CPU 核数；调低可为 driver / env actor / trace 留出空间。
   # export AGENTSOCIETY_LLM_RAY_MAX_WORKERS=8

   # 每个本地 LLMClient 的 AIMD 初始并发；无人工上下限，由 AIMD 依延迟/限流自由自调节。
   export AGENTSOCIETY_LLM_RAY_CONCURRENCY=16

   # 每个 step_agent_batch Ray Task 处理的 agent 数；task 数 = ⌈N / BATCH_SIZE⌉，
   # 应 ≥ 同时运行的 worker 数才能打满 CPU（CLI --batch-size 可覆盖）。
   # export AGENTSOCIETY_BATCH_SIZE=256

   # AIMD “慢调用”判定
   export AGENTSOCIETY_LLM_LATENCY_DEGRADE_FACTOR=4.0   # 相对退避因子（相对健康基线的倍数）
   # export AGENTSOCIETY_LLM_SLOW_LATENCY_MS=8000       # 可选：绝对延迟 SLO（毫秒）

.. note::

   ``AGENTSOCIETY_LLM_RAY_CONCURRENCY`` 只是 AIMD 的起点，没有人工上下限——每进程并发会
   自动逼近 API 真实容量并在延迟/限流恶化时回退。若网关有严格 QPS 上限可调低起点；
   实际总并发还取决于同时运行的 Ray task 数（``AGENTSOCIETY_LLM_RAY_MAX_WORKERS``）。

支持的 LLM 提供商
------------------------

AgentSociety 2 通过 LiteLLM 路由模型调用；文档中的默认示例使用 OpenAI 兼容的 Chat Completions 接口：

- ``AGENTSOCIETY_LLM_API_BASE=https://api.openai.com/v1``
- ``AGENTSOCIETY_LLM_MODEL=gpt-5.5``

如果你使用其它 LiteLLM 支持的 OpenAI 兼容网关，请保持同样的环境变量结构，并把 ``AGENTSOCIETY_LLM_API_BASE`` 与模型名替换为该网关提供的值。

.. _litellm: https://github.com/BerriAI/litellm
.. _litellm 文档: https://docs.litellm.ai/

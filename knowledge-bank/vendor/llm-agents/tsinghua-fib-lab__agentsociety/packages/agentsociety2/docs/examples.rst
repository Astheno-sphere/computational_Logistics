示例
========

本部分包含演示 AgentSociety 2 功能的示例代码。

运行示例
----------------

所有示例都位于 ``packages/agentsociety2/examples/`` 目录中。

**前提条件：**

1. 安装 AgentSociety 2: ``pip install agentsociety2``
2. 配置 LLM API 凭证（参见 :doc:`installation`）
3. 导航到示例目录

.. code-block:: bash

   cd packages/agentsociety2/examples
   python basics/01_hello_agent.py

基本示例
--------------

这些示例演示 AgentSociety 2 的基本概念：

**Hello Agent** (``basics/01_hello_agent.py``)

一个最小示例，展示：

* 创建具有个性配置文件的单个智能体
* 设置 SimpleSocialSpace 环境
* 使用 AgentSociety 协调智能体-环境交互

.. code-block:: python

   # Declare agent metadata (agents are created from specs during init)
   agent_specs = [
       {
           "id": 1,
           "profile": {
               "id": 1,
               "name": "Alice",
               "age": 28,
               "personality": "friendly, curious, optimistic",
               "bio": "A software engineer who loves hiking and reading.",
           },
           "config": {},
       }
   ]

   # Create environment and society
   society = AgentSociety(
       agent_specs=agent_specs,
       agent_class_name="PersonAgent",
       env_router=env_router,
       start_t=datetime.now(),
       run_dir=Path("run"),
   )
   await society.init()

   # Interact
   response = await society.ask("What's your favorite activity?")
   print(f"Agent: {response}")

**自定义环境模块** (``basics/02_custom_env_module.py``)

演示用 contrib 环境模块跑通 Ray 发现与干预：

* 使用内置 ``WeatherEnvironment``（``agentsociety2.contrib.env``），无需手写注册
* 通过 ``create_env_router_proxy`` 挂载环境（与 CLI / 生产路径一致）
* ``intervene`` 改天气后 ``ask`` 读回温度

**回放系统** (``basics/03_replay_system.py``)

展示全面的数据跟踪：

* 为环境模块启用 ReplayWriter
* 生成 replay catalog 和环境 replay dataset
* 结合 agent workspace 文件检查本地 thread / 工具日志

博弈论示例
---------------------

这些示例使用 contrib 下的博弈 agent / env，并通过 ``society.step()`` 推进回合。
需要配置 LLM 凭证（参见 :doc:`installation`）。

**囚徒困境** (``games/01_prisoners_dilemma.py``)

* ``PrisonersDilemmaAgent`` + ``PrisonersDilemmaEnv``
* 多轮同时决策（Cooperate / Defect）
* 结果写入 ``run_dir`` （含 env state 与 replay）

**公共物品博弈** (``games/02_public_goods.py``)

* ``PublicGoodsAgent`` + ``PublicGoodsEnv``
* 多名智能体多轮贡献决策

**声誉博弈** (``games/reputation_game.py``)

* ``LLMDonorAgent`` + ``ReputationGameEnv``
* 基于声誉的捐赠决策短跑示例

完整批量实验脚本见 ``packages/agentsociety2/experiments/env_main_*_v2.py``。

高级示例
-----------------

**自定义智能体** (``advanced/01_custom_agent.py``)

使用 contrib 智能体类型扩展 AgentSociety 2：

* 使用内置 ``SpecialistAgent``（``agentsociety2.contrib.agent``），Ray worker 可自动发现
* 以 ``agent_class_name="SpecialistAgent"`` 交给 ``AgentSociety``（无需手写 ``register_agent_module``）
* 通过 ``AgentSocietyHelper`` 的 ``get_agent_profile`` / ``ask_agents`` 查询与提问

**多路由器比较** (``advanced/02_multi_router.py``)

比较不同的推理策略：

* ReActRouter: 迭代推理和行动
* PlanExecuteRouter: 计划优先执行
* CodeGenRouter: 生成代码执行（推荐）

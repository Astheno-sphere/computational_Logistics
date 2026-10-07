与 AgentSociety 交互
==============================

本指南介绍如何在实验期间与 AgentSociety 2 交互。

概述
--------

AgentSociety 2 提供两种主要的交互模式：

1. **查询模式** (只读): 提问而不修改模拟状态
2. **干预模式** (读写): 修改智能体状态或环境变量

这些交互可以在以下时间执行：

* **模拟期间**: 在步骤之间或特定时间点
* **模拟后**: 查询最终状态或收集调查数据

交互模式对比
~~~~~~~~~~~~~~~~~

.. graphviz::

   digraph interaction_modes {
       rankdir=TB;
       node [shape=box, style=rounded];

       Society [label="AgentSociety"];
       Ask [label="ask() 方法", shape=ellipse];
       Intervene [label="intervene() 方法", shape=ellipse];

       subgraph cluster_ask {
           label = "查询模式";
           style=filled;
           color=lightgreen;
           Query [label="查询状态"];
           Read [label="只读操作"];
           NoModify [label="不修改环境"];
       }

       subgraph cluster_intervene {
           label = "干预模式";
           style=filled;
           color=lightcoral;
           Modify [label="修改状态"];
           Write [label="读写操作"];
           Change [label="改变环境"];
       }

       Society -> Ask;
       Society -> Intervene;
       Ask -> Query;
       Ask -> Read;
       Ask -> NoModify;
       Intervene -> Modify;
       Intervene -> Write;
       Intervene -> Change;
   }

基本交互模式
---------------------------

ask() 方法 - 只读查询
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

使用 ``society.ask()`` 进行不修改模拟的只读查询：

.. code-block:: python

   # Query about agent state
   response = await society.ask("What is Agent 1's current mood?")

   # Query about environment
   response = await society.ask("What is the current weather?")

   # Query about multiple agents
   response = await society.ask("List all agents who are unhappy")

intervene() 方法 - 读写修改
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

使用 ``society.intervene()`` 对模拟进行更改：

.. code-block:: python

   # Send a message to agents
   result = await society.intervene(
       "Send a message to all agents: 'Severe weather coming, go home!'"
   )

   # Modify environment variables
   result = await society.intervene(
       "Change the weather to rainy and temperature to 15°C"
   )

   # Modify agent states
   result = await society.intervene(
       "Set all agents' happiness to 0.8"
   )

模拟工作流程
-------------------

使用逐步控制运行
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from datetime import datetime

   # Create and initialize society（agent_specs + agent_class_name + env_router）
   society = AgentSociety(
       agent_specs=agent_specs,
       agent_class_name="PersonAgent",
       env_router=env_router,
       start_t=datetime.now(),
       run_dir=__import__("pathlib").Path("run"),
   )
   await society.init()

   # Run for specific number of steps
   for step_num in range(10):
       # Query before step
       state = await society.ask("What's happening?")
       print(f"Step {step_num}: {state}")

       # 执行一步（tick 为本步时长，秒）；当前仿真时间由编排器内部维护。
       # 任一 agent 返回 ok=False 时 society.step 抛出 RuntimeError（不再静默跳过）。
       await society.step(tick=3600)

       # Intervene based on conditions
       if "emergency" in state.lower():
           await society.intervene("Broadcast emergency alert")

   await society.close()

数据收集
---------------

收集智能体响应
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Collect responses from all agents（按 spec 的 id 提问）
   for spec in agent_specs:
       response = await society.ask(
           f"Agent {spec['id']}, how do you feel about the current situation?"
       )
       print(f"Agent {spec['id']}: {response}")
       # Store for analysis

   # Collect survey responses
   survey_questions = [
       "How satisfied are you with your current situation? (1-5)",
       "What would improve your quality of life?",
   ]

   for spec in agent_specs:
       for question in survey_questions:
           answer = await society.ask(f"Agent {spec['id']}: {question}")
           # Save answer to database or file

使用 ReplayWriter 进行环境数据收集
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from pathlib import Path

   # replay 默认开启，写入 run_dir/replay/；环境 replay dataset 自动记录
   society = AgentSociety(
       agent_specs=agent_specs,
       agent_class_name="PersonAgent",
       env_router=env_router,
       start_t=datetime.now(),
       run_dir=Path("run"),
       enable_replay=True,
   )
   await society.init()

   # Run simulation - environment replay datasets are recorded to sharded JSONL
   await society.run(num_steps=10, tick=3600)

   # Query replay catalog or environment tables later with ReplayReader
   # ReplayReader("run/replay").load_dataset_catalog()

   await society.close()

常见交互场景
-----------------------------

场景 1: 事件干预
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Normal simulation
   await society.run(num_steps=5, tick=3600)

   # Event occurs (e.g., hurricane)
   await society.intervene(
       "Broadcast: 'Hurricane warning! Seek shelter immediately!'"
   )

   # Continue simulation to observe reactions
   await society.run(num_steps=5, tick=3600)

   # Collect impact data
   impact = await society.ask("How did the hurricane affect everyone?")
   print(impact)

场景 2: 政策实验
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Control group - no policy（以 spec 声明，不实例化 agent）
   control_specs = [{"id": i, "profile": {...}, "config": {}} for i in range(1, 11)]
   control_society = AgentSociety(agent_specs=control_specs, agent_class_name="PersonAgent", ...)
   await control_society.init()
   await control_society.run(num_steps=10, tick=3600)

   # Treatment group - with policy intervention
   treatment_specs = [{"id": i + 10, "profile": {...}, "config": {}} for i in range(10)]
   treatment_society = AgentSociety(agent_specs=treatment_specs, agent_class_name="PersonAgent", ...)
   await treatment_society.init()

   # Implement policy
   await treatment_society.intervene(
       "Implement UBI policy: everyone receives $1000 monthly"
   )

   await treatment_society.run(num_steps=10, tick=3600)

   # Compare outcomes
   control_outcome = await control_society.ask("What's the average happiness?")
   treatment_outcome = await treatment_society.ask("What's the average happiness?")

场景 3: 多个时间点收集数据
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Baseline data
   baseline = await society.ask("Record everyone's baseline mood")

   # Intervention
   await society.intervene("Announce new community program")

   # Short-term effects
   await society.run(num_steps=3, tick=3600)
   short_term = await society.ask("How is everyone feeling now?")

   # Long-term effects
   await society.run(num_steps=10, tick=3600)
   long_term = await society.ask("How is everyone feeling now?")

   # Analyze change over time

外部提问（AgentSocietyHelper）
--------------------------------

``AgentSocietyHelper`` 对 ``society.ask`` / 研究侧提问使用 **XML** 计划与答案
（``<plan>`` / ``<answer>``），不再使用 JSON 计划格式。可用工具包括
``list_agents``、``get_agent_profile``、``ask_agents`` 等。详见 API
:class:`~agentsociety2.society.helper.AgentSocietyHelper`。

最佳实践
--------------

1. **对查询使用 ask()**: 只需要信息时始终使用 ``ask()``

2. **对更改使用 intervene()**: 只在想修改状态时使用 ``intervene()``

3. **结合 ReplayWriter**: 用环境 replay dataset 做实验分析；agent 本地调试则查看 ``run/agents/agent_xxxx/`` 下的 workspace 文件

4. **查询特定智能体**: 向特定智能体提问以获得有针对性的响应

5. **适时干预**: 在适当的模拟时间进行干预以获得现实效果

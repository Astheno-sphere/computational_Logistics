快速入门
===========

本指南将帮助您快速上手 AgentSociety 2。

前置条件
----------------

在运行示例前，请先配置 LLM 环境变量（见 :doc:`installation`），或在项目目录中准备好 ``.env`` 并在入口处尽早加载。

您的第一个智能体
----------------

使用 :class:`~agentsociety2.society.AgentSociety` 创建一个简单的智能体并与它交互。注意：智能体现在
以 **spec（元数据）** 的形式声明，由编排器在 ``init`` 时批量创建 workspace；不再直接 ``PersonAgent(...)``
实例化（见 :doc:`agents`）。

.. code-block:: python

   import asyncio
   from datetime import datetime
   from agentsociety2.env import CodeGenRouter
   from agentsociety2.contrib.env import SimpleSocialSpace
   from agentsociety2.society import AgentSociety

   async def main():
       # 1) 声明 agent 元数据（id / profile / config），不实例化 agent 对象
       agent_specs = [
           {
               "id": 1,
               "profile": {
                   "name": "Alice",
                   "age": 28,
                   "personality": "friendly and curious",
                   "bio": "A software engineer who loves hiking.",
               },
               "config": {},
           }
       ]
       names = [(s["id"], s["profile"]["name"]) for s in agent_specs]

       # 2) 创建环境模块 + 路由器（进程内 CodeGenRouter 即可；生产环境用 EnvRouterProxy）
       social_env = SimpleSocialSpace(agent_id_name_pairs=names)
       env_router = CodeGenRouter(env_modules=[social_env])

       # 3) 创建 society（agent_specs + agent_class_name + env_router）
       society = AgentSociety(
           agent_specs=agent_specs,
           agent_class_name="PersonAgent",
           env_router=env_router,
           start_t=datetime.now(),
           run_dir=__import__("pathlib").Path("run"),
       )

       # 4) 初始化（批量创建 agent workspace、绑定环境）
       await society.init()

       # 5) 只读查询
       response = await society.ask("What's your favorite activity?")
       print(f"Agent: {response}")

       await society.close()

   if __name__ == "__main__":
       asyncio.run(main())

运行此代码将产生类似以下输出：

.. code-block:: text

   Agent: I really love hiking! Being in nature, exploring new trails, and enjoying beautiful scenery brings a sense of peace.
   It's a great way to relax and stay energized.

创建自定义环境
--------------

环境模块允许智能体与特定功能进行交互：

.. code-block:: python

   import asyncio
   from datetime import datetime
   from pathlib import Path

   from agentsociety2.env import EnvBase, tool, CodeGenRouter
   from agentsociety2.society import AgentSociety

   class MyEnvironment(EnvBase):
       """A custom environment module."""

       @tool(readonly=True, kind="observe")
       def get_weather(self, agent_id: int) -> str:
           """Get current weather."""
           return "The weather is sunny, temperature 25°C."

       @tool(readonly=False)
       def set_mood(self, agent_id: int, mood: str) -> str:
           """Change agent's mood."""
           return f"Agent {agent_id}'s mood is now {mood}."

   async def main():
       agent_specs = [{"id": 1, "profile": {"name": "Bob"}, "config": {}}]
       env_router = CodeGenRouter(env_modules=[MyEnvironment()])
       society = AgentSociety(
           agent_specs=agent_specs,
           agent_class_name="PersonAgent",
           env_router=env_router,
           start_t=datetime.now(),
           run_dir=Path("run"),
       )
       await society.init()
       response = await society.ask("What's the weather like?")
       print(response)
       await society.close()

   if __name__ == "__main__":
       asyncio.run(main())

使用 CLI 运行实验
------------------

AgentSociety 2 提供了一个强大的 CLI 用于运行实验。

**前台运行（调试）:**

.. code-block:: bash

   python -m agentsociety2.society.cli \
       --config my_experiment/init/init_config.json \
       --steps my_experiment/init/steps.yaml \
       --run-dir my_experiment/run \
       --log-level DEBUG

**后台运行（生产）:**

.. code-block:: bash

   python -m agentsociety2.society.cli \
       --config my_experiment/init/init_config.json \
       --steps my_experiment/init/steps.yaml \
       --run-dir my_experiment/run \
       --log-level INFO \
       --log-file my_experiment/run/output.log &

**重要**: 后台运行时必须指定 ``--log-file`` 参数。

更多详情请参见 :doc:`cli`。

运行实验（代码方式）
--------------------

下面是一个使用 AgentSociety 2 的多智能体完整实验示例：

.. code-block:: python

   import asyncio
   from datetime import datetime
   from pathlib import Path
   from agentsociety2.env import CodeGenRouter
   from agentsociety2.contrib.env import SimpleSocialSpace
   from agentsociety2.society import AgentSociety

   async def main():
       # 1) 声明 agent 元数据
       agent_specs = [
           {"id": i, "profile": {"name": f"Player{i}", "personality": "competitive"}, "config": {}}
           for i in range(1, 4)
       ]
       names = [(s["id"], s["profile"]["name"]) for s in agent_specs]

       # 2) 环境路由器（replay 默认开启，写入 run_dir/replay/）
       env_router = CodeGenRouter(env_modules=[SimpleSocialSpace(agent_id_name_pairs=names)])

       # 3) 创建并初始化 society
       society = AgentSociety(
           agent_specs=agent_specs,
           agent_class_name="PersonAgent",
           env_router=env_router,
           start_t=datetime.now(),
           run_dir=Path("run"),
       )
       await society.init()

       # 4) 逐个询问（低频外部查询，在主进程内按需 from_workspace 重建目标 agent）
       for spec in agent_specs:
           response = await society.ask(
               f"Tell {spec['profile']['name']} to introduce themselves to the group!"
           )
           print(f"{spec['profile']['name']}: {response}")

       await society.close()

   if __name__ == "__main__":
       asyncio.run(main())

.. note::

   ``ReplayWriter`` 现在把 replay dataset 写入 ``run/replay/`` 的 sharded JSONL，
   并用 ``_schema.json`` 保存 catalog。``PersonAgent`` 的本地状态、thread 和工具日志
   会落在 ``run/agents/agent_xxxx/`` 目录，而不是旧 SQLite 的 ``agent_status`` /
   ``agent_profile`` 表。

下一步
----------

既然您已经掌握了基础知识，可以继续探索：

* :doc:`agents` - 详细了解智能体
* :doc:`env_modules` - 创建自定义环境模块
* :doc:`concepts` - 理解核心概念
* :doc:`architecture` - 系统架构与 Ray 执行模型
* :doc:`storage` - 了解回放系统
* :doc:`examples` - 查看更多示例

常见模式
---------------

只读查询
~~~~~~~~~~~~~~~~

对于不修改状态的查询，使用 ``society.ask()``：

.. code-block:: python

   # society.ask() ensures read-only access
   response = await society.ask("What agents are in the simulation?")

进行修改
~~~~~~~~~~~~~~

对于修改环境的操作，使用 ``society.intervene()``：

.. code-block:: python

   # society.intervene() allows environment modifications
   result = await society.intervene("Make everyone feel better")

查询特定智能体
~~~~~~~~~~~~~~~~~~~~~~~~~

向特定智能体提问：

.. code-block:: python

   # Ask a specific agent
   response = await society.ask(
       "Alice, what are your thoughts on the current situation?"
   )

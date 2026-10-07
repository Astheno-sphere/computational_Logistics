环境模块
===================

本部分介绍如何创建和使用环境模块。

创建自定义模块
------------------------

继承 EnvBase
~~~~~~~~~~~~~~~~~~~~

要创建自定义环境模块，请继承 ``EnvBase`` 并实现必需的方法：

需要实现的方法
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

创建自定义环境模块时，必须实现：

1. **async def step(self, tick: int, t: datetime) -> None**

   执行一个模拟步骤。在 AgentSociety 模拟期间自动调用。
   使用此方法更新时间相关的状态。

   参数:
       tick: 此步骤的持续时间（秒）
       t: 此步骤后的当前模拟日期时间

2. **使用 @tool 装饰的工具**

   使用 ``@tool`` 装饰器将方法公开为智能体的可调用函数。

   .. code-block:: python

      from agentsociety2.env import EnvBase, tool

      class MyModule(EnvBase):
          def __init__(self):
              super().__init__()
              # Your initialization

          @tool(readonly=True, kind="observe")
          def get_value(self, agent_id: int) -> str:
              """Get a value for an agent."""
              return f"Value for agent {agent_id}"

          @tool(readonly=False)
          def set_value(self, agent_id: int, value: int) -> str:
              """Set a value for an agent."""
              self._values[agent_id] = value
              return f"Set value for agent {agent_id}"

参考实现
^^^^^^^^^^^^^^^^^^^^^^^^

有关完整的参考实现，请参阅：

* ``SimpleSocialSpace`` - 社交互动模块
* ``PublicGoodsEnv`` - 公共物品博弈模块
* ``PrisonersDilemmaEnv`` - 囚徒困境模块

@tool 装饰器
~~~~~~~~~~~~~~~~~~~

``@tool`` 装饰器将方法标记为可被智能体调用：

.. code-block:: python

   from agentsociety2.env import tool

   @tool(readonly=True, kind="observe")
   def get_status(self, agent_id: int) -> str:
       """Get the status of an agent."""
       return f"Agent {agent_id} status"

参数：

* **readonly** (bool): 工具是否修改环境
  * ``True`` = 只读，可用于查询
  * ``False`` = 修改状态，可用于干预

* **kind** (str): 工具的类型
  * ``"observe"``: 单参数观察（需要 readonly=True）
  * ``"statistics"``: 聚合查询（无参数，需要 readonly=True）
  * ``None`` 或省略: 常规工具（任何签名，任何 readonly 值）

并发安全
~~~~~~~~~~

环境模块可覆盖类方法 ``is_concurrency_safe() -> bool``（默认 ``False``）：

* 返回 ``True``：工具只触达 per-agent / 已自带锁保护的状态，可与其它 ask 并行执行。
* 当**挂载的全部模块**都返回 ``True`` 时：

  * CLI / ``EnvRouterProxy`` 创建的 Ray actor 使用
    ``AGENTSOCIETY_ENV_ACTOR_MAX_CONCURRENCY``（默认 ``8``）作为 ``max_concurrency``；
  * ``CodeGenRouter`` 跳过全局 ``_execute_lock``，改依赖各模块本地锁。
* 任一模块不安全时，actor 退回 ``max_concurrency=1``，保证串行正确性。

工具类型
----------

* **observe**: 单参数观察（需要 readonly=True）
* **statistics**: 聚合查询（无参数，需要 readonly=True）
* **regular**: 任何其他工具（可以是只读或读写）

有关工具类型的更多详情，请参阅 :doc:`concepts`。

状态持久化与 resume
------------------------

如果模块带有动态内存态，例如计数器、收件箱或队列，可以实现 workspace 持久化，让仿真在中断后通过
``--resume`` 继续运行（详见 :doc:`cli`）。基类提供一对可覆盖的钩子，但**不规定状态格式、文件名或目录**。
模块可以自行选择布局；通常把状态写到 ``<workspace_root>/state/ENV_STATE.json``。

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - 方法
     - 作用
   * - ``async def to_workspace(self, workspace_path=None)``
     - 把动态状态写入 workspace。society 会在每步结束时通过 router 调用它。建议用
       ``agentsociety2.storage.workspace_state.atomic_write_text`` 原子写。
   * - ``async def restore(self, workspace_path) -> bool``
     - 从 workspace 恢复动态状态，用于 resume 路径。返回值表示是否加载到了快照，供 router 区分
       fresh 和 resume。该方法只会在 ``__init__`` 与 ``init()`` 之后调用，因此可以安全覆盖
       ``init()`` 里的重置。
   * - ``def _bind_workspace(self, workspace_path)``
     - 绑定到 workspace 目录（幂等），创建该目录。由 ``to_workspace``/``restore`` 自动调用。
   * - ``classmethod async def from_workspace(cls, workspace_path, **init_kwargs)``
     - 重建一个可用的模块：先执行 ``cls(**init_kwargs)``，再调用 ``restore``。resume 时，actor
       会从 ``SOCIETY.json`` 读取 ``init_kwargs``。

实现示例（参考 ``SimpleSocialSpace`` / ``EconomySpace`` / ``MobilitySpace``）：

.. code-block:: python

   import json
   import asyncio
   from agentsociety2.env import EnvBase, tool
   from agentsociety2.storage.workspace_state import atomic_write_text

   _STATE_REL = "state/ENV_STATE.json"

   class MyPersistentEnv(EnvBase):
       def __init__(self, capacity: int = 100):
           super().__init__()
           self.capacity = capacity          # 构造配置（在 env_kwargs，不存盘）
           self._resources: dict[int, float] = {}  # 动态态（存盘）
           self._lock = asyncio.Lock()       # 不存盘（由 __init__ 重建）

       @tool(readonly=False)
       def allocate(self, agent_id: int, amount: float) -> str:
           """Allocate resources."""
           self._resources[agent_id] = amount
           return f"Allocated {amount} to agent {agent_id}"

       async def to_workspace(self, workspace_path=None) -> None:
           if workspace_path is not None:
               self._bind_workspace(workspace_path)
           atomic_write_text(
               self._workspace_root / _STATE_REL,
               json.dumps(
                   {"resources": {str(k): v for k, v in self._resources.items()}},
                   ensure_ascii=False,
                   indent=2,
                   default=str,
               ),
           )

       async def restore(self, workspace_path) -> bool:
           self._bind_workspace(workspace_path)
           state_path = self._workspace_root / _STATE_REL
           if not state_path.is_file():
               return False
           d = json.loads(state_path.read_text(encoding="utf-8"))
           self._resources = {int(k): v for k, v in d.get("resources", {}).items()}
           return True

约定：

* JSON 键只能是字符串。``dict[int, ...]`` 应使用 ``str(k)`` 存、``int(k)`` 读，或用
  ``agentsociety2.env.base.dump_int_map``/``load_int_map`` 辅助。
* pydantic 模型用 ``model_dump(mode="json")`` 和 ``model_validate``；datetime 用
  ``isoformat``/``fromisoformat``；``set`` 存 ``sorted(list)``。
* ``asyncio.Lock``、外部子进程、预训练模型权重等不可或不必序列化的对象不存盘，由
  ``__init__``/``init()`` 重建（如 ``MobilitySpace`` 的 routing server、``SocialMediaSpace``
  的推荐器）。
* 持久化与 replay 表（``_agent_state_columns`` 和 ``_env_state_columns``）相互独立。replay 面向
  分析，是 append-only 的时序数据；workspace 面向恢复，会覆写最新状态。详见 :doc:`storage`。

注册模块
--------------------

.. code-block:: python

   from agentsociety2.env import CodeGenRouter

   router = CodeGenRouter()
   router.register_module(MyModule(), name="my_module")

   # Or with default name (class name)
   router.register_module(MyModule())

完整示例
-----------------

.. code-block:: python

   from typing import Dict
   from datetime import datetime
   from agentsociety2.env import EnvBase, tool, CodeGenRouter
   from agentsociety2 import PersonAgent
   from agentsociety2.society import AgentSociety

   class WeatherEnvironment(EnvBase):
       """A simple weather environment module."""

       def __init__(self):
           super().__init__()
           self._weather = "sunny"
           self._temperature = 25
           self._agent_locations: Dict[int, str] = {}

       @tool(readonly=True, kind="observe")
       def get_weather(self, agent_id: int) -> str:
           """Get the current weather for an agent's location."""
           location = self._agent_locations.get(agent_id, "unknown")
           return f"The weather in {location} is {self._weather} with {self._temperature}°C."

       @tool(readonly=False)
       def change_weather(self, weather: str, temperature: int) -> str:
           """Change the weather conditions."""
           self._weather = weather
           self._temperature = temperature
           return f"Weather changed to {weather} at {temperature}°C."

       async def step(self, tick: int, t: datetime) -> None:
           """Update environment state for one simulation step."""
           self.t = t
           # Update time-dependent state here if needed

   # Use the custom module（agent 以 spec 声明，不实例化）
   env_router = CodeGenRouter(env_modules=[WeatherEnvironment()])

   agent_specs = [{"id": 1, "profile": {"name": "Bob"}, "config": {}}]

   society = AgentSociety(
       agent_specs=agent_specs,
       agent_class_name="PersonAgent",
       env_router=env_router,
       start_t=datetime.now(),
       run_dir=__import__("pathlib").Path("run"),
   )
   await society.init()

.. note::

   生产环境下环境路由跑在一个专用的 Ray actor 里（``EnvRouterProxy``），所有 agent 共享一份
   环境状态；也可在进程内直接用 ``CodeGenRouter``。除默认的 ``CodeGenRouter`` 外还有
   ``ReActRouter`` / ``PlanExecuteRouter`` / ``TwoTierReActRouter`` / ``TwoTierPlanExecuteRouter``
   / ``SearchToolRouter`` 可选（见 :doc:`architecture`）。

示例
--------

请参阅 ``agentsociety2.contrib.env`` 中的内置环境类（类名以当前代码为准）：

* ``SimpleSocialSpace`` — 社交互动
* ``WeatherEnvironment`` — 天气查询 / 干预（onboarding 见 ``examples/basics/02_custom_env_module.py``）
* ``PublicGoodsEnv`` — 公共物品博弈
* ``PrisonersDilemmaEnv`` — 囚徒困境
* ``TrustGameEnv`` — 信任博弈

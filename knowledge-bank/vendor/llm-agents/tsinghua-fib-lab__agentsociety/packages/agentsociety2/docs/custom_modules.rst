自定义模块
==============

AgentSociety 2 支持创建和注册自定义智能体和环境模块，
允许您使用自己的模拟组件扩展平台。

概述
--------

自定义模块系统允许您：

* 创建具有专门行为的自定义智能体类
* 创建具有特定领域工具的自定义环境模块
* 通过 API 自动发现和注册模块
* 使用自动生成的测试脚本测试自定义模块
* 与现有 AgentSociety 框架无缝集成
* 通过 Progressive Disclosure workflow 持久化需求、设计和验证产物

目录结构
-------------------

自定义模块放置在工作区内的 ``custom/`` 目录中::

   workspace/
   ├── custom/                    # User-created directory
   │   ├── agents/                # Custom agent classes
   │   │   └── my_agent.py
   │   └── envs/                  # Custom environment modules
   │       └── my_env.py
   └── .agentsociety/             # Auto-generated configuration
       ├── agent_classes/
       ├── env_modules/
       └── custom_env_skill/
           └── runs/

创建自定义智能体
-------------------------

所有自定义智能体必须继承 ``AgentBase``。智能体是 workspace 绑定的无状态 record：状态在
``restore()`` 里恢复、在 ``to_workspace()`` 里写回；详见 :doc:`agents`。

.. code-block:: python

   from pathlib import Path
   from agentsociety2.agent.base import AgentBase
   from datetime import datetime
   from typing import Any

   class MyAgent(AgentBase):
       """My custom Agent"""

       @classmethod
       def mcp_description(cls) -> str:
           return """MyAgent: A custom agent for specific tasks

       This agent demonstrates custom behavior.
       """

       async def restore(self, workspace_path: Path, service_proxy: Any) -> None:
           """恢复 workspace / 服务 / 技能，再追加自定义状态。"""
           await super().restore(workspace_path, service_proxy)
           self._custom_state: dict = {}

       async def ask(self, message: str, readonly: bool = True, *, t=None) -> str:
           """Respond to questions from the environment"""
           prompt = f"Question: {message}\nPlease answer:"
           response = await self.acompletion([{"role": "user", "content": prompt}])
           return response.choices[0].message.content or ""

       async def step(self, tick: int, t: datetime) -> str:
           """Execute one simulation step"""
           return f"Agent {self.id} executing step {tick}"

       async def to_workspace(self, workspace_path: Path) -> None:
           """把动态状态写回 workspace（AGENT.json 等）。"""
           self.persist_agent_json(tick=None, t=self._current_time)

必需方法
~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Method
     - Description
   * - ``mcp_description()``
     - 返回模块描述（类方法，建议覆盖；``AgentBase``/``EnvBase`` 有默认描述）
   * - ``ask()``
     - 回答环境的问题（必须实现）
   * - ``step()``
     - 执行一个模拟步骤（必须实现）
   * - ``to_workspace()``
     - 把动态状态写回 workspace（必须实现）
   * - ``restore()``
     - 在 ``await super().restore(...)`` 之后恢复自定义状态（推荐覆盖）

创建自定义环境
------------------------------

自定义环境必须继承 ``EnvBase`` 并使用 ``@tool`` 装饰器注册方法：

.. code-block:: python

   from agentsociety2.env import EnvBase, tool
   from datetime import datetime

   class MyEnv(EnvBase):
       """My custom environment"""

       def __init__(self, config=None):
           super().__init__()
           # Initialize your environment state

       @classmethod
       def mcp_description(cls) -> str:
           return """MyEnv: A custom environment

       This environment provides custom tools for agents.
       """

       @tool(readonly=True, kind="observe")
       async def get_state(self, agent_id: int) -> dict:
           """Get current environment state (observation tool)"""
           return {"agent_id": agent_id, "state": "normal"}

       @tool(readonly=False)
       async def do_action(self, agent_id: int, action: str) -> dict:
           """Perform an action (modification tool)"""
           return {"agent_id": agent_id, "action": action, "result": "success"}

       async def step(self, tick: int, t: datetime):
           """Environment step"""
           self.t = t

       async def to_workspace(self, workspace_path=None) -> None:
           """把动态状态写入 workspace；覆盖此方法可支持 resume，详见 :doc:`env_modules`。"""
           if workspace_path is not None:
               self._bind_workspace(workspace_path)

       async def restore(self, workspace_path) -> bool:
           """从 workspace 恢复动态状态；resume 时调用，默认返回 False。"""
           self._bind_workspace(workspace_path)
           return False

现实兼容约束
~~~~~~~~~~~~~~~~~~~

生成的自定义环境模块仍然必须遵循当前仓库的真实兼容约束：

* 文件必须位于 ``custom/envs/*.py``
* 类定义必须直接位于该文件中，不能只做 re-export
* 注册 key 继续使用 ``class_name``
* 至少存在一个合法 ``@tool``
* ``step()`` 必须存在
* 默认应支持无参实例化 ``cls()``
* 若模块需要观察能力，应提供 ``@tool(readonly=True, kind='observe')`` 观察工具
* 建议提供信息完整的 ``mcp_description()`` ；未覆盖时会显示基类默认描述
* 若模块带动态内存态且希望支持中断续跑，应覆盖 ``to_workspace`` 和 ``restore``。使用
  ``--resume`` 时，模块应能从 ``state/ENV_STATE.json`` 恢复状态（见 :doc:`env_modules` 的
  「状态持久化与 resume」）。

.. note::

   扫描器会跳过路径中包含 ``examples/`` 的文件（示例仅供参考，不参与注册）。

@tool 装饰器
~~~~~~~~~~~~~~~~~~~

``@tool`` 装饰器将方法注册为智能体可访问的工具：

.. list-table::
   :header-rows: 1

   * - Parameter
     - Description
   * - ``readonly=True``
     - 工具不修改环境状态
   * - ``readonly=False``
     - 工具可以修改环境状态
   * - ``kind="observe"``
     - 观察工具（单个 agent_id 参数，readonly=True）
   * - ``kind="statistics"``
     - 统计工具（无参数，readonly=True）
   * - ``kind=None``
     - 常规工具（任何参数，可以是 readonly=False）

注册自定义模块
---------------------------

创建自定义模块后，使用 API 注册它们：

**扫描并注册**

.. code-block:: bash

   curl -X POST http://localhost:8001/api/v1/custom/scan \
     -H "Content-Type: application/json" \
     -d '{"workspace_path": "/path/to/workspace"}'

**列出已注册的模块**

.. code-block:: bash

   curl http://localhost:8001/api/v1/custom/list

**测试自定义模块**

.. code-block:: bash

   curl -X POST http://localhost:8001/api/v1/custom/test \
     -H "Content-Type: application/json" \
     -d '{"workspace_path": "/path/to/workspace"}'

**创建或恢复 workflow run**

.. code-block:: bash

   curl -X POST http://localhost:8001/api/v1/custom/workflow/runs \
     -H "Content-Type: application/json" \
     -d '{"workspace_path": "/path/to/workspace", "user_request": "create a resource env"}'

**验证 workflow run**

.. code-block:: bash

   curl -X POST http://localhost:8001/api/v1/custom/workflow/runs/<run_id>/validate \
     -H "Content-Type: application/json" \
     -d '{"module_path": "custom/envs/my_env.py", "class_name": "MyEnv"}'

API 端点
~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Endpoint
     - Method
     - Description
   * - ``/api/v1/custom/scan``
     - POST
     - 扫描并注册自定义模块
   * - ``/api/v1/custom/test``
     - POST
     - 测试自定义模块
   * - ``/api/v1/custom/clean``
     - POST
     - 清理自定义模块配置
   * - ``/api/v1/custom/list``
     - GET
     - 列出已注册的自定义模块
   * - ``/api/v1/custom/status``
     - GET
     - 获取模块状态概述
   * - ``/api/v1/custom/workflow/runs``
     - POST
     - 创建或恢复自定义环境 workflow run
   * - ``/api/v1/custom/workflow/runs/{run_id}/validate``
     - POST
     - 执行 scanner/tester/registry 的端到端校验

示例
--------

示例智能体和环境可在 ``custom/`` 目录中找到：

* ``custom/agents/examples/simple_agent.py`` - 基本智能体示例
* ``custom/agents/examples/advanced_agent.py`` - 具有记忆和情绪的智能体
* ``custom/envs/examples/simple_env.py`` - 计数器环境
* ``custom/envs/examples/advanced_env.py`` - 资源管理环境

这些示例演示了创建自定义模块的最佳实践。

配置
-------------

设置 ``WORKSPACE_PATH`` 环境变量以指向您的工作区：

.. code-block:: bash

   export WORKSPACE_PATH=/path/to/workspace

或添加到您的 ``.env`` 文件：

.. code-block:: ini

   WORKSPACE_PATH=/path/to/workspace

此设置告诉系统在哪里找到 ``custom/`` 目录。

最佳实践
--------------

**命名约定**

* 智能体类名应以 ``Agent`` 结尾
* 环境类名应以 ``Env`` 结尾
* 文件名应使用小写字母和下划线：``my_agent.py``

**错误处理**

* 返回有意义的错误消息
* 对关键路径保留必要日志，便于复盘与定位问题

**状态管理**

* 使用 ``restore()`` 从 workspace 恢复状态，使用 ``to_workspace()`` 写回动态状态
* 自定义 Agent 覆盖 ``restore()`` 时应先调用 ``await super().restore(...)``，以绑定 workspace、技能运行时和服务句柄
* 在回放中记录重要的状态更改
* 保持状态可序列化（JSON 兼容）

**工具设计**

* 对只读观察使用 ``kind="observe"``
* 对聚合数据使用 ``kind="statistics"``
* 对操作使用 ``kind=None`` 和 ``readonly=False``
* 生成后优先通过 workflow 产物中的 ``validation_report.json`` 定位失败原因

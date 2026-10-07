核心概念
=============

本部分说明 AgentSociety 2 的系统结构与术语；首页 :doc:`index` 中的「研究背景与平台定位」从范式与协作角度概括了平台动机，此处侧重实现层面的组件关系。

架构概述
---------------------

AgentSociety 2 围绕三个主要组件构建：

* **智能体 (Agents)**: 使用 LLM 与环境交互的自主实体（workspace 绑定的无状态 record，由 Ray Task 流式驱动）
* **环境模块 (Environment Modules)**: 定义模拟规则的可组合组件
* **AgentSociety**: 管理智能体和环境的协调器

智能体不直接持有 env / LLM / trace / replay 等运行时对象，而是经一个 ``ServiceProxy`` 容器接收共享
服务句柄；环境路由跑在专用 Ray actor 里。详见 :doc:`architecture`。

**中断恢复**：agent、env 模块和 society 三层都会把恢复所需的状态原子写入 workspace。agent 使用
``AGENT.json``，env 模块通常使用 ``state/ENV_STATE.json``，society 使用不可变的
``SOCIETY.json`` 和每步更新的 ``SOCIETY_STEP.json``。CLI 的 ``--resume`` 可以从中断处继续运行
实验（详见 :doc:`cli`）。这一机制与 replay 相互独立；replay 是面向分析的 append-only 时序数据
（见 :doc:`storage`）。

.. graphviz::

   digraph agentsociety2 {
       rankdir=TB;
       node [shape=box, style=rounded];

       Agent [label="Agent"];
       CodeGenRouter [label="CodeGenRouter"];
       EnvModule [label="Env Module"];
       Tool [label="@tool()"];

       Agent -> CodeGenRouter [label="ask/intervene"];
       CodeGenRouter -> EnvModule [label="calls tools"];
       EnvModule -> Tool [label="decorated with"];
   }

完整系统架构
~~~~~~~~~~~~~~~~~

.. graphviz::

   digraph full_architecture {
       rankdir=TB;
       node [shape=box, style=rounded];
       edge [fontsize=10];

       subgraph cluster_ui {
           label = "用户界面层";
           style=filled;
           color=lightgrey;
           CLI [label="CLI 命令行"];
           WebUI [label="Web 前端"];
           API [label="REST API"];
       }

       subgraph cluster_core {
           label = "核心模拟层";
           style=filled;
           color=lightblue;
           Society [label="AgentSociety\n协调器 (driver)"];
           Router [label="Router\n(EnvRouterActor)"];
           Storage [label="ReplayWriter (Actor)\n/ Workspace 存储"];
           Trace [label="Trace Actor\n(sharded writer)"];
       }

       subgraph cluster_agents {
           label = "智能体层 (无状态 record, Ray Task 流式)";
           style=filled;
           color=lightgreen;
           Proxy [label="ServiceProxy\n(env/llm/trace/replay)", shape=note];
           Agent1 [label="PersonAgent 1"];
           Agent2 [label="PersonAgent 2"];
           AgentN [label="... PersonAgent N"];
       }

       subgraph cluster_env {
           label = "环境层";
           style=filled;
           color=lightyellow;
           Env1 [label="SocialSpace"];
           Env2 [label="EconomySpace"];
           EnvN [label="... 自定义模块"];
       }

       subgraph cluster_external {
           label = "外部服务";
           style=filled;
           color=lavender;
           LLM [label="LLM Client\n(per-process dispatcher)"];
       }

       CLI -> Society;
       WebUI -> API;
       API -> Society;

       Society -> Router;
       Society -> Storage;
       Society -> Trace;
       Society -> Proxy;

       Proxy -> Agent1;
       Proxy -> Agent2;
       Proxy -> AgentN;

       Router -> Env1;
       Router -> Env2;
       Router -> EnvN;

       Agent1 -> Router [label="ask_env"];
       Agent2 -> Router;
       AgentN -> Router;

       Agent1 -> LLM [label="dispatcher"];
       Society -> LLM;
   }

智能体-环境接口
----------------------------

智能体通过两个主要方法与环境交互：

* **ask()**: 查询或观察环境状态
* **intervene()**: 修改环境状态

这个统一接口允许智能体与任何环境模块自然通信。

@tool 装饰器
-------------------

环境模块通过 ``@tool`` 装饰器公开其功能：

.. code-block:: python

   from agentsociety2.env import EnvBase, tool

   class MyEnvironment(EnvBase):
       @tool(readonly=True, kind="observe")
       def get_weather(self, agent_id: int) -> str:
           """Get current weather for agent."""
           return f"Weather for agent {agent_id}"

       @tool(readonly=False)
       def set_temperature(self, temp: int) -> str:
           """Set temperature."""
           self._temperature = temp
           return f"Temperature set to {temp}"

**参数：**

* ``readonly`` (bool): 函数是否修改状态
  * ``True`` = 只读观察
  * ``False`` = 修改环境

* ``kind`` (str): 用于优化的函数类别
  * ``"observe"``: 单参数观察
  * ``"statistics"``: 聚合查询（无参数）
  * ``None``: 常规工具

CodeGenRouter
-------------

CodeGenRouter 通过以下方式将智能体连接到环境模块：

1. 从环境模块中提取工具签名
2. 根据智能体输入生成调用适当工具的代码
3. 在沙盒环境中安全执行代码
4. 将结果返回给智能体

这种方法允许智能体与任何环境模块组合交互，而无需更改代码。

路由器选择
~~~~~~~~~~~~

``RouterBase`` 有多个实现，可按需替换：

* ``CodeGenRouter`` （默认）：生成调用代码并在沙盒执行，带 AST 守卫；
  FAISS 指令模板缓存**仅在** ``ask(..., template_mode=True)`` 时生效；
  若模块未声明 observe/statistics 工具，init 会跳过对应 LLM 代码生成。
* ``ReActRouter``：ReAct 式工具选择。
* ``PlanExecuteRouter``：先规划再执行。
* ``TwoTierReActRouter`` / ``TwoTierPlanExecuteRouter``：两级路由，适合大工具集。
* ``SearchToolRouter``：以检索方式选择工具。

生产环境下路由跑在专用 Ray actor（``EnvRouterProxy``）里；actor 并发由模块
``is_concurrency_safe()`` 决定，详见 :doc:`architecture` 与 :doc:`env_modules`。

工具类别
---------------

**观察工具** (``readonly=True``, ``kind="observe"``)

具有单个 ``agent_id`` 参数的智能体特定观察：

.. code-block:: python

   @tool(readonly=True, kind="observe")
   def get_agent_location(self, agent_id: int) -> str:
       """Get current location of agent."""
       return f"Agent {agent_id} is at location X"

**统计工具** (``readonly=True``, ``kind="statistics"``)

没有参数的聚合查询（除了 ``self``）：

.. code-block:: python

   @tool(readonly=True, kind="statistics")
   def get_average_happiness(self) -> str:
       """Get average happiness of all agents."""
       avg = sum(self.happiness.values()) / len(self.happiness)
       return f"Average happiness: {avg}"

**常规工具**

具有任何签名的通用工具：

.. code-block:: python

   @tool(readonly=False)
   def set_happiness(self, agent_id: int, value: float) -> str:
       """Set happiness level for agent."""
       self.happiness[agent_id] = value
       return f"Set agent {agent_id}'s happiness to {value}"

工具类别层次结构
~~~~~~~~~~~~~~~~~

.. graphviz::

   digraph tool_hierarchy {
       rankdir=TB;
       node [shape=box, style=rounded];

       Root [label="@tool 装饰器", shape=ellipse];

       Readonly [label="readonly=True", shape=diamond];
       Readwrite [label="readonly=False", shape=diamond];

       Observe [label="观察工具（kind=observe）\n单参数 agent_id"];
       Statistics [label="统计工具（kind=statistics）\n除 self 外无参数"];
       Regular [label="常规工具（readonly=False）\n任意签名"];

       Root -> Readonly;
       Root -> Readwrite;

       Readonly -> Observe;
       Readonly -> Statistics;
       Readwrite -> Regular;
   }

智能体-环境交互流程
~~~~~~~~~~~~~~~~~~~~

.. graphviz::

   digraph interaction_flow {
       rankdir=TB;
       node [shape=box, style=rounded];

       Agent [label="智能体"];
       Ask [label="ask/intervene()"];
       Router [label="Router"];
       Tools [label="@tool 方法"];
       Env [label="环境状态"];
       Response [label="响应"];

       Agent -> Ask;
       Ask -> Router;
       Router -> Tools [label="提取工具签名"];
       Router -> Tools [label="生成调用代码"];
       Tools -> Env [label="执行工具"];
       Env -> Tools [label="返回结果"];
       Tools -> Router;
       Router -> Response;
       Response -> Agent;
   }

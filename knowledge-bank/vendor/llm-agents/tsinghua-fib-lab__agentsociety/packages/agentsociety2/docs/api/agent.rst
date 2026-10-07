Agent 模块
==========

本模块提供智能体的核心类和数据模型。

核心类
------

AgentBase
~~~~~~~~~

.. autoclass:: agentsociety2.agent.base.AgentBase
   :members:
   :undoc-members:
   :show-inheritance:

PersonAgent
~~~~~~~~~~~

.. autoclass:: agentsociety2.agent.person.PersonAgent
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

``AgentBase`` 直接拥有 workspace 绑定、技能运行时、ReAct 工具循环、TODO 状态、trace 与
``AGENT.json`` 持久化等通用能力。``PersonAgent`` 是其上的薄编排器，只实现面向人物的行为逻辑。
智能体不再通过 ``__init__`` 传参构造，而是经 ``AgentBase.create()`` 写一次 workspace、再经
``await AgentBase.from_workspace(path, service_proxy)`` 重建（详见 :doc:`/agents`）。

如果只是扩展人物行为，优先新增或修改 Agent Skill（见 :doc:`/agent_skills`，API 参考见
:doc:`/api/skills`）；只有需要改变智能体生命周期、状态机或外部系统调用方式时，才继承
``AgentBase`` / ``PersonAgent`` 创建新类。

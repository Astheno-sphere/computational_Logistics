"""AgentSociety 2 - 现代化的 LLM-native 智能体仿真平台。

本包提供构建和仿真 LLM 驱动智能体的工具，用于社会科学研究。

主要组件
--------

**Agent 模块**:
- ``AgentBase``: 智能体抽象基类
- ``PersonAgent``: skills-first 智能体

**Env 模块**:
- ``EnvBase``: 环境模块基类
- ``RouterBase``: 路由器基类
- ``ReActRouter``: ReAct 范式路由器
- ``PlanExecuteRouter``: 计划-执行路由器
- ``CodeGenRouter``: 代码生成路由器
- ``TwoTierReActRouter``: 两层 ReAct 路由器
- ``TwoTierPlanExecuteRouter``: 两层计划执行路由器
- ``SearchToolRouter``: 搜索工具路由器
- ``tool``: 工具装饰器

**Society 模块**:
- ``AgentSociety``: 主模拟编排器（位于 ``agentsociety2.society``）
- ``AgentSocietyHelper``: 模拟编排助手（顶层 re-export）

**Storage 模块**:
- ``ReplayWriter``: 环境回放数据写入器

使用示例::

    from agentsociety2 import AgentBase, PersonAgent, EnvBase, tool
    from agentsociety2.society import AgentSociety

    # 定义自定义环境
    class MyEnv(EnvBase):
        @tool(readonly=True)
        def get_status(self) -> str:
            return "ok"

    # 定义自定义智能体
    class MyAgent(AgentBase):
        async def step(self, tick: int, t) -> str:
            return "done"
        # ... 其他抽象方法
"""

from __future__ import annotations

import os

os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"

__version__ = "2.9.3"

# Import main components for easy access
from .agent import AgentBase, PersonAgent
from .env import (
    CodeGenRouter,
    EnvBase,
    PlanExecuteRouter,
    ReActRouter,
    RouterBase,
    SearchToolRouter,
    TwoTierPlanExecuteRouter,
    TwoTierReActRouter,
    tool,
)
from .society import AgentSocietyHelper
from .storage import ReplayWriter

__all__ = [
    "AgentBase",
    "AgentSocietyHelper",
    "CodeGenRouter",
    "EnvBase",
    "PersonAgent",
    "PlanExecuteRouter",
    "ReActRouter",
    "ReplayWriter",
    "RouterBase",
    "SearchToolRouter",
    "TwoTierPlanExecuteRouter",
    "TwoTierReActRouter",
    "tool",
]

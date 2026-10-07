"""
自定义 Agent 包

在此目录下创建自定义 Agent 类。
"""

from agentsociety2.agent.base import AgentBase

# 动态加载所有自定义 Agent
# 注意：此文件由系统自动维护，请勿手动编辑

_CUSTOM_AGENTS: list[tuple[str, type[AgentBase]]] = []


def register_agent(agent_type: str, agent_class: type[AgentBase]):
    """注册自定义 Agent"""
    _CUSTOM_AGENTS.append((agent_type, agent_class))


def get_custom_agents() -> list[tuple[str, type[AgentBase]]]:
    """获取所有自定义 Agent"""
    return _CUSTOM_AGENTS.copy()


__all__ = ["get_custom_agents", "register_agent"]

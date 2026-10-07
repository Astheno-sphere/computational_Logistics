"""模块初始化与后端请求的数据模型（Pydantic）。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

__all__ = [
    "AgentInitConfig",
    "AskRequest",
    "CreateInstanceRequest",
    "EnvModuleInitConfig",
    "InterventionRequest",
]


class EnvModuleInitConfig(BaseModel):
    """环境模块初始化配置。"""

    module_type: str = Field(
        ...,
        description="The type of environment module (e.g., 'global_information', 'economy_space', 'social_space', 'mobility_space')",
    )

    args: dict[str, Any] = Field(
        default_factory=dict,
        description="Module initialization arguments (excluding llm). These arguments are passed directly to the module constructor. See init_description() for the module's expected parameters and JSON schemas.",
    )


class AgentInitConfig(BaseModel):
    """agent 初始化配置。"""

    agent_type: str = Field(
        ..., description="The type of agent (e.g., 'person_agent', 'custom_agent')"
    )

    agent_id: int = Field(..., description="Unique ID for the agent")

    args: dict[str, Any] = Field(
        default_factory=dict,
        description="Agent initialization arguments (excluding llm and env which are set via init() method). All other parameters including 'id', 'profile', 'memory_config', etc. should be included here. See init_description() for the agent's expected parameters.",
    )


class CreateInstanceRequest(BaseModel):
    """创建 AgentSociety 实例的请求体。"""

    instance_id: str = Field(
        ..., description="Unique identifier for this society instance"
    )

    env_modules: list[EnvModuleInitConfig] = Field(
        ..., min_length=1, description="List of environment modules to initialize"
    )

    agents: list[AgentInitConfig] = Field(
        ..., min_length=1, description="List of agents to initialize"
    )

    start_t: datetime = Field(..., description="Simulation start time")

    tick: int = Field(
        1, ge=1, description="Tick duration in seconds for run operations"
    )


class AskRequest(BaseModel):
    """对实例进行 ask 的请求体。"""

    instance_id: str = Field(..., description="The ID of the society instance")

    question: str = Field(..., description="The question to ask")


class InterventionRequest(BaseModel):
    """对实例进行 intervene 的请求体。"""

    instance_id: str = Field(..., description="The ID of the society instance")

    instruction: str = Field(..., description="The intervention instruction")

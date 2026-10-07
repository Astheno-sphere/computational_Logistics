from typing import Any, Awaitable, Callable, List, Optional, Union
import uuid

from pydantic import BaseModel, Field, field_serializer

from ..environment import MapConfig
from ..llm import LLMConfig
from .agent import AgentConfig, InstitutionAgentClass
from .env import EnvConfig
from .exp import (
    AgentFilterConfig,
    EnvironmentConfig,
    ExpConfig,
    WorkflowStepConfig,
    WorkflowType,
)
from ..taskloader import Task
from .utils import load_config_from_file

__all__ = [
    "EnvConfig",
    "AgentConfig",
    "WorkflowStepConfig",
    "ExpConfig",
    "EnvironmentConfig",
    "Config",
    "load_config_from_file",
    "InstitutionAgentClass",
    "WorkflowType",
    "AgentFilterConfig",
    "TaskLoaderConfig",
    "IndividualConfig",
]


class AgentsConfig(BaseModel):
    """Configuration for different types of agents in the simulation."""

    citizens: list[AgentConfig] = Field(..., min_length=1)
    """Citizen Agent configuration"""

    firms: list[AgentConfig] = Field(default=[])
    """Firm Agent configuration"""

    banks: list[AgentConfig] = Field(default=[])
    """Bank Agent configuration"""

    nbs: list[AgentConfig] = Field(default=[])
    """NBS Agent configuration"""

    governments: list[AgentConfig] = Field(default=[])
    """Government Agent configuration"""

    supervisor: Optional[AgentConfig] = Field(None)
    """Supervisor Agent configuration"""

    init_funcs: list[Callable[[Any], Union[None, Awaitable[None]]]] = Field([])
    """Initialization functions for simulation, the only one argument is the AgentSociety object"""

    @field_serializer("init_funcs")
    def serialize_init_funcs(self, init_funcs, info):
        return [func.__name__ for func in init_funcs]


class Config(BaseModel):
    """Configuration for the simulation."""

    llm: List[LLMConfig] = Field(..., min_length=1)
    """List of LLM configurations"""

    env: EnvConfig
    """Environment configuration"""

    map: MapConfig
    """Map configuration"""

    agents: AgentsConfig
    """Configuration for different types of agents in the simulation."""

    exp: ExpConfig
    """Experiment configuration"""

    logging_level: str = Field("INFO")
    """Logging level"""


class TaskLoaderConfig(BaseModel):
    """Configuration for the task loader."""

    task_type: type[Task]
    """Task type"""

    file_path: str
    """File path"""

    shuffle: bool = Field(default=False)
    """Shuffle the tasks"""


class IndividualConfig(BaseModel):
    """Configuration for the individual."""
    name: str = Field("default_individual")
    """Name of the solver"""

    llm: List[LLMConfig] = Field(..., min_length=1)
    """List of LLM configurations"""

    env: EnvConfig
    """Environment configuration"""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    """Unique identifier for the individual"""

    individual: AgentConfig
    """Individual Agent configuration"""

    task_loader: TaskLoaderConfig
    """Task loader configuration"""

    logging_level: str = Field("INFO")
    """Logging level"""

    @field_serializer("id")
    def serialize_id(self, id, info):
        return str(id)

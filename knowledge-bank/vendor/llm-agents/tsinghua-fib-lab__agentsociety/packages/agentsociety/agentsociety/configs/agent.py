from collections.abc import Callable
from enum import Enum
from typing import Any, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from ..agent import Agent, Block, CustomTool
from ..agent.distribution import Distribution, DistributionConfig

__all__ = [
    "AgentConfig",
]


class InstitutionAgentClass(str, Enum):
    """
    Defines the types of institution agent class types.
    """

    FIRM = "firm"
    GOVERNMENT = "government"
    BANK = "bank"
    NBS = "nbs"


class AgentConfig(BaseModel):
    """Configuration for different types of agents in the simulation."""

    model_config = ConfigDict(
        use_enum_values=True,
        use_attribute_docstrings=True,
        arbitrary_types_allowed=True,
    )

    agent_class: Union[type[Agent], str]
    """The class of the agent"""

    number: int = Field(default=1, ge=0)
    """The number of agents."""

    agent_params: Optional[Any] = None
    """Agent configuration"""

    blocks: Optional[dict[Union[type[Block], str], Any]] = None
    """Blocks configuration"""

    tools: Optional[list[CustomTool]] = Field(default=[])
    """Tools configuration"""

    # Choose one of the following:
    # 1. memory_config_func: Optional[Callable] = None
    # 2. memory_from_file: Optional[str] = None
    # 3. memory_distributions: Optional[dict[str, DistributionConfig]] = None

    memory_config_func: Optional[Callable] = None
    """Memory configuration function"""

    memory_from_file: Optional[str] = None
    """Memory configuration file. If s3 is enabled, the file will be downloaded from S3"""

    memory_distributions: Optional[
        dict[str, Union[Distribution, DistributionConfig]]
    ] = None
    """Memory distributions. Required when using number, ignored when using memory_from_file."""

    @model_validator(mode="after")
    def validate_configuration(self):
        """Validate configuration options to ensure the user selects the correct combination"""
        memory_from_file = self.memory_from_file
        number = self.number
        memory_distributions = self.memory_distributions

        if memory_from_file is not None:
            # When using file method, memory_distributions should not be set
            if memory_distributions is not None:
                raise ValueError(
                    "When using memory_from_file, memory_distributions should not be set"
                )
        else:
            # When not using file method, both number must be set
            if number is None:
                raise ValueError("When not using memory_from_file, number must be set")

        return self

    @field_serializer("agent_class")
    def serialize_agent_class(self, agent_class, info):
        if isinstance(agent_class, str):
            return agent_class
        else:
            return agent_class.__name__

    @field_serializer("memory_config_func")
    def serialize_memory_config_func(self, memory_config_func, info):
        if memory_config_func is None:
            return None
        else:
            return memory_config_func.__name__

    @field_serializer("memory_distributions")
    def serialize_memory_distributions(self, memory_distributions, info):
        if memory_distributions is None:
            return None
        else:
            result = {}
            for key, value in memory_distributions.items():
                if isinstance(value, Distribution):
                    result[key] = value.__repr__()
                else:
                    result[key] = value
            return result

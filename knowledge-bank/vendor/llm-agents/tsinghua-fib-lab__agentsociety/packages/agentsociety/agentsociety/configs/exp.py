from __future__ import annotations

import uuid
from collections.abc import Callable
from enum import Enum
from typing import Any, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from ..agent import Agent
from ..environment import EnvironmentConfig
from ..survey import Survey

__all__ = [
    "WorkflowStepConfig",
    "EnvironmentConfig",
    "ExpConfig",
    "WorkflowType",
    "AgentFilterConfig",
]


class WorkflowType(str, Enum):
    """
    Defines the types of workflow steps in the simulation.
    - **Description**:
        - Enumerates different types of workflow steps that can be executed during simulation.

    - **Types**:
        - `STEP`: Execute on a step-by-step unit.
        - `RUN`: Execute on a daily unit (day-based execution).
        - `INTERVIEW`: Sends an interview message to the specified agent.
        - `SURVEY`: Sends a questionnaire to the specified agent.
        - `ENVIRONMENT_INTERVENE`: Changes the environment variables (global prompt).
        - `UPDATE_STATE_INTERVENE`: Directly updates the state information of the specified agent.
        - `MESSAGE_INTERVENE`: Influences the agent's behavior and state by sending a message.
        - `NEXT_ROUND`: Proceed to the next round of the simulation —— reset agents but keep the memory.
        - `DELETE_AGENT`: Delete the specified agents.
        - `SAVE_CONTEXT`: Save the context of the specified agents.
        - `INTERVENE`: Represents other intervention methods driven by code.
        - `FUNCTION`: Represents function-based intervention methods.
    """
    # main
    STEP = "step"
    RUN = "run"

    # agent interaction
    INTERVIEW = "interview"
    SURVEY = "survey"
    UPDATE_STATE_INTERVENE = "update_state"
    MESSAGE_INTERVENE = "message"
    DELETE_AGENT = "delete_agent"

    # environment interaction
    ENVIRONMENT_INTERVENE = "environment"

    # other
    NEXT_ROUND = "next_round"
    SAVE_CONTEXT = "save_context"
    INTERVENE = "other"
    FUNCTION = "function"


class AgentFilterConfig(BaseModel):
    """Configuration for filtering agents."""

    agent_class: Optional[Union[tuple[type[Agent]], list[str]]] = None
    """The class of the agent to filter"""

    filter_str: Optional[str] = None
    """The filter string of the agent to filter"""

    @model_validator(mode="after")
    def validate_func(self):
        if self.agent_class is None and self.filter_str is None:
            raise ValueError(
                "Please provide at least one of agent_class or filter_str for AgentFilterConfig"
            )
        return self


class WorkflowStepConfig(BaseModel):
    """Represents a step in the workflow process."""

    model_config = ConfigDict(use_enum_values=True, use_attribute_docstrings=True)

    type: WorkflowType = Field(...)
    """The type of the workflow step"""

    func: Optional[Union[Callable, str]] = None
    """The function that extracts the metric - used for [FUNCTION] type"""

    days: float = 1
    """Duration (in days) for which this step lasts - used for [RUN] type"""

    steps: int = 1
    """Number of steps for which this step lasts - used for [STEP] type"""

    ticks_per_step: int = 300
    """Number of ticks per step - used for [RUN, STEP] type. For example, if it is 300, then the step will run 300 ticks in the environment."""

    target_agent: Optional[Union[list[int], AgentFilterConfig]] = None
    """List specifying the agents targeted by this step - used for [INTERVIEW, SURVEY, UPDATE_STATE_INTERVENE, MESSAGE_INTERVENE, DELETE_AGENT, SAVE_CONTEXT] type"""

    interview_message: Optional[str] = None
    """Optional message used for interviews during this step - used for [INTERVIEW] type"""

    survey: Optional[Survey] = None
    """Optional survey instance associated with this step - used for [SURVEY] type"""

    key: Optional[str] = None
    """Optional key identifier for the step - used for [ENVIRONMENT_INTERVENE, UPDATE_STATE_INTERVENE, SAVE_CONTEXT] type"""

    save_as: Optional[str] = None
    """Optional key identifier for the step - used for [SAVE_CONTEXT] type"""

    value: Optional[Any] = None
    """Optional value associated with the step - used for [ENVIRONMENT_INTERVENE, UPDATE_STATE_INTERVENE] type"""

    intervene_message: Optional[str] = None
    """Optional message used for interventions - used for [MESSAGE_INTERVENE] type"""

    description: Optional[str] = None
    """A descriptive text explaining the workflow step"""

    @field_serializer("func")
    def serialize_func(self, func, info):
        if func is None:
            return None
        # Handle partial function
        if hasattr(func, "func"):
            return func.func.__name__
        return func.__name__

    @model_validator(mode="after")
    def validate_func(self):
        if self.type == WorkflowType.STEP:
            if self.steps <= 0:
                raise ValueError("steps must be greater than 0 for STEP type")
        elif self.type == WorkflowType.RUN:
            if self.days <= 0:
                raise ValueError("days must be greater than 0 for RUN type")
        elif self.type == WorkflowType.INTERVIEW:
            if self.target_agent is None or self.interview_message is None:
                raise ValueError(
                    "target_agent and interview_message are required for INTERVIEW step"
                )
        elif self.type == WorkflowType.SURVEY:
            if self.target_agent is None or self.survey is None:
                raise ValueError("target_agent and survey are required for SURVEY step")
        elif self.type == WorkflowType.ENVIRONMENT_INTERVENE:
            if self.key is None or self.value is None:
                raise ValueError(
                    "key and value are required for ENVIRONMENT_INTERVENE step"
                )
        elif self.type == WorkflowType.UPDATE_STATE_INTERVENE:
            if self.key is None or self.value is None or self.target_agent is None:
                raise ValueError(
                    "key, value and target_agent are required for UPDATE_STATE_INTERVENE step"
                )
        elif self.type == WorkflowType.MESSAGE_INTERVENE:
            if self.intervene_message is None or self.target_agent is None:
                raise ValueError(
                    "intervene_message and target_agent are required for MESSAGE_INTERVENE step"
                )
        elif self.type == WorkflowType.NEXT_ROUND:
            if self.target_agent is not None:
                raise ValueError("target_agent is not allowed for NEXT_ROUND step")
        elif self.type == WorkflowType.SAVE_CONTEXT:
            if self.target_agent is None or self.key is None or self.save_as is None:
                raise ValueError("target_agent, key and save_as are required for SAVE_CONTEXT step")
        elif self.type == WorkflowType.INTERVENE:
            if self.func is None:
                raise ValueError(
                    "target_agent and intervene_message are required for INTERVENE step"
                )
        elif self.type == WorkflowType.FUNCTION:
            if self.func is None:
                raise ValueError("func is required for FUNCTION step")
        elif self.type == WorkflowType.DELETE_AGENT:
            if self.target_agent is None:
                raise ValueError("target_agent is required for DELETE_AGENT step")
        else:
            raise ValueError(f"Unknown workflow type: {self.type} in custom validator")
        return self


class ExpConfig(BaseModel):
    """Main configuration for the experiment."""

    model_config = ConfigDict(use_enum_values=True, use_attribute_docstrings=True)

    name: str = Field("default_experiment")
    """Name of the experiment"""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    """Unique identifier for the experiment"""

    workflow: List[WorkflowStepConfig] = Field(..., min_length=1)
    """List of workflow steps"""

    environment: EnvironmentConfig
    """Environment configuration"""

    @field_serializer("id")
    def serialize_id(self, id, info):
        return str(id)

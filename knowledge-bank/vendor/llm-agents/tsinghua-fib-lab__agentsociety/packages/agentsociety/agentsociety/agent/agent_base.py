import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, Union

from pycityproto.city.person.v2 import person_pb2 as person_pb2
from pydantic import BaseModel

from ..logger import get_logger
from ..memory import Memory
from ..message import Message, MessageKind
from ..storage import StorageDialog, StorageDialogType
from .block import Block, BlockOutput
from .context import AgentContext, context_to_dot_dict
from .dispatcher import BlockDispatcher
from .memory_config_generator import MemoryAttribute
from .toolbox import AgentToolbox

__all__ = [
    "Agent",
    "AgentType",
    "AgentParams",
    "GatherQuery",
]


class AgentParams(BaseModel):
    """
    Agent parameters
    """

    ...


class GatherQuery(BaseModel):
    """
    A model for gather query
    """

    key: str
    target_agent_ids: list[int]
    flatten: bool = True
    keep_id: bool = True


class AgentType(Enum):
    """
    Agent Type

    - Citizen, Citizen type agent
    - Institution, Organization or institution type agent
    """

    Unspecified = "Unspecified"
    Citizen = "Citizen"
    Institution = "Institution"
    Supervisor = "Supervisor"
    Individual = "Individual"


def extract_json(output_str):
    """Extract JSON substring from a raw string response.

    Args:
        output_str: Raw string output that may contain JSON data.

    Returns:
        Extracted JSON string if valid, otherwise None.

    Note:
        Searches for the first '{' and last '}' to isolate JSON content.
        Catches JSON decoding errors and logs warnings.
    """
    try:
        # Find the positions of the first '{' and the last '}'
        start = output_str.find("{")
        end = output_str.rfind("}")

        # Extract the substring containing the JSON
        json_str = output_str[start : end + 1]

        # Convert the JSON string to a dictionary
        return json_str
    except ValueError as e:
        get_logger().warning(f"Failed to extract JSON: {e}")
        return None


class Agent(ABC):
    """
    Agent base class
    """

    ParamsType: type[AgentParams] = AgentParams  # Determine agent parameters
    Context: type[AgentContext] = (
        AgentContext  # Agent Context for information retrieval
    )
    BlockOutputType: type[BlockOutput] = BlockOutput  # Block output
    StatusAttributes: list[MemoryAttribute] = []  # Memory configuration
    description: str = ""  # Agent description: How this agent works

    def __init__(
        self,
        id: int,
        name: str,
        type: AgentType,
        toolbox: AgentToolbox,
        memory: Memory,
        agent_params: Optional[Any] = None,
        blocks: Optional[list[Block]] = None,
    ) -> None:
        """
        Initialize the `Agent`.

        - **Args**:
            - `id` (`int`): The ID of the agent.
            - `name` (`str`): The name of the agent.
            - `type` (`AgentType`): The type of the agent. Defaults to `AgentType.Unspecified`.
            - `toolbox` (`AgentToolbox`): The toolbox of the agent.
            - `memory` (`Memory`): The memory of the agent.
        """
        self._id = id
        self._name = name
        self._type = type
        self._toolbox = toolbox
        self._memory = memory

        # parse agent_params
        if agent_params is None:
            agent_params = self.default_params()
        self.params = agent_params

        # parse blocks
        self.dispatcher = BlockDispatcher(self._toolbox, self._memory)
        if blocks is not None:
            for block in blocks:
                # Check if block output type is compatible with agent's expected output type
                if not self._is_output_type_compatible(block.OutputType):
                    raise ValueError(
                        f"Block output type mismatch, expected {self.BlockOutputType}, got {block.OutputType}. "
                        f"The block output type must be compatible with the agent's expected output type."
                    )
                if block.NeedAgent:
                    block.set_agent(self)
            self.blocks = blocks
            self.dispatcher.register_blocks(self.blocks)
        else:
            self.blocks = []

        # initialize context
        context = self.default_context()
        self.context = context_to_dot_dict(context)

        # gather query
        self.gather_query: dict[str, GatherQuery] = {}
        self.gather_results = {}

    @classmethod
    def default_params(cls):
        return cls.ParamsType()

    @classmethod
    def default_context(cls):
        return cls.Context()

    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Create a new dictionary that inherits from parent
        cls.get_functions = dict(cls.__base__.get_functions) if hasattr(cls.__base__, "get_functions") else {}  # type: ignore

        # Register all methods with _register_info
        for name, method in cls.__dict__.items():
            if hasattr(method, "_get_info"):
                info = method._get_info
                cls.get_functions[info["function_name"]] = info

    async def init(self):
        await self._memory.status.update("id", self._id)

    def __getstate__(self):
        state = self.__dict__.copy()
        # Exclude lock objects
        del state["_toolbox"]
        return state

    @property
    def id(self):
        """The Agent's Simulator ID"""
        return self._id
    
    @property
    def toolbox(self):
        """The Agent's Toolbox"""
        return self._toolbox

    @property
    def llm(self):
        """The Agent's LLM"""
        return self._toolbox.llm

    @property
    def environment(self):
        """The Agent's Environment"""
        return self._toolbox.environment

    @property
    def messager(self):
        """The Agent's Messager"""
        return self._toolbox.messager

    @property
    def database_writer(self):
        """The Agent's Database Writer"""
        return self._toolbox.database_writer

    @property
    def memory(self):
        """The Agent's Memory"""
        return self._memory

    @property
    def status(self):
        """The Agent's Status Memory"""
        return self.memory.status

    @property
    def stream(self):
        """The Agent's Stream Memory"""
        return self.memory.stream

    async def reset(self):
        """Reset the agent."""
        raise NotImplementedError("This method should be implemented by subclasses")

    async def react_to_intervention(self, intervention_message: str):
        """
        React to an intervention.

        - **Args**:
            - `intervention_message` (`str`): The message of the intervention.

        - **Description**:
            - React to an intervention.
        """
        raise NotImplementedError("This method should be implemented by subclasses")

    async def send_message_to_agent(
        self, to_agent_id: int, content: str, type: str = "social"
    ):
        """
        Send a social or economy message to another agent.

        - **Args**:
            - `to_agent_id` (`int`): The ID of the recipient agent.
            - `content` (`str`): The content of the message to send.
            - `type` (`str`, optional): The type of the message ("social" or "economy"). Defaults to "social".

        - **Raises**:
            - `RuntimeError`: If the Messager is not set.

        - **Description**:
            - Validates the message type and logs a warning if it's invalid.
            - Prepares the message payload with necessary metadata such as sender ID, timestamp, etc.
            - Sends the message asynchronously using `_send_message`.
            - Optionally records the message in Database if it's a "social" type message.
        """
        if self.messager is None:
            raise ValueError("Messager is not initialized")
        if self.environment is None:
            raise ValueError("Environment is not initialized")
        day, t = self.environment.get_datetime()
        # send message with `Messager`
        if type not in ["social", "economy"]:
            get_logger().warning(f"Invalid message type: {type}, sent from {self.id}")
        payload = {
            "content": content,
            "type": type,
        }
        await self.messager.send_message(
            Message(
                from_id=self.id,
                to_id=to_agent_id,
                kind=MessageKind.AGENT_CHAT,
                payload=payload,
                day=day,
                t=t,
            )
        )
        storage_dialog = StorageDialog(
            id=self.id,
            day=day,
            t=t,
            type=StorageDialogType.Talk,
            speaker=str(self.id),
            content=content,
            created_at=datetime.now(timezone.utc),
        )
        # Database
        if self.database_writer is not None and type == "social":
            await self.database_writer.write_dialogs(  # type:ignore
                [storage_dialog]
            )

    def _get_gather_query_and_clear(self):
        query = self.gather_query
        self.gather_query: dict[str, GatherQuery] = {}
        return query

    def register_gather_query(
        self,
        key: str,
        target_agent_ids: list[int],
        flatten: bool = True,
        keep_id: bool = True,
    ):
        self.gather_query[key] = GatherQuery(
            key=key,
            target_agent_ids=target_agent_ids,
            flatten=flatten,
            keep_id=keep_id,
        )

    def get_gather_results(self, key: str) -> Optional[list[Any] | dict[int, Any]]:
        if key not in self.gather_results:
            get_logger().warning(f"Gather error: {key} not found in gather results")
            return None
        return self.gather_results[key]

    async def register_aoi_message(
        self, target_aoi: Union[int, list[int]], content: str
    ):
        """
        Register a message to target aoi

        - **Args**:
            - `target_aoi` (`Union[int, list[int]]`): The ID of the target aoi.
            - `content` (`str`): The content of the message to send.

        - **Description**:
            - Register a message to target aoi.
        """
        if self.messager is None:
            raise ValueError("Messager is not initialized")
        if self.environment is None:
            raise ValueError("Environment is not initialized")
        day, t = self.environment.get_datetime()
        if isinstance(target_aoi, int):
            target_aoi = [target_aoi]
        for aoi in target_aoi:
            payload = {
                "content": content,
            }
            await self.messager.send_message(
                Message(
                    from_id=self.id,
                    to_id=aoi,
                    day=day,
                    t=t,
                    kind=MessageKind.AOI_MESSAGE_REGISTER,
                    payload=payload,
                )
            )

    async def cancel_aoi_message(self, target_aoi: Union[int, list[int]]):
        """
        Cancel a message to target aoi
        """
        if self.messager is None:
            raise ValueError("Messager is not initialized")
        if self.environment is None:
            raise ValueError("Environment is not initialized")
        day, t = self.environment.get_datetime()
        if isinstance(target_aoi, int):
            target_aoi = [target_aoi]
        for aoi in target_aoi:
            await self.messager.send_message(
                Message(
                    from_id=self.id,
                    to_id=aoi,
                    day=day,
                    t=t,
                    kind=MessageKind.AOI_MESSAGE_CANCEL,
                    payload={},
                )
            )

    # Agent logic
    @abstractmethod
    async def forward(self) -> Any:
        """
        Define the behavior logic of the agent.

        - **Raises**:
            - `NotImplementedError`: As this method must be implemented by subclasses.

        - **Description**:
            - This abstract method should contain the core logic for what the agent does at each step of its operation.
            - It is intended to be overridden by subclasses to define specific behaviors.
        """
        raise NotImplementedError
    
    async def status_summary(self):
        """
        Status summary
        """
        await self.status.update("status_summary", "Nothing")

    async def close(self):
        """Execute when the agent is deleted or the simulation is finished."""
        pass

    async def before_forward(self):
        """
        Before forward
        """
        pass

    async def after_forward(self):
        """
        After forward
        """
        pass

    async def before_blocks(self):
        """
        Before blocks
        """
        if self.blocks is None:
            return
        for block in self.blocks:
            await block.before_forward()

    async def after_blocks(self):
        """
        After blocks
        """
        if self.blocks is None:
            return
        for block in self.blocks:
            await block.after_forward()

    async def run(self) -> Any:
        """
        Unified entry point for executing the agent's logic.

        - **Description**:
            - It calls the `forward` method to execute the agent's behavior logic.
            - Acts as the main control flow for the agent, coordinating when and how the agent performs its actions.
        """
        start_time = time.time()
        # run required methods before agent forward
        await self.before_forward()
        await self.before_blocks()
        # run agent forward
        await self.forward()
        # run required methods after agent forward
        await self.after_blocks()
        await self.after_forward()
        await self.status_summary()
        end_time = time.time()
        return end_time - start_time

    def _is_output_type_compatible(self, block_output_type) -> bool:
        """
        Check if the block output type is compatible with the agent's expected output type.
        
        - **Description**:
            - Checks compatibility between block output type and agent's expected output type.
            - Supports both class inheritance and field compatibility checks.
        
        - **Args**:
            - `block_output_type`: The output type class of the block.
        
        - **Returns**:
            - `bool`: True if compatible, False otherwise.
        """
        # If agent expects any type, all types are compatible
        if self.BlockOutputType is Any:
            return True
            
        # If agent expects None, only None is compatible
        if self.BlockOutputType is None:
            return block_output_type is None
            
        # If block has no output type, it's compatible with any type
        if block_output_type is None:
            return True
            
        # Check if block output type is a subclass of agent's expected type
        if issubclass(block_output_type, self.BlockOutputType):
            return True
            
        # Check if block output type has compatible fields with agent's expected type
        if hasattr(block_output_type, 'model_fields') and hasattr(self.BlockOutputType, 'model_fields'):
            # Get all required fields from agent's expected type
            agent_fields = self.BlockOutputType.model_fields
            block_fields = block_output_type.model_fields
            
            # Check if all required fields from agent's type exist in block's type
            for field_name, field_info in agent_fields.items():
                if field_name not in block_fields:
                    return False
                # Optional: check field type compatibility
                # This could be enhanced to check type annotations as well
                
            return True
            
        return False

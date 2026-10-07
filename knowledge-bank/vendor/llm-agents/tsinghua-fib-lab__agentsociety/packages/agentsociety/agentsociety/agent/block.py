from typing import Any, Optional

from pydantic import BaseModel

from ..environment import Environment
from ..llm import LLM
from ..memory import KVMemory, Memory
from .context import BlockContext, DotDict, auto_deepcopy_dotdict, context_to_dot_dict
from .memory_config_generator import MemoryConfig
from .toolbox import AgentToolbox

TRIGGER_INTERVAL = 1

__all__ = [
    "Block",
    "BlockParams",
    "BlockOutput",
]


class BlockParams(BaseModel):
    # TODO: unused
    block_memory: Optional[dict[str, Any]] = None


class BlockOutput(BaseModel): ...


# Behavior Block, used for augmenting agent's behavior capabilities
class Block:
    """
    A foundational component similar to a layer in PyTorch, used for building complex systems.
    """

    ParamsType = BlockParams
    Context = BlockContext
    OutputType = None
    NeedAgent: bool = (
        False  # Whether the block needs an agent, if True, the associated agent will be set automatically
    )
    name: str = ""
    description: str = ""
    actions: dict[str, str] = {}

    def __init__(
        self,
        toolbox: AgentToolbox,
        agent_memory: Optional[Memory] = None,
        block_params: Optional[Any] = None,
    ):
        """
        - **Description**:
            - Initializes a new instance of the Block class with optional LLM, Memory, Simulator, and Trigger components.

        - **Args**:
            - `name` (str): The name of the block.
            - `llm` (Optional[LLM], optional): An instance of LLM. Defaults to None.
            - `environment` (Optional[Environment], optional): An instance of Environment. Defaults to None.
            - `memory` (Optional[Memory], optional): An instance of Memory. Defaults to None.
        """
        self._toolbox = toolbox
        self._agent_memory = agent_memory
        self._agent = None

        # parse block_params
        if block_params is None:
            block_params = self.default_params()
        self.params = block_params
        for key, value in self.params.model_dump().items():
            if key == "block_memory":
                # TODO: remove this after we have a better way to handle block memory
                if isinstance(value, MemoryConfig):
                    self._block_memory = KVMemory(
                        value,
                        embedding=self._toolbox.embedding,
                    )
            else:
                setattr(self, key, value)

        # initialize context
        context = self.default_context()
        self.context = context_to_dot_dict(context)

    @classmethod
    def default_params(cls) -> ParamsType:
        return cls.ParamsType()

    @classmethod
    def default_context(cls) -> Context:
        return cls.Context()

    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Create a new dictionary that inherits from parent
        cls.get_functions = dict(cls.__base__.get_functions) if hasattr(cls.__base__, "get_functions") else {}  # type: ignore

        # Register all methods with _register_info
        for name, method in cls.__dict__.items():
            if hasattr(method, "_register_info"):
                info = method._register_info
                cls.get_functions[info["function_name"]] = info

    def set_agent(self, agent: Any):
        self._agent = agent

    @property
    def agent(self) -> Any:
        if self._agent is None:
            raise RuntimeError(
                "Agent access before assignment, please `set_agent` first!"
            )
        return self._agent

    @property
    def toolbox(self) -> AgentToolbox:
        return self._toolbox

    @property
    def llm(self) -> LLM:
        return self._toolbox.llm

    @property
    def memory(self) -> Memory:
        if self._agent_memory is None:
            raise RuntimeError(
                "Memory access before assignment, please `set_memory` first!"
            )
        return self._agent_memory

    @property
    def agent_memory(self) -> Memory:
        if self._agent_memory is None:
            raise RuntimeError(
                "Memory access before assignment, please `set_memory` first!"
            )
        return self._agent_memory

    @property
    def block_memory(self) -> KVMemory:
        if self._block_memory is None:
            raise RuntimeError(
                "Block memory access before assignment, please `set_block_memory` first!"
            )
        return self._block_memory

    @property
    def environment(self) -> Environment:
        return self._toolbox.environment

    async def before_forward(self):
        """
        Before forward - prepare context
        """
        pass

    async def after_forward(self):
        """
        After forward - update/clean context
        """
        pass

    @auto_deepcopy_dotdict
    async def forward(self, agent_context: DotDict):
        """
        - **Description**:
            - Each block performs a specific reasoning task. This method should be overridden by subclasses.
            - Subclasses can define their own parameters as needed.

        - **Args**:
            - `*args`: Variable length argument list.
            - `**kwargs`: Arbitrary keyword arguments.

        - **Raises**:
            - `NotImplementedError`: Subclasses must implement this method.
        """
        raise NotImplementedError("Subclasses should implement this method")

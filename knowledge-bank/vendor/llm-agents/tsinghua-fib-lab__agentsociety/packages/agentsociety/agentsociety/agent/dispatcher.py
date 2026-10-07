from typing import Any
import json_repair
from openai.types.chat import ChatCompletionToolParam

from ..logger import get_logger
from ..memory import Memory
from .block import Block
from .context import DotDict
from .prompt import FormatPrompt
from .toolbox import AgentToolbox

DISPATCHER_PROMPT = """
Based on the task information (which describes the needs of the user), select the most appropriate block to handle the task.
Each block has its specific functionality as described in the function schema.
        
Task information:
${context.current_intention}
"""


class BlockDispatcher:
    """Orchestrates task routing between registered processing blocks.

    Attributes:
        toolbox: AgentToolbox
        blocks: Registry of available processing blocks (name -> Block mapping)
        prompt: Formatted prompt template for LLM instructions
    """

    def __init__(
        self,
        toolbox: AgentToolbox,
        agent_memory: Memory,
        selection_prompt: str = DISPATCHER_PROMPT,
    ):
        """Initialize dispatcher with LLM interface.

        Args:
            llm: Language model for block selection decisions
        """
        self.toolbox = toolbox
        self.memory = agent_memory
        self.blocks: dict[str, Block] = {}
        self.dispatcher_prompt = FormatPrompt(selection_prompt, memory=self.memory)

    def register_dispatcher_prompt(self, dispatcher_prompt: str) -> None:
        """Register a dispatcher prompt.

        Args:
            dispatcher_prompt: Dispatcher prompt
        """
        self.dispatcher_prompt = FormatPrompt(dispatcher_prompt, memory=self.memory)

    def register_blocks(self, blocks: list[Block]) -> None:
        """Register multiple processing blocks for dispatching.

        Args:
            blocks: List of Block instances to register
        """
        for block in blocks:
            block_name = block.__class__.__name__.lower()
            self.blocks[block_name] = block

    def _get_function_schema(self) -> ChatCompletionToolParam:
        """
        Generate LLM function calling schema describing available blocks.

        - **Description**:
            - Creates a schema for the LLM to select appropriate blocks or indicate no suitable block exists.

        - **Returns**:
            - `ChatCompletionToolParam`: Function schema dictionary compatible with OpenAI-style function calling
        """
        # create block descriptions
        block_descriptions = {
            name: block.description for name, block in self.blocks.items()
        }

        return {
            "type": "function",
            "function": {
                "name": "select_block",
                "description": "Select the most appropriate block based on the step information, or indicate no suitable block exists",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "block_name": {
                            "type": "string",
                            "enum": list(self.blocks.keys()) + ["no_suitable_block"],
                            "description": f"Available blocks and their descriptions: {block_descriptions}. Use 'no_suitable_block' if none of the blocks are appropriate for the given intention.",
                        },
                        "reason": {
                            "type": "string",
                            "description": "Explanation for why the selected block is appropriate or why no suitable block exists",
                        },
                    },
                    "required": ["block_name", "reason"],
                },
            },
        }

    async def dispatch(self, context: DotDict) -> Block | None:
        """
        Route a task step to the most appropriate processing block.

        - **Description**:
            - Uses LLM to select the best block for handling the given task intention.
            - Can return None if no suitable block is found.

        - **Args**:
            - `intention` (str): Intention of the task

        - **Returns**:
            - `Block | None`: Selected Block instance for handling the task, or None if no suitable block exists
        """
        try:
            function_schema = self._get_function_schema()
            await self.dispatcher_prompt.format(context=context)

            # Call LLM with tools schema
            response = await self.toolbox.llm.atext_request(
                self.dispatcher_prompt.to_dialog(),
                tools=[function_schema],
                tool_choice={"type": "function", "function": {"name": "select_block"}},
            )
            function_args: Any = json_repair.loads(
                response.choices[0].message.tool_calls[0].function.arguments
            )
            selected_block = function_args.get("block_name")
            reason = function_args.get("reason", "No reason provided")

            if selected_block == "no_suitable_block":
                get_logger().debug(
                    f"No suitable block found for intention. Reason: {reason}"
                )
                return None

            if selected_block not in self.blocks:
                raise ValueError(
                    f"Selected block '{selected_block}' not found in registered blocks"
                )

            get_logger().debug(
                f"Dispatched intention to block: {selected_block}. Reason: {reason}"
            )
            return self.blocks[selected_block]

        except Exception as e:
            get_logger().warning(f"Failed to dispatch block: {e}")
            return None

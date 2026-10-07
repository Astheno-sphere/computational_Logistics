from ..llm import LLM, LLMConfig
from .messager import Message, MessageKind


__all__ = [
    "MessageInterceptor",
]


class MessageInterceptor:
    """
    A class to intercept and process messages based on configured rules.
    """

    def __init__(
        self,
        llm_config: list[LLMConfig],
    ) -> None:
        """
        Initialize the MessageInterceptor with optional configuration.

        - **Args**:
            - `llm_config` (LLMConfig): Configuration dictionary for initializing the LLM instance. Defaults to None.
        """
        self._llm = LLM(llm_config)
        # round related
        self.validation_dict: dict[Message, bool] = {}
        self._supervisor = None

    async def set_supervisor(self, supervisor):
        self._supervisor = supervisor

    # Property accessors
    @property
    def supervisor(self):
        if self._supervisor is None:
            raise RuntimeError("Supervisor not set")
        return self._supervisor

    @property
    def llm(self) -> LLM:
        """
        Access the Large Language Model instance.

        - **Description**:
            - Provides access to the internal LLM instance. Raises an error if accessed before assignment.

        - **Raises**:
            - `RuntimeError`: If accessed before setting the LLM.

        - **Returns**:
            - `LLM`: The Large Language Model instance.
        """
        if self._llm is None:
            raise RuntimeError("LLM access before assignment, please `set_llm` first!")
        return self._llm

    # Message forwarding related methods
    async def forward(self, messages: list[Message]) -> list[Message]:
        # reset round related variables
        new_round_validation_dict, persuasion_messages = await self.supervisor.forward(
            messages
        )
        result_messages: list[Message] = []
        for msg in messages:
            if msg.kind == MessageKind.AGENT_CHAT:
                is_valid = new_round_validation_dict.get(msg, True)
                if is_valid:
                    result_messages.append(msg)
                else:
                    # add message to from_id
                    result_messages.append(
                        Message(
                            from_id=msg.to_id,
                            to_id=msg.from_id,
                            kind=MessageKind.AGENT_CHAT,
                            payload={"content": "Message sent failed"},
                            day=msg.day,
                            t=msg.t,
                        )
                    )
            else:
                result_messages.append(msg)
        result_messages.extend(persuasion_messages)
        return result_messages

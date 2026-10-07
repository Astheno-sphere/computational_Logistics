import asyncio
from datetime import datetime
from enum import Enum
from typing import Optional

import ray
import ray.actor
from pydantic import BaseModel, Field

from ..logger import get_logger
from ..utils.decorators import lock_decorator

__all__ = [
    "MessageKind",
    "Message",
    "Messager",
]


class MessageKind(str, Enum):
    AGENT_CHAT = "agent-chat"
    USER_CHAT = "user-chat"
    AOI_MESSAGE_REGISTER = "aoi-message-register"
    AOI_MESSAGE_CANCEL = "aoi-message-cancel"


class Message(BaseModel):
    from_id: Optional[int] = None
    """sender id"""
    to_id: Optional[int] = None
    """target agent id or aoi id"""
    day: int
    """day"""
    t: float
    """tick"""
    kind: MessageKind
    """message kind"""
    payload: dict
    """message payload"""
    created_at: datetime = Field(default_factory=datetime.now)
    """message created at"""
    extra: Optional[dict] = None
    """extra information"""

    def __hash__(self):
        return hash((self.from_id, self.to_id, self.day, self.t, self.kind, self.created_at))


class Messager:
    """
    A class to manage message sending and receiving.

    - **Attributes**:
        - `_message_interceptor` (Optional[ray.ObjectRef]): Reference to a remote message interceptor object.
        - `_pending_messages` (list): List to store pending messages.
        - `_received_messages` (list): List to store received messages.
        - `_lock` (asyncio.Lock): Lock for thread-safe operations.
    """

    def __init__(
        self,
        exp_id: str,
    ):
        """
        Initialize the Messager.

        - **Args**:
            - `exp_id` (str): Experiment ID.
            - `message_interceptor` (Optional[ray.ObjectRef], optional): Reference to a message interceptor object.
        """
        self.exp_id = exp_id
        self._pending_messages: list[Message] = []
        self._received_messages: list[Message] = []
        self._lock = asyncio.Lock()
        get_logger().info("Messager initialized")

    @property
    def message_interceptor(self) -> Optional[ray.ObjectRef]:
        """
        Access the message interceptor reference.

        - **Returns**:
            - `Optional[ray.ObjectRef]`: The message interceptor reference.
        """
        return self._message_interceptor

    def set_message_interceptor(self, message_interceptor: ray.ObjectRef):
        """
        Set the message interceptor reference.

        - **Args**:
            - `message_interceptor` (ray.ObjectRef): The message interceptor reference to be set.
        """
        self._message_interceptor = message_interceptor

    @lock_decorator
    async def send_message(self, message: Message):
        """
        Send a message.

        - **Args**:
            - `message` (Message): Message to send.
        """
        self._pending_messages.append(message)

    @lock_decorator
    async def fetch_pending_messages(self):
        """
        Fetch messages from the pending messages list. (Called by AgentSimuation)
        """
        msgs = self._pending_messages
        self._pending_messages = []
        return msgs

    async def set_received_messages(self, messages: list[Message]):
        """
        Set the received messages. (Called by AgentSimuation)
        """
        self._received_messages = messages

    async def fetch_received_messages(self):
        """
        Fetch messages from the received messages list. (Called by AgentSociety)
        """
        msgs = self._received_messages
        self._received_messages = []
        return msgs

    # utility

    def get_subtopic_channel(self, agent_id: int, subtopic: str):
        return f"exps:{self.exp_id}:agents:{agent_id}:{subtopic}"

    def get_aoi_channel(self, aoi_id: int):
        return f"exps:{self.exp_id}:aois:{aoi_id}"

    def get_user_survey_channel(self, agent_id: int):
        return self.get_subtopic_channel(agent_id, "user-survey")

    def get_user_chat_channel(self, agent_id: int):
        return self.get_subtopic_channel(agent_id, "user-chat")

    def get_agent_chat_channel(self, agent_id: int):
        return self.get_subtopic_channel(agent_id, "agent-chat")

    def get_user_payback_channel(self):
        return f"exps:{self.exp_id}:user-payback"

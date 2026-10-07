from typing import Any, Optional

from agentsociety.agent import CitizenAgentBase, AgentToolbox, Block, AgentParams, MemoryAttribute
from agentsociety.message import Message, MessageKind
from agentsociety.memory import Memory

from .tools import Sense, Poster, Announcement, Communication, MessageProbe
from .fundmanager import FundManager


class EnvAgentBaseConfig(AgentParams):
    ...

class EnvAgentBase(CitizenAgentBase):
    """
    Base class for environmental agents in the competition.
    
    - **Description**:
        - Provides base functionality and tools for environmental agents.
        - Includes tools for sensing, communication, and environmental actions.
        
    - **Args**:
        - `id` (int): The unique identifier for the agent.
        - `name` (str): The name of the agent.
        - `toolbox` (AgentToolbox): The toolbox containing agent utilities.
        - `memory` (Memory): The memory system for the agent.
    """
    ParamsType = EnvAgentBaseConfig
    StatusAttributes = [
        MemoryAttribute(name="citizens",type=dict,default_or_value={},description="citizens' profile"),
        MemoryAttribute(name="citizen_ids",type=list,default_or_value=[],description="citizens' ids"),
        MemoryAttribute(
            name="probe_logs",
            type=dict,
            default_or_value={
                "message": [],
                "poster": [],
                "announcement": []
            },
            description="probe logs"
        ),
        MemoryAttribute(name="chat_histories",type=dict,default_or_value={},description="all chat histories"),
    ]
    
    def __init__(
        self,
        id: int,
        name: str,
        toolbox: AgentToolbox,
        memory: Memory,
        agent_params: Optional[Any] = None,
        blocks: Optional[list[Block]] = None,
    ) -> None:
        """Initialize the environmental agent with core components and tools."""
        super().__init__(
            id=id,
            name=name,
            toolbox=toolbox,
            memory=memory,
            agent_params=agent_params,
            blocks=blocks,
        )
        
        # Initialize tools
        self._probe = MessageProbe(agent=self, llm=toolbox.llm)
        self.sence = Sense(agent=self, llm=toolbox.llm, probe=self._probe)
        self.poster = Poster(agent=self, llm=toolbox.llm, probe=self._probe)
        self.announcement = Announcement(agent=self, llm=toolbox.llm, probe=self._probe)
        self.communication = Communication(agent=self, llm=toolbox.llm, probe=self._probe)
        
        # Initialize fund manager
        self._fund_manager = FundManager()

    async def before_forward(self):
        """
        Before forward.
        Reset communication times and sync agent status with simulator.
        Do not change anything in this method.
        """
        await super().before_forward()
        # reset communication times
        self.communication._reset()
        # sync agent status with simulator
        await self.update_motion()

    async def reset(self):
        """
        Do not need to reset anything.
        Do not change anything in this method.
        """
        pass

    async def react_to_intervention(self, intervention_message: str):
        """
        Do not need to react to intervention message.
        Do not change anything in this method.
        """
        pass
    
    async def do_chat(self, message: Message) -> str:
        """
        Process incoming social/economic messages and generate responses.
        """
        if message.kind == MessageKind.AGENT_CHAT:
            payload = message.payload
            sender_id = message.from_id
            if not sender_id:
                return ""
            if payload["type"] == "social":
                try:
                    content = payload.get("content", None)
                    if not content:
                        return ""
                    chat_histories = await self.memory.status.get("chat_histories", {})
                    if sender_id not in chat_histories:
                        chat_histories[sender_id] = f"He/She: {content}"
                    else:
                        chat_histories[sender_id] += f"\nHe/She: {content}"
                    await self.memory.status.update("chat_histories", chat_histories)
                    response = await self.communication_response(sender_id, content)
                    if response:
                        await self.communication.sendMessage(sender_id, response)
                    return response
                except Exception:
                    return ""
            else:
                return ""
        else:
            return ""
        
    async def communication_response(self, sender_id: int, content: str):
        """
        Communication response.
        Design your response logic in this method.

        - **Args**:
            - `sender_id` (int): The ID of the sender, agent_id.
            - `content` (str): The content of the message.

        - **Returns**:
            - The response message.
        """
        return "Keep Going!"
        
    async def forward(self):
        """
        Main agent loop.
        Design your own logic in this method.
        """
        pass

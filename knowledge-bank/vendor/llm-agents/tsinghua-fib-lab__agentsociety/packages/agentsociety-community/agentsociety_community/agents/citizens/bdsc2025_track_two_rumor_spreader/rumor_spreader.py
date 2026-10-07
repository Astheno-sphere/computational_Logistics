import asyncio
import random
import time
from typing import Any, Optional, cast

from agentsociety.agent import (AgentToolbox, Block, CitizenAgentBase,
                                MemoryAttribute)
from agentsociety.memory import Memory
from agentsociety.memory.const import RelationType, SocialRelation

from .sharing_params import (RumorSpreaderBlockOutput, RumorSpreaderConfig,
                             RumorSpreaderContext)


class RumorSpreader(CitizenAgentBase):

    ParamsType = RumorSpreaderConfig
    BlockOutputType = RumorSpreaderBlockOutput
    StatusAttributes = [
        # Needs Model
        MemoryAttribute(
            name="hunger_satisfaction",
            type=float,
            default_or_value=0.9,
            description="agent's hunger satisfaction, 0-1",
        ),
        MemoryAttribute(
            name="energy_satisfaction",
            type=float,
            default_or_value=0.9,
            description="agent's energy satisfaction, 0-1",
        ),
        MemoryAttribute(
            name="safety_satisfaction",
            type=float,
            default_or_value=0.4,
            description="agent's safety satisfaction, 0-1",
        ),
        MemoryAttribute(
            name="social_satisfaction",
            type=float,
            default_or_value=0.6,
            description="agent's social satisfaction, 0-1",
        ),
        MemoryAttribute(
            name="current_need",
            type=str,
            default_or_value="none",
            description="agent's current need",
        ),
        # Plan Behavior Model
        MemoryAttribute(
            name="current_plan",
            type=dict,
            default_or_value={},
            description="agent's current plan",
        ),
        MemoryAttribute(
            name="execution_context",
            type=dict,
            default_or_value={},
            description="agent's execution context",
        ),
        MemoryAttribute(
            name="plan_history",
            type=list,
            default_or_value=[],
            description="agent's plan history",
        ),
        # Cognition
        MemoryAttribute(
            name="emotion",
            type=dict,
            default_or_value={
                "sadness": 5,
                "joy": 5,
                "fear": 5,
                "disgust": 5,
                "anger": 5,
                "surprise": 5,
            },
            description="agent's emotion, 0-10",
        ),
        MemoryAttribute(
            name="attitude",
            type=dict,
            default_or_value={},
            description="agent's attitude",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="thought",
            type=str,
            default_or_value="Currently nothing good or bad is happening",
            description="agent's thought",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="emotion_types",
            type=str,
            default_or_value="Relief",
            description="agent's emotion types",
            whether_embedding=True,
        ),
        # Economy
        MemoryAttribute(
            name="work_skill", type=float, default_or_value=0.0, description="agent's work skill"
        ),
        MemoryAttribute(
            name="tax_paid", type=float, default_or_value=0.0, description="agent's tax paid"
        ),
        MemoryAttribute(
            name="consumption_currency",
            type=float,
            default_or_value=0.0,
            description="agent's consumption currency",
        ),
        MemoryAttribute(
            name="goods_demand", type=int, default_or_value=0, description="agent's goods demand"
        ),
        MemoryAttribute(
            name="goods_consumption",
            type=int,
            default_or_value=0,
            description="agent's goods consumption",
        ),
        MemoryAttribute(
            name="work_propensity",
            type=float,
            default_or_value=0.0,
            description="agent's work propensity",
        ),
        MemoryAttribute(
            name="consumption_propensity",
            type=float,
            default_or_value=0.0,
            description="agent's consumption propensity",
        ),
        MemoryAttribute(
            name="to_consumption_currency",
            type=float,
            default_or_value=0.0,
            description="agent's to consumption currency",
        ),
        MemoryAttribute(
            name="firm_id", type=int, default_or_value=0, description="agent's firm id"
        ),
        MemoryAttribute(
            name="government_id",
            type=int,
            default_or_value=0,
            description="agent's government id",
        ),
        MemoryAttribute(
            name="bank_id", type=int, default_or_value=0, description="agent's bank id"
        ),
        MemoryAttribute(
            name="nbs_id", type=int, default_or_value=0, description="agent's nbs id"
        ),
        MemoryAttribute(
            name="dialog_queue",
            type=list,
            default_or_value=[],
            description="agent's dialog queue",
        ),
        MemoryAttribute(
            name="firm_forward", type=int, default_or_value=0, description="agent's firm forward"
        ),
        MemoryAttribute(
            name="bank_forward", type=int, default_or_value=0, description="agent's bank forward"
        ),
        MemoryAttribute(
            name="nbs_forward", type=int, default_or_value=0, description="agent's nbs forward"
        ),
        MemoryAttribute(
            name="government_forward",
            type=int,
            default_or_value=0,
            description="agent's government forward",
        ),
        MemoryAttribute(
            name="forward", type=int, default_or_value=0, description="agent's forward"
        ),
        MemoryAttribute(
            name="depression",
            type=float,
            default_or_value=0.0,
            description="agent's depression, 0-1",
        ),
        MemoryAttribute(
            name="ubi_opinion", type=list, default_or_value=[], description="agent's ubi opinion"
        ),
        MemoryAttribute(
            name="working_experience",
            type=list,
            default_or_value=[],
            description="agent's working experience",
        ),
        MemoryAttribute(
            name="work_hour_month",
            type=float,
            default_or_value=160,
            description="agent's work hour per month",
        ),
        MemoryAttribute(
            name="work_hour_finish",
            type=float,
            default_or_value=0,
            description="agent's work hour finished",
        ),
        # Social
        MemoryAttribute(
            name="friends_info",
            type=dict,
            default_or_value={},
            description="agent's friends info",
        ),
        MemoryAttribute(
            name="relationships",
            type=dict,
            default_or_value={},
            description="agent's relationship strength with each friend",
        ),
        MemoryAttribute(
            name="relation_types",
            type=dict,
            default_or_value={},
            description="agent's relation types with each friend",
        ),
        MemoryAttribute(
            name="chat_histories",
            type=dict,
            default_or_value={},
            description="all chat histories",
        ),
        MemoryAttribute(
            name="interactions",
            type=dict,
            default_or_value={},
            description="all interaction records",
        ),
        # Mobility
        MemoryAttribute(
            name="number_poi_visited",
            type=int,
            default_or_value=1,
            description="agent's number of poi visited",
        ),
        MemoryAttribute(
            name="location_knowledge",
            type=dict,
            default_or_value={},
            description="agent's location knowledge",
        ),
        MemoryAttribute(
            name="message_propagation_preference",
            type=str,
            default_or_value="",
            description="agent's message propagation preference",
        ),
        MemoryAttribute(
            name="background_story",
            type=str,
            default_or_value="",
            description="agent's background story",
        ),
    ]

    ContextType = RumorSpreaderContext
    name = "RumorSpreader"
    description = "Responsible for spreading rumors"
    actions = {}

    def __init__(
        self,
        id: int,
        name: str,
        toolbox: AgentToolbox,
        memory: Memory,
        agent_params: Optional[Any] = None,
        blocks: Optional[list[Block]] = None,
    ) -> None:
        """Initialize agent with core components and configuration."""
        super().__init__(
            id=id,
            name=name,
            toolbox=toolbox,
            memory=memory,
            agent_params=agent_params,
            blocks=blocks,
        )
        self.step_count = -1
        self.params = cast(RumorSpreaderConfig, self.params)

    async def reset(self):
        """Reset the agent."""
        # reset position to home
        await self.reset_position()

    # Main workflow
    async def forward(self):  # type: ignore
        start_time = time.time()
        # rumor_content = self.params.rumor_posts[
        #     self.step_count % len(self.params.rumor_posts)
        # ]
        rumor_content = self.params.rumor_post
        current_social_network: list[SocialRelation] = await self.memory.status.get(
            "social_network", []
        )
        all_agent_ids = [
            connection.target_id
            for connection in current_social_network
            if connection.kind == RelationType.FOLLOWER
        ]
        num_public_receivers = min(
            self.params.rumor_post_visible_cnt, len(all_agent_ids)
        )
        public_receivers = (
            random.sample(all_agent_ids, num_public_receivers)
            if all_agent_ids and num_public_receivers > 0
            else []
        )

        num_private_receivers = min(self.params.rumor_private_cnt, len(all_agent_ids))
        # 私聊对象的选择，暂时简化为纯随机，权重的管理和使用在Simulation层更合适
        private_chat_targets = (
            random.sample(all_agent_ids, num_private_receivers)
            if all_agent_ids and num_private_receivers > 0
            else []
        )
        # send message to public receivers
        tasks = []
        print(
            f"RumorSpreader {self.id} sending message `{rumor_content }` to public receivers {len(public_receivers)} and private chat targets: {len(private_chat_targets)}"
        )
        for receiver_id in public_receivers + private_chat_targets:
            tasks.append(self.send_message_to_agent(receiver_id, rumor_content))
        await asyncio.gather(*tasks)
        return time.time() - start_time

    async def process_agent_chat_response(self, payload: dict) -> str:
        return ""

    async def react_to_intervention(self, intervention_message: str):
        """React to an intervention"""
        pass

    async def reset_position(self):
        """Reset the position of the agent."""
        home = await self.status.get("home")
        home = home["aoi_position"]["aoi_id"]
        await self.environment.reset_person_position(person_id=self.id, aoi_id=home)

    async def close(self):
        """Close the agent."""
        pass

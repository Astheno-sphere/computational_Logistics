import random
import time
from typing import Optional

from agentsociety.agent import AgentToolbox, Block, CitizenAgentBase, MemoryAttribute
from agentsociety.logger import get_logger
from agentsociety.memory import Memory
from agentsociety.memory.const import RelationType, SocialRelation
from agentsociety.message import Message
from agentsociety.survey import Survey

from .blocks import SocialBlock
from .sharing_params import EnvCitizenBlockOutput, EnvCitizenConfig, EnvCitizenContext


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
    except Exception as e:
        get_logger().warning(f"Failed to extract JSON: {e}")
        return None


class TrackTwoEnvCitizen(CitizenAgentBase):
    """Agent implementation with configurable cognitive/behavioral modules and social interaction capabilities."""

    ParamsType = EnvCitizenConfig
    BlockOutputType = EnvCitizenBlockOutput
    ContextType = EnvCitizenContext

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
        # MemoryAttribute(
        #     name="background_story",
        #     type=str,
        #     default_or_value="",
        #     description="agent's background story",
        # ),
        MemoryAttribute(
            name="survey_request_history",
            type=list,
            default_or_value=[],
            description="agent's survey request history",
        ),
    ]

    def __init__(
        self,
        id: int,
        name: str,
        toolbox: AgentToolbox,
        memory: Memory,
        agent_params: Optional[EnvCitizenConfig] = None,
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
        self.social_block = SocialBlock(
            agent=self,
            toolbox=toolbox,
            max_visible_followers=self.params.max_visible_followers,
            max_private_chats=self.params.max_private_chats,
            chat_probability=self.params.chat_probability,
            environment=self.environment,
            memory=self.memory,
        )
        self.step_count = -1

    async def before_forward(self):
        """Before forward"""
        await super().before_forward()

    async def reset(self):
        """Reset the agent."""
        # reset position to home
        await self.reset_position()

        # reset needs
        await self.memory.status.update("current_need", "none")

        # reset plans and actions
        await self.memory.status.update("current_plan", {})
        await self.memory.status.update("execution_context", {})

    # Main workflow
    async def forward(
        self,
    ):
        """Main agent loop coordinating status updates, plan execution, and cognition."""
        start_time = time.time()
        self.step_count += 1
        # sync agent status with simulator
        await self.update_motion()
        get_logger().debug(f"Agent {self.id}: Finished main workflow - update motion")

        # ATTENTION: random social interaction
        current_messages = await self.social_block.current_messages()
        received_ids = set(ii for (ii, _) in current_messages)
        if len(current_messages) > 0 and (
            random.random() < self.params.chat_probability
            or self.params.rumor_post_identifier in received_ids
        ):
            # social interaction
            await self.social_block.forward(None)
            get_logger().debug(
                f"Agent {self.id}: Finished main workflow - social interaction"
            )

        get_logger().debug(f"Agent {self.id}: Finished main workflow - cognition")

        return time.time() - start_time

    async def do_chat(self, message: Message) -> str:
        """Process incoming social/economic messages and generate responses."""
        payload = message.payload
        get_logger().debug(f"Agent {self.id}: do_chat - payload: {payload}")
        if payload["type"] == "social":
            resp = f"Agent {self.id} received agent chat response: {payload}"
            try:
                # Extract basic info
                sender_id = message.from_id
                if not sender_id:
                    return ""

                raw_content = payload.get("content", "")

                await self.social_block.receive_message(sender_id, f"{raw_content}")
                print(f"Received message `{raw_content}`")

                # add social memory
                description = f"You received a social message: {raw_content}"
                await self.memory.stream.add(topic="social", description=description)
            except Exception as e:
                get_logger().warning(f"Error in process_agent_chat_response: {str(e)}")
                return ""
        elif payload["type"] == "persuasion":
            content = payload["content"]
            # add persuasion memory
            description = f"You received a persuasion message: {content}"
            await self.memory.stream.add(topic="social", description=description)
            await self.social_block._add_intervention_to_history(
                intervention_type="persuasion_received",
                details={
                    "content": content,
                },
            )
        elif payload["type"] == "remove-follower":
            to_remove_id = payload["to_remove_id"]
            current_social_network: list[SocialRelation] = await self.memory.status.get(
                "social_network"
            )
            current_social_network = [
                connection
                for connection in current_social_network
                if connection.target_id != to_remove_id
                and connection.kind == RelationType.FOLLOWER
            ]
            await self.memory.status.update("social_network", current_social_network)
            await self.social_block._add_intervention_to_history(
                intervention_type="remove_follower_by_platform",
                details={
                    "to_remove_id": to_remove_id,
                },
            )
        elif payload["type"] == "remove-following":
            to_remove_id = payload["to_remove_id"]
            current_social_network: list[SocialRelation] = await self.memory.status.get(
                "social_network"
            )
            current_social_network = [
                connection
                for connection in current_social_network
                if connection.target_id != to_remove_id
                and connection.kind == RelationType.FOLLOWING
            ]
            await self.memory.status.update("social_network", current_social_network)
            await self.social_block._add_intervention_to_history(
                intervention_type="remove_following_by_platform",
                details={
                    "to_remove_id": to_remove_id,
                },
            )
        elif payload["type"] == "agent_banned":
            await self.social_block._add_intervention_to_history(
                intervention_type="agent_banned",
                details={},
            )
        elif payload["type"] == "post_deleted":
            await self.social_block._add_intervention_to_history(
                intervention_type="post_deleted",
                details={
                    "post_id": payload["post_id"],
                },
            )
        return ""

    async def do_survey(self, survey: Survey) -> str:
        """
        Generate a response to a user survey based on the agent's memory and current state.

        - **Args**:
            - `survey` (`Survey`): The survey that needs to be answered.

        - **Returns**:
            - `str`: The generated response from the agent.

        - **Description**:
            - Prepares a prompt for the Language Model (LLM) based on the provided survey.
            - Constructs a dialog including system prompts, relevant memory context, and the survey question itself.
            - Uses the LLM client to generate a response asynchronously.
            - If the LLM client is not available, it returns a default message indicating unavailability.
            - This method can be overridden by subclasses to customize survey response generation.
        """
        survey_prompt = ""
        for page in survey.pages:
            for question in page.elements:
                survey_prompt += f"{question.title}\n"
        dialog = []

        # Add memory context
        message_summary = self.social_block.history_summary
        preference = await self.memory.status.get("message_propagation_preference", "")

        # Add survey question
        dialog.append(
            {
                "role": "user",
                "content": survey_prompt
                + f"\n{self.social_block.preference_appendix.get(preference, '')}\n"
                + f"你预先了解到的信息：\n{message_summary}\n",
            }
        )

        survey_request_history = await self.memory.status.get("survey_request_history")
        survey_request_history.append(dialog)
        await self.memory.status.update(
            "survey_request_history", survey_request_history
        )

        for retry in range(10):
            try:
                # Use LLM to generate a response
                # print(f"dialog: {dialog}")
                _response = await self.llm.atext_request(dialog)
                return _response.strip()
            except:
                pass
        else:
            import traceback

            traceback.print_exc()
            get_logger().error("Failed to generate survey response")
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

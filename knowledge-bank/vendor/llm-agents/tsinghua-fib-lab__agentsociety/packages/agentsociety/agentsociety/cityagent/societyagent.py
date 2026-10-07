import random
import time

from typing import Optional

import json_repair

from ..agent import (
    AgentToolbox,
    Block,
    CitizenAgentBase,
    FormatPrompt,
    MemoryAttribute,
)
from ..logger import get_logger
from ..memory import Memory
from .blocks import CognitionBlock, NeedsBlock, PlanBlock
from .sharing_params import (
    SocietyAgentConfig,
    SocietyAgentBlockOutput,
    SocietyAgentContext,
)
from ..message import Message

ENVIRONMENT_REFLECTION_PROMPT = """
You are a citizen of the city.
Your occupation: {occupation}
Your age: {age}
Your current emotion: {emotion_types}

In your current location, you can sense the following information:
{area_information}

What's your feeling about those environmental information?
"""


class SocietyAgent(CitizenAgentBase):
    ParamsType = SocietyAgentConfig
    BlockOutputType = SocietyAgentBlockOutput
    Context = SocietyAgentContext
    StatusAttributes = [
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
        # cognition
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
            name="depression",
            type=float,
            default_or_value=0.0,
            description="agent's depression, 0-1",
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
        # social
        MemoryAttribute(
            name="social_network",
            type=list,
            default_or_value=[],
            description="all social network",
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
        # mobility
        MemoryAttribute(
            name="number_poi_visited",
            type=int,
            default_or_value=1,
            description="agent's number of poi visited",
        ),
    ]
    description: str = """
A social agent that can interact with other agents and the environment.
The main workflow includes:
1. Agent needs determination (based on Maxlow's Hierarchy Needs) —— including hunger needs, safety needs, social needs and emergency needs)
2. Plan generation (The citizen generate a detailed plan based on the needs)
3. Step execution (The citizen execute the action based on the generated plan)

Notice: The capability of citizen is controled by the BLOCKS (defaultly, it contains 4 blocks:
1). MobilityBlock: endow the citizen with the ability to move around the city
2). EconomyBlock: endow the citizen with the ability to shoping and working
3). SocialBlock: endow the citizen with the ability to socializing with other citizens
4). OtherBlocks: handle other intentions (e.g., cooking, sleeping, etc.)

You can add more blocks to the citizen as you wish to adapt to the different scenarios. We strongly recommend you keep the default blocks as they are.
"""

    """Agent implementation with configurable cognitive/behavioral modules and social interaction capabilities."""

    def __init__(
        self,
        id: int,
        name: str,
        toolbox: AgentToolbox,
        memory: Memory,
        agent_params: Optional[SocietyAgentConfig] = None,
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

        self.needs_block = NeedsBlock(
            toolbox=self._toolbox,
            agent_memory=self.memory,
            agent_context=self.context,
            initial_prompt=self.params.need_initialization_prompt,
        )

        self.plan_block = PlanBlock(
            agent=self,
            toolbox=self._toolbox,
            agent_memory=self.memory,
            agent_context=self.context,
            max_plan_steps=self.params.max_plan_steps,
            detailed_plan_prompt=self.params.plan_generation_prompt,
        )

        self.cognition_block = CognitionBlock(
            toolbox=self._toolbox,
            agent_memory=self.memory,
        )
        self.environment_reflection_prompt = FormatPrompt(
            ENVIRONMENT_REFLECTION_PROMPT, memory=self.memory
        )

        # register blocks
        self.dispatcher.register_dispatcher_prompt(self.params.block_dispatch_prompt)

        self.step_count = -1
        self.cognition_update = -1

    async def status_summary(self):
        """
        Status summary
        """
        # Environment Information
        current_time = self.context.current_time
        weather = self.context.weather
        temperature = self.context.temperature
        other_information = self.context.other_information

        # Agent Profile
        name = await self.memory.status.get("name")
        occupation = await self.memory.status.get("occupation")
        age = await self.memory.status.get("age")
        gender = await self.memory.status.get("gender")
        education = await self.memory.status.get("education")
        personality = await self.memory.status.get("personality")
        background_story = await self.memory.status.get("background_story")

        # Current Status
        current_need = self.context.current_need
        current_plan_target = self.context.plan_target
        current_intention = self.context.current_intention
        current_emotion = self.context.current_emotion
        current_thought = self.context.current_thought
        current_location = self.context.current_location

        # Create LLM prompt for status description
        status_description_prompt = f"""
Based on the following information, provide a concise 1-2 sentence description of the agent's current status:

**Agent Profile:**
- Name: {name}
- Age: {age}
- Gender: {gender}
- Occupation: {occupation}
- Education: {education}
- Personality: {personality}
- Background: {background_story}

**Current Environment:**
- Time: {current_time}
- Weather: {weather}
- Temperature: {temperature}
- Location: {current_location}
- Other Information: {other_information}

**Current Status:**
- Current Need: {current_need}
- Plan Target: {current_plan_target}
- Current Intention: {current_intention}
- Emotion: {current_emotion}
- Thought: {current_thought}

Please provide a natural, human-like description of what the agent is currently doing and feeling, considering their personality, current situation, and environment. Focus on the most relevant aspects that define their current state.

Response format: 1-2 sentences describing the agent's current status from a first-person perspective.

Example:
"I am working at the office, the work is not too busy, but I am a bit tired."
"""
        summary_text = await self.llm.atext_request([
            {"role": "system", "content": "You are an AI assistant that describes the current status of a citizen agent in a city simulation."},
            {"role": "user", "content": status_description_prompt}
        ])
        await self.memory.status.update("status_summary", summary_text)

    async def before_forward(self):
        """Before forward"""
        await super().before_forward()
        assert self.environment is not None
        # preparing context values
        # Current Time
        now_time = self.environment.get_datetime(format_time=True)
        self.context.current_time = now_time[1]

        # Current Emotion
        emotion_types = await self.memory.status.get("emotion_types")
        self.context.current_emotion = emotion_types

        # Current Thought
        thought = await self.memory.status.get("thought")
        self.context.current_thought = thought

        # Current Location
        position_now = await self.memory.status.get("position")
        home_location = await self.memory.status.get("home")
        work_location = await self.memory.status.get("work")
        current_location = "Outside"
        if (
            "aoi_position" in position_now
            and position_now["aoi_position"] == home_location["aoi_position"]
        ):
            current_location = "At home"
        elif (
            "aoi_position" in position_now
            and position_now["aoi_position"] == work_location["aoi_position"]
        ):
            current_location = "At workplace"
        self.context.current_position = current_location

        # Area Information
        aoi_info = await self.get_aoi_info()
        if not aoi_info:
            self.context.area_information = "Don't know"
        else:
            self.context.area_information = aoi_info

        # Weather
        weather_info = self.environment.sense("weather")
        self.context.weather = weather_info

        # Temperature
        temperature_info = self.environment.sense("temperature")
        self.context.temperature = temperature_info

        # Other Information
        other_info = self.environment.sense("other_information")
        self.context.other_information = other_info

    async def reset(self):
        """Reset the agent."""
        # reset position to home
        await self.reset_position()

        # reset needs
        await self.memory.status.update("current_need", "none")

        # reset plans and actions
        await self.memory.status.update("current_plan", {})
        await self.memory.status.update("execution_context", {})

        # reset initial flag
        await self.needs_block.reset()

    async def plan_generation(self):
        """Generate a new plan if no current plan exists in memory."""
        cognition = None
        current_plan = await self.memory.status.get("current_plan", False)
        if current_plan is None or not current_plan:
            cognition = (
                await self.plan_block.forward()
            )  # Delegate to PlanBlock for plan creation
        return cognition

    async def reflect_to_environment(self):
        """Reflect to the environment"""
        aoi_info = await self.get_aoi_info()
        if aoi_info:
            await self.environment_reflection_prompt.format()
            reflection = await self.llm.atext_request(
                self.environment_reflection_prompt.to_dialog()
            )
            await self.save_agent_thought(reflection)

    # Main workflow
    async def forward(self):
        """Main agent loop coordinating status updates, plan execution, and cognition."""
        start_time = time.time()
        self.step_count += 1

        # reflect to environment
        await self.reflect_to_environment()

        # check last step
        ifpass = await self.check_and_update_step()
        if not ifpass:
            return
        get_logger().debug(
            f"Agent {self.id}: Finished main workflow - check and update step"
        )

        # Maxlow's Needs
        cognition = await self.needs_block.forward()
        if self.params.enable_cognition and cognition:
            await self.save_agent_thought(cognition)

        # Planned-Behavior
        cognition = await self.plan_generation()
        if cognition:
            await self.save_agent_thought(cognition)
        get_logger().debug(f"Agent {self.id}: Finished main workflow - plan")

        # step execution - dispatch to different blocks
        await self.step_execution()
        get_logger().debug(f"Agent {self.id}: Finished main workflow - step execution")

        # cognition
        if self.params.enable_cognition:
            await self.cognition_block.forward()
        get_logger().debug(f"Agent {self.id}: Finished main workflow - cognition")

        return time.time() - start_time

    async def check_and_update_step(self):
        """Check if the previous step has been completed"""
        assert self.environment is not None
        status = await self.memory.status.get("status")
        if status == 2:
            # Agent is moving
            return False

        # Get the previous step information
        current_plan = await self.memory.status.get("current_plan", False)
        # If there is no current plan, return True
        if current_plan is None or not current_plan:
            return True
        step_index = current_plan.get("index", 0)
        current_step = current_plan.get("steps", [])[step_index]
        time_now = self.environment.get_tick()
        step_start_time = current_step["start_time"]
        step_consumed_time = current_step["evaluation"]["consumed_time"]
        try:
            time_end_plan = step_start_time + int(step_consumed_time) * 60
        except Exception as e:
            get_logger().warning(f"Error in check_and_update_step: {str(e)}")
            time_end_plan = time_now
        if time_now >= time_end_plan:
            # The previous step has been completed
            current_step["evaluation"]["consumed_time"] = (
                time_now - step_start_time
            ) / 60
            current_plan["stream_nodes"].append(current_step["evaluation"]["node_id"])
            if current_step["evaluation"]["success"]:
                # last step is completed
                current_plan["steps"][step_index] = current_step
                if step_index + 1 < len(current_plan["steps"]):
                    # Last step is completed
                    current_plan["index"] = step_index + 1
                    await self.memory.status.update("current_plan", current_plan)
                else:
                    # Whole plan is completed
                    current_plan["completed"] = True
                    _, current_plan["end_time"] = self.environment.get_datetime(
                        format_time=True
                    )
                    related_memories = None
                    if self.params.enable_cognition:
                        try:
                            # Update emotion for the plan
                            related_memories = await self.memory.stream.get_by_ids(
                                current_plan["stream_nodes"]
                            )
                            incident = f"You have successfully completed the plan: {related_memories}"
                            conclusion = await self.cognition_block.emotion_update(
                                incident
                            )
                            await self.save_agent_thought(conclusion)
                            await self.memory.stream.add_cognition_to_memory(
                                current_plan["stream_nodes"], conclusion
                            )
                        except Exception as e:
                            get_logger().warning(
                                f"Check_and_update_step (emotion_update): {str(e)}"
                            )
                    await self.memory.status.update("current_plan", current_plan)
                return True
            else:
                # last step is failed
                current_plan["failed"] = True
                _, current_plan["end_time"] = self.environment.get_datetime(
                    format_time=True
                )
                if self.params.enable_cognition:
                    related_memories = None
                    try:
                        # Update emotion for the plan
                        related_memories = await self.memory.stream.get_by_ids(
                            current_plan["stream_nodes"]
                        )
                        incident = (
                            f"You have failed to complete the plan: {related_memories}"
                        )
                        conclusion = await self.cognition_block.emotion_update(incident)
                        await self.save_agent_thought(conclusion)
                        await self.memory.stream.add_cognition_to_memory(
                            current_plan["stream_nodes"], conclusion
                        )
                    except Exception as e:
                        get_logger().warning(
                            f"Check_and_update_step (emotion_update): {str(e)}"
                        )
                await self.memory.status.update("current_plan", current_plan)
                return True
        # The previous step has not been completed
        return False

    async def do_chat(self, message: Message) -> str:
        """Process incoming social/economic messages and generate responses."""
        payload = message.payload
        if payload.get("type", "social") == "social":
            try:
                # Extract basic info
                sender_id = message.from_id
                if not sender_id:
                    return ""

                content = payload.get("content", "Hello, how are you?")
                if isinstance(content, dict):
                    content = content.get("content", "Hello, how are you?")

                # add social memory
                description = f"You received a social message: {content}"
                await self.memory.stream.add(topic="social", description=description)
                if self.params.enable_cognition:
                    # update emotion
                    await self.cognition_block.emotion_update(description)

                # Get chat histories and ensure proper format
                chat_histories = await self.memory.status.get("chat_histories") or {}
                if not isinstance(chat_histories, dict):
                    chat_histories = {}

                # Update chat history with received message
                if sender_id not in chat_histories:
                    chat_histories[sender_id] = ""
                if chat_histories[sender_id]:
                    chat_histories[sender_id] += "，"
                chat_histories[sender_id] += f"he/she: {content}"

                # Get relationship strength and type
                my_social_network = await self.memory.status.get("social_network", [])
                relationship_strength = 0.0
                relationship_type = "I don't know him/her"
                for relation in my_social_network:
                    if relation.target_id == sender_id:
                        relationship_strength = relation.strength
                        relationship_type = relation.kind
                        break

                recent_chat_history = chat_histories.get(sender_id, "No chat history")
                get_logger().info(f"Recent chat history: {recent_chat_history}")
                try:
                    recent_chat_history = recent_chat_history[-200:]
                except Exception as e:
                    get_logger().warning(f"Error in do_chat (recent_chat_history): {str(e)}")
                    recent_chat_history = "No chat history"

                current_intention = "I am doing nothing"
                current_plan = await self.memory.status.get("current_plan")
                if (
                    current_plan is None
                    or not current_plan
                    or len(current_plan.get("steps", [])) == 0
                ):
                    current_intention = "I am doing nothing"
                else:
                    step_index = current_plan.get("index", 0)
                    current_step = current_plan.get("steps", [])[step_index]
                    current_intention = current_step.get("intention", "I am doing nothing")

                # Decision prompt
                should_respond_prompt = f"""
My current action/intention is: {current_intention}
My profile: 
    - gender: {await self.memory.status.get("gender", "unknown")}
    - education: {await self.memory.status.get("education", "unknown")}
    - personality: {await self.memory.status.get("personality", "unknown")}
    - occupation: {await self.memory.status.get("occupation", "unknown")}
    - background_story: {await self.memory.status.get("background_story", "unknown")}
My current emotion: {await self.memory.status.get("emotion_types", "unknown")}

I received a message:{content}
    - My relationship strength with him/her: {relationship_strength}
    - Our relationship type: {relationship_type}
    - Recent chat history: {recent_chat_history}

Based on the above all information, should I respond to this message? If I should respond, what should I say?
1. Is this a message that needs/deserves a response?
2. If you think the conversation should end, you should not respond or end quick and say goodbye.
3. If I should respond, what should I say? (only output the response content from a first person perspective, no other text)
4. If I am busy, I should not respond or tell him/her that I am busy.
5. The length of the social message should be less than 20 characters.
6. If I need to respond, I should respond in a natural way, not like a robot, talk in the point but not nonsense.

Answer only YES or NO, in JSON format, e.g. {{"should_respond": "YES", "response_content": "Hello, how are you?(optional)"}}"""

                respond = await self.llm.atext_request(
                    dialog=[
                        {
                            "role": "system",
                            "content": "You are helping decide whether to respond to a message, and if so, what to say.",
                        },
                        {"role": "user", "content": should_respond_prompt},
                    ],
                    response_format={"type": "json_object"},
                )
                should_respond = json_repair.loads(respond)["should_respond"]  # type: ignore
                if should_respond == "NO":
                    return ""
                response_content = json_repair.loads(respond)["response_content"]  # type: ignore
                if response_content:
                    # Update chat history with response
                    chat_histories[sender_id] += f"，me: {response_content}"
                    await self.memory.status.update("chat_histories", chat_histories)

                    # Send response
                    await self.send_message_to_agent(sender_id, response_content)
                    return response_content
                else:
                    return ""
            except Exception as e:
                get_logger().warning(f"SocietyAgent Error in do_chat: {str(e)}")
                return ""
        else:
            content = payload["content"]
            key, value = content.split("@")
            if "." in value:
                value = float(value)
            else:
                value = int(value)
            description = f"You received a economic message: Your {key} has changed from {await self.memory.status.get(key)} to {value}"
            await self.memory.status.update(key, value)
            await self.memory.stream.add(topic="economy", description=description)
            if self.params.enable_cognition:
                await self.cognition_block.emotion_update(description)
            return ""

    async def react_to_intervention(self, intervention_message: str):
        """React to an intervention"""
        # cognition
        conclusion = await self.cognition_block.emotion_update(intervention_message)
        await self.save_agent_thought(conclusion)
        await self.memory.stream.add(topic="cognition", description=conclusion)
        # needs
        await self.needs_block.reflect_to_intervention(intervention_message)

    async def reset_position(self):
        """Reset the position of the agent."""
        assert self.environment is not None
        home = await self.status.get("home")
        home = home["aoi_position"]["aoi_id"]
        await self.environment.reset_person_position(person_id=self.id, aoi_id=home)

    async def step_execution(self):
        """Execute the current step in the active plan based on step type."""
        assert self.environment is not None
        current_plan = await self.memory.status.get("current_plan")
        if (
            current_plan is None
            or not current_plan
            or len(current_plan.get("steps", [])) == 0
        ):
            return  # No plan, no execution
        step_index = current_plan.get("index", 0)
        execution_context = await self.memory.status.get("execution_context")
        current_step = current_plan.get("steps", [])[step_index]
        # check current_step is valid (not empty)
        if current_step:
            self.context.current_step = current_step
            self.context.current_intention = current_step["intention"]
            self.context.plan_context = execution_context
            position = await self.memory.status.get("position")
            if "aoi_position" in position:
                current_step["position"] = position["aoi_position"]["aoi_id"]
            current_step["start_time"] = self.environment.get_tick()
            result = None
            if self.blocks and len(self.blocks) > 0:
                selected_block = await self.dispatcher.dispatch(self.context)
                if selected_block:
                    result = await selected_block.forward(self.context)
                    result = result.model_dump()
                else:
                    get_logger().warning(
                        f"There is no appropriate block found for {self.context['current_intention']}"
                    )
                    node_id = await self.memory.stream.add(
                        topic="activity",
                        description=f"I finished: {self.context['current_intention']}",
                    )
                    result = {
                        "success": True,
                        "evaluation": f"I finished: {self.context['current_intention']}",
                        "consumed_time": random.randint(1, 100),
                        "node_id": node_id,
                    }
            else:
                get_logger().warning(
                    f"There is no block found for {self.context['current_intention']}"
                )
                node_id = await self.memory.stream.add(
                    topic="activity",
                    description=f"I finished: {self.context['current_intention']}",
                )
                result = {
                    "success": True,
                    "evaluation": f"I finished: {self.context['current_intention']}",
                    "consumed_time": random.randint(1, 100),
                    "node_id": node_id,
                }
            if result is not None:
                current_step["evaluation"] = result

            # Update current_step, plan, and execution_context information
            current_plan["steps"][step_index] = current_step
            await self.memory.status.update("current_plan", current_plan)
            await self.memory.status.update("execution_context", execution_context)

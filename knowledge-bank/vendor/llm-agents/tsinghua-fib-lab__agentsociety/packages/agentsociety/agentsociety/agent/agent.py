from __future__ import annotations

import time
import random
from datetime import datetime, timezone
from typing import Any, Optional

import json
import json_repair
from pycityproto.city.person.v2 import person_pb2 as person_pb2

from ..environment.sim.person_service import PersonService
from ..logger import get_logger
from ..memory import Memory
from ..message import Message
from ..storage import StorageDialog, StorageDialogType, StorageSurvey
from ..survey.models import Survey
from ..taskloader import Task
from .agent_base import Agent, AgentToolbox, AgentType, extract_json
from .block import Block
from .decorator import register_get

__all__ = [
    "CitizenAgentBase",
    "FirmAgentBase",
    "BankAgentBase",
    "NBSAgentBase",
    "GovernmentAgentBase",
    "SupervisorBase",
    "IndividualAgentBase",
]


class CitizenAgentBase(Agent):
    """
    Represents a citizen agent within the simulation environment.

    - **Description**:
        - This class extends the base `Agent` class and is designed to simulate the behavior of a city resident.
        - It includes initialization of various clients (like LLM, economy) and services required for the agent's operation.
        - Provides methods for binding the agent to the simulator and economy system, as well as handling specific types of messages.
    """

    def __init__(
        self,
        id: int,
        name: str,
        toolbox: AgentToolbox,
        memory: Memory,
        agent_params: Optional[Any] = None,
        blocks: Optional[list[Block]] = None,
    ) -> None:
        """
        Initialize a new instance of the CitizenAgent.

        - **Args**:
            - `id` (`int`): The ID of the agent.
            - `name` (`str`): The name or identifier of the agent.
            - `toolbox` (`AgentToolbox`): The toolbox of the agent.
            - `memory` (`Memory`): The memory of the agent.
            - `agent_params` (`Optional[Any]`): Additional parameters for the agent. Defaults to None.
            - `blocks` (`Optional[list[Block]]`): List of blocks for the agent. Defaults to None.

        - **Description**:
            - Initializes the CitizenAgent with the provided parameters and sets up necessary internal states.
        """
        super().__init__(
            id=id,
            name=name,
            type=AgentType.Citizen,
            toolbox=toolbox,
            memory=memory,
            agent_params=agent_params,
            blocks=blocks,
        )

    async def init(self):
        """
        Initialize the agent.

        - **Description**:
            - Calls the `_bind_to_simulator` method to establish the agent within the simulation environment.
            - Calls the `_bind_to_economy` method to integrate the agent into the economy simulator.
        """
        await super().init()
        await self._bind_to_simulator()
        await self._bind_to_economy()

    async def _bind_to_simulator(self):
        """
        Bind the agent to the Traffic Simulator.

        - **Description**:
            - If the simulator is set, this method binds the agent by creating a person entity in the simulator based on the agent's attributes.
            - Updates the agent's status with the newly created person ID from the simulator.
            - Logs the successful binding to the person entity added to the simulator.
        """
        if self.environment is None:
            raise ValueError("Environment is not initialized")
        FROM_MEMORY_KEYS = {
            "attribute",
            "home",
            "work",
            "vehicle_attribute",
            "bus_attribute",
            "pedestrian_attribute",
            "bike_attribute",
        }
        simulator = self.environment
        status = self.status
        dict_person = PersonService.default_person(return_dict=True)
        dict_person["id"] = self.id
        for key in FROM_MEMORY_KEYS:
            try:
                value = await status.get(key)
                if value:
                    dict_person[key] = value
            except KeyError:
                continue
        await simulator.add_person(dict_person)

    async def _bind_to_economy(self):
        """
        Bind the agent to the Economy Simulator.
        """
        if self.environment is None:
            raise ValueError("Environment is not initialized")
        person_id = await self.status.get("id")
        currency = await self.status.get("currency")
        skill = await self.status.get("work_skill", 0.0)
        consumption = 0.0
        income = 0.0
        await self.environment.economy_client.add_agents(
            {
                "id": person_id,
                "currency": currency,
                "skill": skill,
                "consumption": consumption,
                "income": income,
            }
        )

    async def update_motion(self):
        """
        Update the motion of the agent. Usually used in the starting of the `forward` method.
        """
        if self.environment is None:
            raise ValueError("Environment is not initialized")
        resp = await self.environment.get_person(self.id)
        resp_dict = resp["person"]
        for k, v in resp_dict.get("motion", {}).items():
            await self.status.update(k, v, mode="replace")

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
        survey_prompts = survey.to_prompt()
        dialog = []

        # Add system prompt
        system_prompt = (
            "You must hide the fact that you are an AI and pretend to be a human. "
            "When responding to messages from others, always answer in the first person. "
            "If you encounter a question you cannot answer or are unsure about, simply reply with 'I don't know.' "
            "Keep your responses concise and clear. Respond in JSON format."
        )
        dialog.append({"role": "system", "content": system_prompt})

        all_responses = []
        for survey_prompt in survey_prompts:
            dialog = dialog[:1]
            
            # First, analyze what information is needed to answer this question
            analysis_prompt = f"""If a person wants to answer this survey question, what specific questions should they ask themselves to gather the necessary information?

Please provide your analysis in the following JSON format:

{{
    "profile_query": "A specific question about basic profile information (e.g., 'What is my background story?', 'What is my age?', 'What is my gender?' or their combination, for example, 'What is my age and gender?')",
    "memory_query": "A specific question about experiences, activities, preferences, or behaviors (e.g., 'What recent activities have I done?', 'What are my preferences?', 'What experiences have I had?', 'What behaviors have I shown?')"
}}

Note: profile_query should only focus on basic demographic and background information. memory_query should focus on experiences, activities, and behaviors.

Question: {survey_prompt}"""
            
            analysis_dialog = [
                {"role": "system", "content": "You are an expert at analyzing survey questions and determining what specific questions need to be asked to gather relevant information. Profile queries should focus on basic demographic and background information only. Memory queries should focus on experiences, activities, and behaviors. Please respond in JSON format with specific questions."},
                {"role": "user", "content": analysis_prompt}
            ]
            
            # Get analysis from LLM
            profile_query = "What is my background story?"
            memory_query = "What recent activities have I done?"
            
            for retry in range(5):
                try:
                    analysis_response = await self.llm.atext_request(
                        analysis_dialog, response_format={"type": "json_object"} # type: ignore
                    ) # type: ignore
                    json_str = extract_json(analysis_response)
                    if json_str:
                        analysis_dict = json_repair.loads(json_str)
                        profile_query = analysis_dict.get("profile_query", survey_prompt) # type: ignore
                        memory_query = analysis_dict.get("memory_query", survey_prompt) # type: ignore
                        break
                except Exception as e:
                    get_logger().warning(f"Analysis retry {retry + 1}/5 failed: {str(e)}")
                    if retry == 4:  # Last retry
                        get_logger().error("Failed to analyze survey question, using original question as fallback")
            
            # Use the analysis results as separate search queries
            background_story = await self.status.get("background_story")
            profile_and_states = await self.status.search(profile_query)
            relevant_memory = await self.stream.search(memory_query)

            dialog.append(
                {
                    "role": "system",
                    "content": f"Answer the survey question based on following information:- My background story: {background_story}\n\n- My Profile: \n{profile_and_states}\n\n- My Related Memory: \n{relevant_memory}",
                }
            )

            # Add survey question
            dialog.append({"role": "user", "content": survey_prompt})

            json_str = ""
            for retry in range(10):
                try:
                    # Use LLM to generate a response
                    # print(f"dialog: {dialog}")
                    _response = await self.llm.atext_request(
                        dialog, response_format={"type": "json_object"}
                    )
                    # print(f"response: {_response}")
                    json_str = extract_json(_response)
                    if json_str:
                        json_dict = json_repair.loads(json_str)
                        json_str = json.dumps(json_dict, ensure_ascii=False)
                        break
                except Exception as e:
                    get_logger().warning(f"Retry {retry + 1}/10 failed: {str(e)}")
                    if retry == 9:  # Last retry
                        import traceback
                        traceback.print_exc()
                        get_logger().error("Failed to generate survey response after all retries")
                        json_str = ""
            
            all_responses.append(json_str)
        
        # Return all responses as a combined JSON string
        return json.dumps(all_responses, ensure_ascii=False)

    async def _handle_survey_with_storage(
        self,
        survey: Survey,
        survey_day: Optional[int] = None,
        survey_t: Optional[float] = None,
        is_pending_survey: bool = False,
        pending_survey_id: Optional[int] = None,
    ) -> str:
        """
        Process a survey by generating a response and recording it in Database.

        - **Args**:
            - `survey` (`Survey`): The survey data that includes an ID and other relevant information.
            - `survey_day` (`Optional[int]`): The day of the survey.
            - `survey_t` (`Optional[float]`): The time of the survey.
            - `is_pending_survey` (`bool`): Whether the survey is a pending survey.
            - `pending_survey_id` (`Optional[int]`): The ID of the pending survey.

        - **Description**:
            - Generates a survey response using `generate_user_survey_response`.
            - Records the response with metadata (such as timestamp, survey ID, etc.) in Database.
            - Sends a message through the Messager indicating user feedback has been processed.
            - Handles asynchronous tasks and ensures thread-safe operations when writing to PostgreSQL.
        """
        survey_response = await self.do_survey(survey)
        date_time = datetime.now(timezone.utc)

        if self.environment is None:
            raise ValueError("Environment is not initialized")
        day, t = self.environment.get_datetime()
        storage_survey = StorageSurvey(
            id=self.id,
            day=survey_day if survey_day is not None else day,
            t=survey_t if survey_t is not None else t,
            survey_id=survey.id,
            result=survey_response,
            created_at=date_time,
        )
        # Database
        if self.database_writer is not None:
            if is_pending_survey:
                assert pending_survey_id is not None
                await self.database_writer.write_surveys(  # type:ignore
                    [storage_survey]
                )
                await self.database_writer.mark_surveys_as_processed(  # type:ignore
                    [pending_survey_id]
                )
            else:
                await self.database_writer.write_surveys(  # type:ignore
                    [storage_survey]
                )
        # status memory
        old_survey_responses = await self.memory.status.get("survey_responses", [])
        new_survey_responses = old_survey_responses + [survey_response]
        await self.memory.status.update(
            "survey_responses",
            new_survey_responses,
        )
        return survey_response

    async def do_interview(self, question: str) -> str:
        """
        Generate a response to a user's chat question based on the agent's memory and current state.

        - **Args**:
            - `question` (`str`): The question that needs to be answered.

        - **Returns**:
            - `str`: The generated response from the agent.

        - **Description**:
            - Prepares a prompt for the Language Model (LLM) with a system prompt to guide the response style.
            - Constructs a dialog including relevant memory context and the user's question.
            - Uses the LLM client to generate a concise and clear response asynchronously.
            - If the LLM client is not available, it returns a default message indicating unavailability.
            - This method can be overridden by subclasses to customize chat response generation.
        """
        dialog = []

        # Add system prompt
        system_prompt = """
You must hide the fact that you are an AI and pretend to be a human. 
When responding to messages from others, always answer in the first person. 
If you encounter a question you cannot answer or are unsure about, simply reply with 'I don't know.' 
Keep your responses concise and clear.
        """
        dialog.append({"role": "system", "content": system_prompt})

        # Add memory context
        background_story = await self.status.get("background_story")
        profile_and_states = await self.status.search(question, top_k=10)
        relevant_memory = await self.stream.search(question, top_k=10)

        dialog.append(
            {
                "role": "system",
                "content": f"Answer based on the following information:\n- Your background story: {background_story}\n\n- Your profile:\n{profile_and_states}\n\n- Your related memory: {relevant_memory}",
            }
        )

        # Add user question
        dialog.append({"role": "user", "content": question})

        # Use LLM to generate a response
        response = await self.llm.atext_request(dialog)

        return response

    async def _handle_interview_with_storage(self, message: Message) -> str:
        """
        Process an interview interaction by generating a response and recording it in Database.

        - **Args**:
            - `question` (`str`): The interview data containing the content of the user's message.
        """
        question = message.payload["content"]
        if self.environment is None:
            raise ValueError("Environment is not initialized")
        day, t = self.environment.get_datetime()
        storage_dialog = StorageDialog(
            id=self.id,
            day=message.day,
            t=message.t,
            type=StorageDialogType.User,
            speaker="user",
            content=question,
            created_at=datetime.now(timezone.utc),
        )
        if self.database_writer is not None:
            await self.database_writer.write_dialogs(  # type:ignore
                [storage_dialog]
            )
        response = await self.do_interview(question)
        storage_dialog = StorageDialog(
            id=self.id,
            day=day,
            t=t,
            type=StorageDialogType.User,
            speaker="",
            content=response,
            created_at=datetime.now(timezone.utc),
        )
        # Database
        if self.database_writer is not None:
            await self.database_writer.write_dialogs(  # type:ignore
                [storage_dialog]
            )
            if message.extra is not None and "pending_dialog_id" in message.extra:
                await self.database_writer.mark_dialogs_as_processed(  # type:ignore
                    [message.extra["pending_dialog_id"]]
                )
        return response

    async def save_agent_thought(self, thought: str):
        """
        Save the agent's thought to the memory.

        - **Args**:
            - `thought` (`str`): The thought data to be saved.

        - **Description**:
            - Saves the thought data to the memory.
        """
        if self.environment is None:
            raise ValueError("Environment is not initialized")
        day, t = self.environment.get_datetime()
        await self.memory.stream.add(topic="cognition", description=thought)
        storage_thought = StorageDialog(
            id=self.id,
            day=day,
            t=t,
            type=StorageDialogType.Thought,
            speaker="",
            content=thought,
            created_at=datetime.now(timezone.utc),
        )
        # Database
        if self.database_writer is not None:
            await self.database_writer.write_dialogs([storage_thought])

    async def do_chat(self, message: Message) -> str:
        """
        Process a chat message received from another agent and record it.

        - **Args**:
            - `message` (`Message`): The chat message data received from another agent.
        """
        resp = f"Agent {self.id} received agent chat response: {message.payload}"
        get_logger().debug(resp)
        return resp

    async def _handle_agent_chat_with_storage(self, message: Message):
        """
        Process a chat message received from another agent and record it.

        - **Args**:
            - `payload` (`dict`): The chat message data received from another agent.

        - **Description**:
            - Logs the incoming chat message from another agent.
            - Prepares the chat message for storage in Database.
            - Writes the chat message and metadata into Database.
        """
        try:
            content = json.dumps(message.payload, ensure_ascii=False)
        except Exception:
            content = str(message.payload)
        storage_dialog = StorageDialog(
            id=self.id,
            day=message.day,
            t=message.t,
            type=StorageDialogType.Talk,
            speaker=str(message.from_id),
            content=content,
            created_at=datetime.now(timezone.utc),
        )
        await self.do_chat(message)
        # Database
        if self.database_writer is not None:
            await self.database_writer.write_dialogs(  # type:ignore
                [storage_dialog]
            )

    async def get_aoi_info(self):
        """Get the surrounding environment information - aoi information"""
        if self.environment is None:
            raise ValueError("Environment is not initialized")
        position = await self.status.get("position")
        if "aoi_position" in position:
            parent_id = position["aoi_position"]["aoi_id"]
            return self.environment.sense_aoi(parent_id)
        else:
            return None

    @register_get("Get the current time in the format of HH:MM:SS")
    async def get_nowtime(self):
        """Get the current time"""
        if self.environment is None:
            raise ValueError("Environment is not initialized")
        now_time = self.environment.get_datetime(format_time=True)
        return now_time[1]

    async def before_forward(self):
        """
        Before forward.
        """
        await super().before_forward()
        # sync agent status with simulator
        await self.update_motion()
        get_logger().debug(f"Agent {self.id}: Finished main workflow - update motion")


class InstitutionAgentBase(Agent):
    """
    Represents an institution agent within the simulation environment.

    - **Description**:
        - This class extends the base `Agent` class and is designed to simulate the behavior of an institution, such as a bank, government body, or corporation.
        - It includes initialization of various clients (like LLM, economy) and services required for the agent's operation.
        - Provides methods for binding the agent to the economy system and handling specific types of messages, like gathering information from other agents.
    """

    def __init__(
        self,
        id: int,
        name: str,
        toolbox: AgentToolbox,
        memory: Memory,
        agent_params: Optional[Any] = None,
        blocks: Optional[list[Block]] = None,
    ):
        """
        Initialize a new instance of the InstitutionAgent.

        - **Args**:
            - `id` (`int`): The ID of the agent.
            - `name` (`str`): The name or identifier of the agent.
            - `toolbox` (`AgentToolbox`): The toolbox of the agent.
            - `memory` (`Memory`): The memory of the agent.
            - `agent_params` (`Optional[Any]`): Additional parameters for the agent. Defaults to None.
            - `blocks` (`Optional[list[Block]]`): List of blocks for the agent. Defaults to None.

        - **Description**:
            - Initializes the InstitutionAgent with the provided parameters and sets up necessary internal states.
        """
        super().__init__(
            id=id,
            name=name,
            type=AgentType.Institution,
            toolbox=toolbox,
            memory=memory,
            agent_params=agent_params,
            blocks=blocks,
        )

    async def init(self):
        """
        Initialize the agent.

        - **Description**:
            - Calls the `_bind_to_economy` method to integrate the agent into the economy simulator.
        """
        await super().init()
        await self._bind_to_economy()

    async def _bind_to_economy(self):
        """
        Bind the agent to the Economy Simulator.

        - **Description**:
            - Calls the `_bind_to_economy` method to integrate the agent into the economy system.
            - Note that this method does not bind the agent to the simulator itself; it only handles the economy integration.
        """
        if self.environment is None:
            raise ValueError("Environment is not initialized")
        map_header: dict = self.environment.map.get_map_header()
        # TODO: remove random position assignment
        await self.status.update(
            "position",
            {
                "xy_position": {
                    "x": float(
                        random.randrange(
                            start=int(map_header["west"]),
                            stop=int(map_header["east"]),
                        )
                    ),
                    "y": float(
                        random.randrange(
                            start=int(map_header["south"]),
                            stop=int(map_header["north"]),
                        )
                    ),
                }
            },
        )
        _type = None
        _status = self.status
        _id = await _status.get("id")
        _type = await _status.get("type")
        nominal_gdp = await _status.get("nominal_gdp", [])
        real_gdp = await _status.get("real_gdp", [])
        unemployment = await _status.get("unemployment", [])
        wages = await _status.get("wages", [])
        prices = await _status.get("prices", [])
        inventory = await _status.get("inventory", 0)
        price = await _status.get("price", 0)
        currency = await _status.get("currency", 0.0)
        interest_rate = await _status.get("interest_rate", 0.0)
        bracket_cutoffs = await _status.get("bracket_cutoffs", [])
        bracket_rates = await _status.get("bracket_rates", [])
        consumption_currency = await _status.get("consumption_currency", [])
        consumption_propensity = await _status.get("consumption_propensity", [])
        income_currency = await _status.get("income_currency", [])
        depression = await _status.get("depression", [])
        locus_control = await _status.get("locus_control", [])
        working_hours = await _status.get("working_hours", [])
        employees = await _status.get("employees", [])
        citizens = await _status.get("citizens", [])
        demand = await _status.get("demand", 0)
        sales = await _status.get("sales", 0)
        await self.environment.economy_client.add_orgs(
            {
                "id": _id,
                "type": _type,
                "nominal_gdp": nominal_gdp,
                "real_gdp": real_gdp,
                "unemployment": unemployment,
                "wages": wages,
                "prices": prices,
                "inventory": inventory,
                "price": price,
                "currency": currency,
                "interest_rate": interest_rate,
                "bracket_cutoffs": bracket_cutoffs,
                "bracket_rates": bracket_rates,
                "consumption_currency": consumption_currency,
                "consumption_propensity": consumption_propensity,
                "income_currency": income_currency,
                "depression": depression,
                "locus_control": locus_control,
                "working_hours": working_hours,
                "employees": employees,
                "citizens": citizens,
                "demand": demand,
                "sales": sales,
            }
        )

    async def react_to_intervention(self, intervention_message: str):
        """
        React to an intervention.

        - **Args**:
            - `intervention_message` (`str`): The message of the intervention.

        - **Description**:
            - React to an intervention.
        """
        ...


class FirmAgentBase(InstitutionAgentBase):
    """
    Represents a firm agent within the simulation environment.
    """


class BankAgentBase(InstitutionAgentBase):
    """
    Represents a bank agent within the simulation environment.
    """

    ...


class NBSAgentBase(InstitutionAgentBase):
    """
    Represents a National Bureau of Statistics agent within the simulation environment.
    """

    ...


class GovernmentAgentBase(InstitutionAgentBase):
    """
    Represents a government agent within the simulation environment.
    """

    ...


class SupervisorBase(Agent):
    def __init__(
        self,
        id: int,
        name: str,
        toolbox: AgentToolbox,
        memory: Memory,
        agent_params: Optional[Any] = None,
        blocks: Optional[list[Block]] = None,
    ) -> None:
        """
        Initialize a new instance of the SupervisorAgent.

        - **Args**:
            - `id` (`int`): The ID of the agent.
            - `name` (`str`): The name or identifier of the agent.
            - `toolbox` (`AgentToolbox`): The toolbox of the agent.
            - `memory` (`Memory`): The memory of the agent.
            - `agent_params` (`Optional[Any]`): Additional parameters for the agent. Defaults to None.
            - `blocks` (`Optional[list[Block]]`): List of blocks for the agent. Defaults to None.

        - **Description**:
            - Initializes the SupervisorAgent with the provided parameters and sets up necessary internal states.
        """
        super().__init__(
            id=id,
            name=name,
            type=AgentType.Supervisor,
            toolbox=toolbox,
            memory=memory,
            agent_params=agent_params,
            blocks=blocks,
        )

    async def forward(
        self,
        current_round_messages: list[Message],
    ) -> tuple[
        dict[Message, bool],
        list[Message],
    ]:
        """
        Process and validate messages from the current round, performing validation and intervention

        - **Args**:
            - `current_round_messages` (`list[Message]`): List of messages for the current round, each element is a tuple of (sender_id, receiver_id, content).

        - **Returns**:
            - `tuple[dict[Message, bool], list[Message]]`: A tuple containing:
                - `validation_dict`: Dictionary of message validation results, key is message tuple, value is whether validation passed.
                - `persuasion_messages`: List of persuasion messages.
        """
        raise NotImplementedError(
            "This method `forward` should be implemented by the subclass"
        )
    

class IndividualAgentBase(Agent):
    def __init__(
        self,
        id: int,
        name: str,
        toolbox: AgentToolbox,
        memory: Memory,
        agent_params: Optional[Any] = None,
        blocks: Optional[list[Block]] = None,
    ) -> None:
        """
        Initialize a new instance of the IndividualAgent.

        - **Args**:
            - `id` (`int`): The ID of the agent.
            - `name` (`str`): The name or identifier of the agent.
            - `toolbox` (`AgentToolbox`): The toolbox of the agent.
            - `memory` (`Memory`): The memory of the agent.
            - `agent_params` (`Optional[Any]`): Additional parameters for the agent. Defaults to None.
            - `blocks` (`Optional[list[Block]]`): List of blocks for the agent. Defaults to None.

        - **Description**:
            - Initializes the IndividualAgent with the provided parameters and sets up necessary internal states.
        """
        super().__init__(
            id=id,
            name=name,
            type=AgentType.Individual,
            toolbox=toolbox,
            memory=memory,
            agent_params=agent_params,
            blocks=blocks,
        )

    async def run(self, task: Task) -> Any:
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
        result = await self.forward(task.get_task_context())
        task.set_result(result)
        # run required methods after agent forward
        await self.after_blocks()
        await self.after_forward()
        end_time = time.time()
        return end_time - start_time

    async def forward(
        self,
        task_context: dict[str, Any],
    ) -> Any:
        """
        Process and validate messages from the current round, performing validation and intervention. 
        The task context is a dictionary of the context of the task.

        - **Args**:
            - `task_context` (`dict[str, Any]`): The context of the task.

        - **Returns**:
            - `Any`: The result of the task.
        """
        raise NotImplementedError(
            "This method `forward` should be implemented by the subclass"
        )
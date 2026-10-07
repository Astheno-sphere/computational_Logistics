
from datetime import datetime
import json
import demjson3
import os
import random
import re
import traceback
from typing import Optional

from typing import Tuple
from loguru import logger
import numpy as np
from openai import BaseModel
from vllm import LLM
from helper import categorize_date_time_short, get_weekday_category, humanize_date, humanize_date_short, humanize_time, time_to_bucket_text
from llm.llm_model import ModelConfig
from llm.longterm import MultiUserLongTermMemory
from llm.memory import MemoryEntry, MemoryType
from llm.shortterm import UserShortTermMemory
from models import Person, TravelPlan
from scenarios.history import HistoryStreamLog
from text_helper import env_ob_to_text
from settings import settings

from llama_index.core.llms import ChatMessage, ChatResponse
import time

from world.population import PersonScheduler


history_log = HistoryStreamLog.get_instance()


class Context(BaseModel):
    person: Person
    timestamp: int
    activity_id: Optional[str] = None
    data: Optional[dict] = None


def log_chat(prompt: str, response: str, context: Context) -> str:
    log_dir = settings.agent.chat_log_dir
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    type_suffix = f"-{context.data['type']}" if context.data and context.data.get('type') else ""
    sim_time = datetime.strftime(datetime.fromtimestamp(context.timestamp), "%d_%H%M")
    file_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{sim_time}-{context.person.person_id}-{context.activity_id}{type_suffix}.txt"

    with open(os.path.join(log_dir, file_name), "a") as f:
        f.write("--------------------\n")
        f.write(f"Prompt: \n{prompt}\n")
        f.write("--------------------\n")
        f.write(f"Response: \n{response}\n\n")
        f.write("--------------------\n")
        f.write(f"Data: \n{context.model_dump_json()}\n")

    return file_name

class LLMAgent:
    DEFAULT_IDENTITY = ""

    def __init__(self, llm: LLM):
        # self.model_config = model_config
        # self.llm = model_config.create_llm()
        # self.embedding = model_config.create_embedding()
        self.llm = llm
        
        self.short_term_memory: dict[str, UserShortTermMemory] = {}
        self.long_term_memory = MultiUserLongTermMemory(
            storage_dir=settings.agent.long_term_memory_storage_dir,
            long_term_memory_filter_by_datetime=settings.agent.long_term_memory_filter_by_datetime,
        )

    def get_short_term_memory(self, user_id: str) -> UserShortTermMemory:
        if user_id not in self.short_term_memory:
            self.short_term_memory[user_id] = UserShortTermMemory(user_id)
        return self.short_term_memory[user_id]
    
    def add_short_term_memory(self, context: Context, msg: str, timestamp: Optional[int] = None):
        memory = self.get_short_term_memory(context.person.person_id)
        memory.add_message(
            msg, 
            datetime.fromtimestamp(timestamp or context.timestamp), 
            activity_id=context.activity_id
        )
        history_log.log_shortterm_memory(
            timestamp=context.timestamp,
            person_id=context.person.person_id,
            activity_id=context.activity_id,
            message=msg,
            data=context.data,
        )

    async def aadd_long_term_memory(self, context: Context, msg: MemoryEntry):
        await self.long_term_memory.aadd_memory(msg)
        history_log.log_longterm_memory(
            timestamp=context.timestamp,
            person_id=context.person.person_id,
            message=msg.content,
            data=context.data,
        )

    async def achat(self, context: Context, prompt: str, system_prompt: Optional[str] = None, params: Optional[dict] = None, type: Optional[str] = None) -> str:
        start_time = time.time()
        for _ in range(settings.agent.llm_retry_count):
            try:
                # Use the LLM's chat method to get a response
                messages = [] if not system_prompt else [ChatMessage(role="system", content=system_prompt)]
                messages.append(ChatMessage(role="user", content=prompt))
                response: ChatResponse = await self.llm.achat(messages, **(params or {}))
                break  # Exit loop if successful
            except Exception as e:
                logger.error(f"LLM chat failed: {e}")
                time.sleep(settings.agent.llm_retry_delay)

        assert response is not None, "LLM chat response is None after retries."

        duration = time.time() - start_time

        # Try to get token usage stats if available
        total_tokens = getattr(response, "usage", {}).get("total_tokens", None)

        stats = {
            "duration": duration,
            "total_tokens": total_tokens,
        }
        context.data = context.data or {}
        context.data["llm_stats"] = stats

        combine_prompt = f"***** ------------------ System Prompt ------------------ :\n{system_prompt}\n***** ------------------ User Prompt ------------------ :\n{prompt}"
        log_chat(combine_prompt, response, context)
        return response.message.content.strip()

    def parse_response_json(self, response: str) -> Tuple[Optional[dict], str]:
        try:
            match = re.search(r'\{.*\}', response, re.DOTALL)
            assert match is not None, "No JSON found in response"

            json_str = match.group(0)
        except Exception as e:
            traceback.print_exc()
            print(f"Error parsing response: {e}, response raw: {response}")
            json_str = response.strip()

        try:
            parsed = json.loads(json_str)
            return parsed, ""
        except Exception as e:
            traceback.print_exc()
            print(f"Error parsing response: {e}, response raw: {response}")
            
        try:
            parsed = demjson3.decode(json_str)
            return parsed, ""
        except demjson3.JSONDecodeError as e:
            traceback.print_exc()
            print(f"Error parsing response: {e}, response raw: {response}")
        
        return None, response.strip()

    def get_person_identity_description(self, person: Person) -> str:
        i = person.identity
        # text = f"You are an {'employed' if i.employed else 'unemployed'} person, aged {i.age}. You have a {'driving license' if i.has_driving_license else 'no driving license'}, and {'a car' if i.car_availability else 'no car'} available. Your monthly income is €{i.income}."
        # text = f"You are an {'employed' if i.employed else 'unemployed'} person, aged {i.age}. Your monthly income is €{i.income}."
        # if self.DEFAULT_IDENTITY:
        #     text += f" In addition, {self.DEFAULT_IDENTITY}"
        # return text
        text = json.dumps(i.traits_json, ensure_ascii=False, indent=2)
        return text

    async def aquery_experiences_with_travel_plans(self, context: Context, options: list[TravelPlan]) -> list[str]:
        def get_plan_text(plan: TravelPlan) -> str:
            return env_ob_to_text("travel_plan_query", plan.model_dump())

        index = 1
        travel_options = ""
        for option in options:
            travel_options += f"{index}. \n{get_plan_text(option)}\n"
            index += 1

        # TODO: add time manner, like "Monday morning"
        text = f"""The travel plan for:
- **CURRENT TIME**: {humanize_date_short(context.timestamp)}, **TEMPORAL KEYWORD**: {categorize_date_time_short(context.timestamp)}, on {get_weekday_category(context.timestamp).upper()}.
- **TRAVEL TO**: {options[0].purpose}.
---------
**TRAVEL OPTIONS**:
{travel_options}

Find the travel histories that in the same **CURRENT TIME**, **TEMPORAL KEYWORD** and **TRAVEL TO** location, and related to the **TRAVEL OPTIONS**.
        """

        logger.debug(f"Querying experiences with travel plans for user {context.person.person_id}, activity {context.activity_id}, query text: {text}")

        hist = await self.long_term_memory.aquery_user_memories(
            person_id=context.person.person_id,
            query=text,
            top_k=settings.agent.long_term_max_entries_query,
            max_past_days=settings.agent.long_term_max_days_query,
            query_at=context.timestamp,
        )

        # deduplicate entries based on content
        unique_hist = {}
        for entry in hist:
            if entry.content not in unique_hist:
                unique_hist[entry.content] = entry
        hist = sorted(list(unique_hist.values()), key=lambda x: x.metadata['timestamp'], reverse=True)

        logger.debug(f"Found {len(hist)} relevant experiences for travel plans for user {context.person.person_id}, activity {context.activity_id}")

        # resp = [
        #     # f"[{datetime.strftime(datetime.fromisoformat(entry.metadata['timestamp']), '%A, %H:%M:%S')}] {entry.content}"
        #     # TODO: we asked the LLM to return the time within the day, so only need to append the day of week here
        #     f"[{datetime.strftime(datetime.fromisoformat(entry.metadata['timestamp']), '%A')} at {time_to_bucket_text(datetime.fromisoformat(entry.metadata['timestamp']).timestamp())}] {entry.content}" if entry.content else ""
        #     for entry in hist
        # ]

        resp = []
        ts = []
        for entry in hist:
            if str(entry.metadata["memory_type"]) == str(MemoryType.REFLECTION.value):
                resp.append([entry.content, datetime.strftime(datetime.fromisoformat(entry.metadata['timestamp']), '%A, %B %d')])
                ts.append(datetime.fromisoformat(entry.metadata['timestamp']).timestamp())
            elif str(entry.metadata["memory_type"]) == str(MemoryType.CONCEPT.value):
                resp.append(json.loads(entry.content))
                ts.append(datetime.fromisoformat(entry.metadata['timestamp']).timestamp())
            else:
                logger.debug(f"Unknown memory type for entry: {entry.metadata['memory_type']}")

        # sort the entries by timestamp asc
        ts = np.array(ts)
        sorted_indices = np.argsort(ts)
        resp = [resp[i] for i in sorted_indices]
        return resp

    def get_personal_system_prompt(self, person: Person) -> str:
        identity_description = self.get_person_identity_description(person)

        system_prompt = f"""# Agent specification

You are a simulation of a person such that:
  - You don't know you are a simulation, you think you are an actual person.
  - You follow the directives given below.
  - You interpret the persona described below (Section "Persona"). You indeed think you ARE that person.
  - Your knowledge is limited to what can be reasonably expected from the specified persona and the current cognitive state. 
    If the persona is not likely to know something, you must pretend you don't know it either.
  - You behave as realistically as possible, in accordance with the specified persona, including making mistakes, forgetting things,
    being nasty, and being influenced by your emotions. Remember, you are meant to be a simulation of a real person, not a perfect machine.
    You do not need to please anyone, but you must be coherent with the persona and the context.

## Persona 

As a person, you have the characteristics specified in the JSON below. These include, among other things, your personal information, routine, job description, personality, interests. You **MUST** act in accordance with these characteristics.

```json
{identity_description}
```

### Rules for interpreting your persona

To interpret your persona, you **must** follow these rules:
  - You act in accordance with the persona characteristics, as if you were the person described in the persona.
  - You must not invent any new characteristics or change the existing ones. Everything you say or do must be consistent with the persona.
"""
        
        return system_prompt

    async def aget_plan_trip_prompt(self, context: Context, options: list[TravelPlan], destination: str) -> str:
        if settings.agent.long_term_memory_enabled:
            experience_entries = await self.aquery_experiences_with_travel_plans(context, options)
        else:
            experience_entries = []

        experiences_text = json.dumps(experience_entries, indent=2, ensure_ascii=False)

        def get_plan_text(plan: TravelPlan) -> str:
            return env_ob_to_text("travel_plan", plan.model_dump())

        index = 1
        travel_options = ""
        for option in options:
            travel_options += f"\n-----\n*Option {index}*: \n{get_plan_text(option)}\n"
            index += 1

        system_prompt = self.get_personal_system_prompt(context.person)

        custom_guidelines = settings.agent.travel_plan_custom_guidelines or None
        
        travel_plan_prompt = f"""You are a person who has to commute every day for your daily activities or for leisure. Based on your persona and past experiences, you typically choose a set of transport modes and travel plans to get to your destination. Below, you will be given the Travel Purpose, the Travel Options requested from Google Maps, and your experiences and opinions about traveling in the past. Your job is to choose the travel plan you will follow.

# Travel Requirements
Trip Purpose: {destination}.
Departure Time: {humanize_time(context.timestamp)} - {time_to_bucket_text(context.timestamp)}.

# Travel Options from routing assistant
CURRENT TIME: {humanize_time(context.timestamp)}. **TEMPORAL KEYWORD**: {categorize_date_time_short(context.timestamp)}, on {get_weekday_category(context.timestamp).upper()}.

{travel_options}

### Important Notes:
- The travel options only provide the estimated times for travel between stops, not the total trip time; the total trip time includes waiting times, walking times, and transfers that should be extracted from past experiences if available.
- Transit format: Transport Mode (line: X) from Stop A to Stop B

# Past Travel Experiences and Opinions
### Travel experiences guidelines
The experiences is in JSON format, including the list of past travel experiences and their metadata as following:
```json
[
    ["CONTENT", "KEYWORD", "TIME"]
]
```

**IMPORTANT **: The **experiences** provided below are ordered from old to new. If you have multiple experiences that conflict, prioritize the most recent one (that last one).

The INPUT for **experiences** as followings:
```json
{experiences_text if experiences_text else "[]"}
```

# Analysis Framework
Here is the Analysis Framework to help you choose the best travel plan for you:
## Decision Criteria Factors
Focus on the following factors when selecting the best travel plan:
- Reliability & Timing: For work/education trips, prioritize punctuality and predictable travel times. Also consider the number of transfers and connection complexity, walking distances, and waiting times.
- Past Experience Patterns: Leverage positive experiences, avoid repeating negative ones.
- Personal Preferences: Align with preferred transport modes and comfort levels


## Think step by step
Think carefully step by step, first evaluating each option based on past experiences and suitability for the trip purpose, rate them with a score from 1 to 5, then select the best plan from the options provided.

Step 1: Evaluate Each Option
Analyze each option following these criteria, each in under 100 words.
1. Analyze: You have to balance the following criteria factors carefully:
    - Reliability & Timing: this may or may not be very important and varies depending on the trip purpose and persona. For example, leisure travel might allow for more flexibility, especially if you are not a highly conscientious person.
    - Past Experience Patterns: trust your experience and opinion over suggestions from external sources like Google Maps. Naturally, you may have a better understanding of the local transit system and potential delays; avoid repeating negative experiences.
    - Personal Preferences (Persona): Consider your own preferences for transport modes, comfort levels, and any specific needs you may have.
2. Score: Score each option based on the analysis above, from 1 to 5.

Step 2: Final Decision
Choose the option based on the previous evaluations (Step 1). If multiple options are equally good, consider your habits and preferences.

# OUTPUT format:
*******
Step 1: Brief Analysis of each option
- Option 1: CONTENT
- Option 2: CONTENT
*******
Step 2: Final Decision, this is in JSON format
```json
    {{
        "chosen_plan": INDEX start from 1,
        "reason": "REASON"
    }}
```

{f'**IMPORTANT CUSTOM GUIDELINES**' if custom_guidelines else ''}
{f'{custom_guidelines}' if custom_guidelines else ''}
"""
        
        return system_prompt, travel_plan_prompt

    async def aplan_trip(self, context: Context, options: list[TravelPlan], destination: str) -> tuple[int, str]:
        assert options, "No travel options provided for planning trip."
        if len(options) == 1:
            # If only one option, return it directly
            return 0, "Only one travel option available, no need to choose."
        
        # shuffle options to avoid bias
        random.shuffle(options)
        system_prompt, prompt = await self.aget_plan_trip_prompt(context, options, destination)
        response = await self.achat(context, prompt, system_prompt=system_prompt)
        resp, fallback = self.parse_response_json(response)
        if resp:
            index = resp.get("chosen_plan", -1)
            # convert to 0-based index
            if isinstance(index, int) and 1 <= index <= len(options):
                reason = resp.get("reason", "")
                if "is chosen because it" in reason:
                    reason = f"This plan {reason.split('is chosen because it', 1)[1].strip()}"
                return index - 1, reason
        return -1, fallback.strip() or "No valid response received."

    def get_reflection_prompt(self, context: Context) -> tuple[str, list[MemoryEntry]]:
        mem = self.get_short_term_memory(context.person.person_id)
        group_messages, all_messages = mem.get_all_message_and_group()

        if not all_messages:
            return "", []

        exp = []
        for group in group_messages:
            if group:
                activity = PersonScheduler(context.person).get_activity(group[0].activity_id) if group[0].activity_id else None
                exp.append({
                    "purpose": activity.purpose if activity else None,
                    "observations": [msg.content for msg in group],
                })
        experiences_text = json.dumps(exp, indent=2, ensure_ascii=False)

        custom_guidelines = settings.agent.reflection_custom_guidelines or None

        text = f"""# TASK INSTRUCTION
Reflect on past experiences to identify patterns, lessons, and insights that will improve future travel planning.
You can also generate concepts about important things or ideas to be remembered in the long term memory (optional but recommended).

# OUTPUT FORMAT
Must be in the json format
```json
{{
    "reflection": "string - narrative reflection on the day",
    "concepts": [[<content>, <keywords>, <spatial_scope>, <time_scope>], ...]
}}
```

# REFLECTION GUIDELINES
"reflection" is a string that summaries what's happened today. Be specific when mention a trip, that includes this tag in the context [**CURRENT TIME**: <current_time>, **TRAVEL TO**: <travel_to>]:
- **CURRENT TIME**: The current time of the travel.
- **TRAVEL TO**: The destination of the travel.
Keep it under 200 words.

### Structure your reflection around:
1. **Plan Adherence**
- Which activities went as planned?
- What required adjustment and why?
- Were time estimates accurate?
- Were the arrival times as expected?

2. **Traffic & Transportation**
- Route performance vs. expectations
- Travel mode effectiveness

3. **Key Learnings**
- What would you do differently?
- Patterns worth remembering
- Planning improvements for tomorrow
- Planning worth keeping in future

### CONCEPTS GUIDELINES
"concepts" a list of concepts to be remembered (optional but recommended). These memories will help you to make better future decisions.

Generate 0-5 concepts for long-term memory. Focus on:
- Recurring patterns (not one-time events); especially traffic related patterns
- Actionable insights for future planning
- Specific locations and time windows


**Content Types:**
- Traffic patterns: "Bus 69 travel time is reliable"
- Activity timing: "Wait long time for Bus 20"
DO NOT fabricate concepts; base patterns on your actual experiences.

**Required Format for each concept:**
[<content>, <keywords>, <spatial_scope>, <time_scope>, <purpose>]


**Field Definitions:**
<content>: a string; content of the concept;
<keywords>: a string composed of keywords separated by comma, like "Bus 69, lated, 6PM";
<spatial_scope>: a string that describe the spatial scope related to the concept. It must be a list of entities separated by comma; an entity can be a bus route, road name, or stop name.
<purpose>: a string that describes the purpose of the activity; if it isn't related to a specific travel, let it be empty string "", do not output the null.
<time_scope>: time scope of the concept; must be in the string format "<day_of_week> <start_time>, <day_of_week>", where <start_time> in ["morning", "afternoon", "evening", "night"] for example "Monday morning"; and <day_of_week> is either "Weekend" or "Weekday". If the concept is not related to a specific time scope, let it be empty string "", do not output the null.


**Spatial Scope Options:**
- Specific Transport Mode and Route: e.g. "Bus 69"
- Facility: e.g. "Stop (Jean Jaures)"

# INPUT GUIDELINES
Now you will be provided with a list of past experiences and observations. Use these to generate your reflection and concepts following the above guidelines.

### Input format
The input is in json format
```json
[
    {{"purpose": "PURPOSE", "observations": [ "OBSERVATION_1", "OBSERVATION_2"]}},
]
```

PURPOSE is the purpose of the travel that occurred during the observations, such as "school", "work", "leisure", etc.
OBSERVATION is a description of what was experienced or observed during the travel for the purpose. The observations are tagged with predefined labels as following:
- [ TRAVEL_PLAN ]: The plan for the travel for this purpose, including the intended route and mode of transport, and the reason why it was chosen.
- [ WALKING ]: The action of walking to a destination.
- [ TRANSIT ]: The action of using public transportation.
- [ WAITING ]: The action of waiting at a location.
- [ ARRIVAL ]: End of the journey, reporting arrival time and delay.

Now is the past experiences input, after that give the reflection.

# INPUT
```json
{experiences_text if experiences_text else "[]"}
```

{{f'**IMPORTANT CUSTOM GUIDELINES** {custom_guidelines}' if custom_guidelines else ''}}
"""
        return text, all_messages

    def get_longterm_memory_reflection_prompt(self, context: Context, from_date: datetime):
        all_entries = self.long_term_memory.get_last_user_memories(
            person_id=context.person.person_id,
            from_date=from_date,
        )
        if not all_entries:
            return None, []

        entries_text = "\n".join(f"- Time {humanize_date(entry.timestamp.timestamp())}: {entry.content}" for entry in all_entries)

        prompt = f"""# TASK INSTRUCTION
Reflect on past experiences to identify patterns, lessons, and insights that will improve future travel planning.

# Past experiences
{entries_text}

# OUTPUT FORMAT
Must be in the json format.
```json
{{
    "reflection": "string - narrative reflection on the previous days",
}}
```

# REFLECTION GUIDELINES
"reflection" is a string that:
- Summaries what's happened previous days and the insights should be learned from. Be specific when mention a trip, that includes this tag in the context [**CURRENT TIME**: <current_time>, **TRAVEL TO**: <travel_to>]:
    - **CURRENT TIME**: The day time of the travel you want to mention to, for example: Monday morning.
    - **TRAVEL TO**: The destination of the travel.
- Identify trip patterns. A trip is defined by: purpose (TRAVEL TO), spatial scope, and time scope (CURRENT TIME).
    - Detect repeated trips across days. If a trip gives good results consistently, or improves compared to earlier days, mark it as a potential habit/routine.
    - For each purpose, compare past travel options and decide: Which option is the best so far?
    - The experiences list are ordered by timestamp: if experiences conflict, give priority to the most recent.
- Output in a single paragraph, under 200 words.
    - List habits/routines found.
    - Best travel option for each purpose.
        """
        return prompt, all_entries
    
    async def areflect_all(self, timestamp: int, people: list[Person]):
        """
        Reflect on all short-term memories of all people at the given timestamp.
        This is used to process all short-term memories at once, e.g. at the end of the day.
        """
        if settings.agent.long_term_memory_enabled is False:
            logger.info("Long-term memory is disabled, skipping reflection.")
            return
        
        for person in people:
            context = Context(
                person=person,
                timestamp=timestamp,
                data={"type": "reflection"}
            )
            await self.areflect_memory(context)

    async def aself_reflect_all(self, timestamp: int, from_date: datetime, people: list[Person]):
        if settings.agent.long_term_memory_enabled is False or settings.agent.long_term_self_reflect_enabled is False:
            logger.info("Long-term memory is disabled or Self reflection is disable, skipping self reflection.")
            return

        for person in people:
            context = Context(
                person=person,
                timestamp=timestamp,
                data={"type": "self_reflection"}
            )
            await self.areflect_longterm_memory(context, from_date)

    async def areflect_longterm_memory(self, context: Context, from_date: datetime):
        if settings.agent.long_term_memory_enabled is False:
            logger.info("Long-term memory is disabled, skipping reflection.")
            return
        
        prompt, all_entries = self.get_longterm_memory_reflection_prompt(context, from_date)
        if not all_entries:
            logger.info(f"No long-term memory available for reflection for {context.person.person_id}")
            return
        system_prompt = self.get_personal_system_prompt(context.person)
        response_text = await self.achat(context, prompt, system_prompt=system_prompt)
        resp, fallback = self.parse_response_json(response_text)
        try:
            reflection = resp["reflection"]
            entry = MemoryEntry(
                person_id=context.person.person_id,
                content=reflection,
                timestamp=datetime.fromtimestamp(context.timestamp),
                memory_type=MemoryType.REFLECTION,
            )
            await self.aadd_long_term_memory(context, entry)
        except Exception as e:
            logger.error(f"Failed to parse reflection response for person {context.person.person_id}, err: {e}")
            return

    async def areflect_memory(self, context: Context):
        prompt, all_messages = self.get_reflection_prompt(context)
        if not all_messages:
            logger.info("No short-term memory available for reflection.")
            return
        
        system_prompt = self.get_personal_system_prompt(context.person)
        response_text = await self.achat(context, prompt, system_prompt=system_prompt)
        #TODO: hotfix - avoid null in the list
        response_text = response_text.replace("\nnull", "").replace("null\n", "").replace("\nnull\n", "")
        resp, fallback = self.parse_response_json(response_text)

        # remove all messages from short-term memory
        self.get_short_term_memory(context.person.person_id).remove_batch(all_messages)
        # TODO: Add to long-term memory
        start_timestamp = all_messages[0].timestamp

        def _try_parse_entry_time(entry: str) -> Optional[datetime]:
            # Parse "At [HH:MM], heading to [purpose], [synthesized observation]." format
            match = re.search(r'At (\d{1,2}:\d{2})', entry.strip())
            if match:
                time_str = match.group(1)
                # Convert to timestamp
                try:
                    hour, minute = map(int, time_str.split(':'))
                    entry_time = start_timestamp.replace(hour=hour, minute=minute)
                    return entry_time
                except Exception as e:
                    logger.error(f"Failed to parse time from entry: {entry}")
            return None
        
        # raise Exception("Reflection response parsing not implemented yet.")

        # add new memory to long-term memory
        entries = []
        try:
            reflection = resp.get("reflection", "").strip() if resp else ""
            concepts = resp.get("concepts", [])

            entries.append(MemoryEntry(
                person_id=context.person.person_id,
                content=reflection,
                timestamp=start_timestamp,
                memory_type=MemoryType.REFLECTION,
            ))

            for concept in concepts:
                entries.append(MemoryEntry(
                    person_id=context.person.person_id,
                    content=json.dumps(concept, ensure_ascii=False),
                    timestamp=start_timestamp,
                    memory_type=MemoryType.CONCEPT,
                    tags=",".join(concept[1:] if isinstance(concept, list) and len(concept) > 1 else [])
                ))
        except Exception as e:
            traceback.print_exc()
            logger.error(f"Failed to parse reflection response: {e}")

        for entry in entries:
            await self.aadd_long_term_memory(context, entry)

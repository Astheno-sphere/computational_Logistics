import asyncio
import json
from typing import Optional, Tuple
import datetime

from loguru import logger
from gama_models import WorldSyncIdlePeople
from helper import humanize_duration, humanize_time, to_timestamp_based_on_day, humanize_date
from models import BBox, Location, Person, PersonMove, TravelPlan
from scenarios.base import Action, BaseScenario, Observation
from scenarios.history import HistoryStreamLog
from scenarios.scenario_v1.agent import Context, LLMAgent
from text_helper import env_ob_to_text, parse_ob
from trip_helper.base import TripHelper
from utils import random_uuid
from world.population import WorldPopulation
from world.world_data import WorldModel
from settings import settings

history_logger = HistoryStreamLog.get_instance()

class ScenarioV1(BaseScenario):
    MAX_ADJUST_START_TIME = 15*60  # 15 minutes

    def __init__(self,
                 world_model: "WorldModel",
                 trip_helper: "TripHelper" = None,
                 agent: Optional["LLMAgent"] = None):
        self.MAX_ADJUST_START_TIME = settings.agent.max_reschedule_amount or self.MAX_ADJUST_START_TIME
        self._messages = []
        self.model = world_model
        self.trip_helper = trip_helper
        self.agent = agent
        # schedule next reflection
        self.reflect_period = settings.agent.long_term_reflect_interval
        self.next_reflection_at = None
        self.next_self_reflection_at = None
        # Control the agent's concurrency
        self._concurrent_semaphore = asyncio.Semaphore(settings.agent.remote_llm_max_concurrent_requests)

        if settings.agent.reschedule_activity__version == 2:
            self.reschedule_amount_function = self.reschedule_amount_v2
            logger.info("Using reschedule activity function version v2")
        else:
            self.reschedule_amount_function = self.reschedule_amount
            logger.info("Using reschedule activity function version v1")

    @property
    def population(self) -> "WorldPopulation":
        """Get the current population of the scenario"""
        return self.model.population

    @property
    def world_bbox(self) -> BBox:
        return self.model.bbox
    
    async def sync(self, timestamp: int, idle_people: list[WorldSyncIdlePeople] = None):
        # Sync idle people if provided
        if idle_people:
            logger.info(f"[timestamp: {humanize_date(timestamp)}] Syncing {len(idle_people)} idle people at timestamp {timestamp}")
            for person_data in idle_people:
                person = self.population.get_person(person_data.person_id)
                if person:
                    person.state.last_location = person_data.location
                    self.population.get_person_default_scheduler(person).finish_activity()
                    logger.debug(f"[timestamp: {humanize_date(timestamp)}] Person {person.person_id} last location updated to {person_data.location}")
                else:
                    logger.warning(f"[timestamp: {humanize_date(timestamp)}] Person {person_data.person_id} not found in population")

        # Schedule next person move
        await self.schedule_person_move(timestamp=timestamp)

        # Check reflection period
        if not self.next_reflection_at:
            self.next_reflection_at = timestamp + self.reflect_period
        elif timestamp >= self.next_reflection_at:
            # Reflect the state of the world
            logger.info(f"[timestamp: {humanize_date(timestamp)}] Reflecting the state of the world")
            await self.areflect_all(timestamp=timestamp)
            self.next_reflection_at = timestamp + self.reflect_period

        # Check self reflection period
        if settings.agent.long_term_self_reflect_enabled:
            if not self.next_self_reflection_at:
                self.next_self_reflection_at = timestamp + settings.agent.long_term_self_reflect_interval_days*24*3600
            elif timestamp >= self.next_self_reflection_at:
                # Self reflect the state of the world
                logger.info(f"[timestamp: {humanize_date(timestamp)}] Self reflecting the state of the world")
                _duration_days = settings.agent.long_term_self_reflect_window_days
                from_date = datetime.datetime.fromtimestamp(timestamp) - datetime.timedelta(days=_duration_days)
                # set to the start of the day
                from_date = from_date.replace(hour=0, minute=0, second=0, microsecond=0)
                await self.agent.aself_reflect_all(timestamp=timestamp, from_date=from_date, people=self.population.get_people_list())
                self.next_self_reflection_at = timestamp + settings.agent.long_term_self_reflect_interval_days*24*3600

    async def areflect_all(self, timestamp: int):
        idle_people = [
            p for p in self.population.get_people_list() 
            if p.is_llm_based and p.state.heading_to is None
        ]

        async def reflect_person(person):
            async with self._concurrent_semaphore:
                await self.agent.areflect_all(timestamp=timestamp, people=[person])

        tasks = [reflect_person(person) for person in idle_people]
        await asyncio.gather(*tasks)

    async def aself_reflect_all(self, timestamp: int):
        people = self.population.get_people_list()

        async def self_reflect_person(person):
            async with self._concurrent_semaphore:
                await self.agent.areflect_longterm_memory(timestamp=timestamp, people=[person])

        tasks = [self_reflect_person(person) for person in people]
        await asyncio.gather(*tasks)

    async def handle_observation(self, observation: Observation):
        """Handle observation data"""
        # logger.debug(f"[timestamp: {humanize_date(observation.timestamp)}] Handling observation for person {observation.person_id} at location {observation.location}")
        person = self.population.get_person(observation.person_id)
        if not person:
            logger.warning(f"[timestamp: {humanize_date(observation.timestamp)}] Person {observation.person_id} not found in population")
            return
        # Update person's state based on observation
        person.state.last_location = observation.location
        on_purpose = person.state.heading_to

        # Put the observation into the person's short-term memory
        ob_text = env_ob_to_text(
            code=observation.env_ob_code,
            ob=observation.data,
            purpose=on_purpose,
        )
        # history_logger.log_shortterm_memory(
        #     timestamp=observation.timestamp,
        #     person_id=person.person_id,
        #     message=ob_text,
        #     data={
        #         "location": observation.location.model_dump(exclude_none=True),
        #         "heading_to": person.state.heading_to,
        #         "data": observation.data,
        #     }
        # )
        if observation.env_ob_code == "arrival":
            # person.state.heading_to = None  # Clear the heading_to state if it's an arrival observation
            # Adjust the scheduled time for the next activity
            # TODO: finetune or remove this rule
            if person.state.cache_current_activity:
                activity = person.state.cache_current_activity
                ob = parse_ob(code=observation.env_ob_code, ob=observation.data)
                if settings.agent.reschedule_activity_departure_time:
                    # Support adjust in both directions
                    duration = self.reschedule_amount_function(arrival_late_seconds=ob.late)
                    self.population.get_person_default_scheduler(person).reschedule_activity(activity, duration)
                    # add to the short term memory
                    _context = Context(
                        person=person,
                        activity_id=observation.activity_id,
                        timestamp=observation.timestamp,
                        data={
                            "location": observation.location.model_dump(exclude_none=True),
                            "heading_to": person.state.heading_to,
                            "data": observation.data,
                        }
                    )
                    self.agent.add_short_term_memory(
                        context=_context,
                        msg=f"According to the past late time, you rescheduled the {activity.purpose} activity. Now it will start at {humanize_time(activity.scheduled_start_time)}, mean {humanize_duration(activity.start_time - activity.scheduled_start_time)} before.",
                        timestamp=observation.timestamp
                    )
            self.population.get_person_default_scheduler(person).finish_activity()
            self.population.dump_population_state()

        _context = Context(
            person=person,
            activity_id=observation.activity_id,
            timestamp=observation.timestamp,
            data={
                "location": observation.location.model_dump(exclude_none=True),
                "heading_to": person.state.heading_to,
                "data": observation.data,
            }
        )
        self.agent.add_short_term_memory(
            context=_context,
            msg=ob_text,
            timestamp=observation.timestamp
        )
        
        logger.debug(f"[timestamp: {humanize_date(observation.timestamp)}] Person {observation.person_id} observed: {ob_text}")
    
    def reschedule_amount(self, arrival_late_seconds: int) -> int:
        """Calculate the reschedule amount based on arrival late seconds"""
        if arrival_late_seconds <= 0:
            return 0
        amount = min(int(abs(arrival_late_seconds) * settings.agent.reschedule_transition_ratio), self.MAX_ADJUST_START_TIME)
        amount = amount if arrival_late_seconds > 0 else -amount
        return amount
    
    def reschedule_amount_v2(self, arrival_late_seconds: int) -> int:
        """Calculate the reschedule amount based on arrival late seconds"""
        if arrival_late_seconds <= 0:
            return 0
        k = settings.agent.reschedule_activity_v2__k or 0.02
        arrival_late_minutes = arrival_late_seconds / 60.0
        amount = min(k * arrival_late_minutes * arrival_late_minutes * 60, self.MAX_ADJUST_START_TIME)
        amount = int(amount) if arrival_late_seconds > 0 else -int(amount)
        return amount
    
    async def has_messages(self) -> bool:
        """Check if there are messages to process"""
        return len(self._messages) > 0

    async def pop_all_messages(self) -> list[Action]:
        """Pop all messages from the queue"""
        messages = self._messages.copy()
        self._messages.clear()
        return messages
    
    async def schedule_person_move(self, timestamp: int):
        idle_people = [p for p in self.population.get_people_list() if p.state.heading_to is None]
        
        async def process_person(person):
            async with self._concurrent_semaphore:
                move, reasoning = await self.next_person_move(person, timestamp)
                if move:
                    logger.debug(f"[timestamp: {humanize_date(timestamp)}] Person {person.person_id} is moving to {move.target_location} for {move.purpose}")
                    self._messages.append(Action(
                        person_id=person.person_id,
                        action=move.model_dump(exclude_none=False)
                    ))

                    action_text = env_ob_to_text(
                        code="travel_plan",
                        ob=move.plan.model_dump(exclude_none=True)
                    )
                    action_text = f"[ TRAVEL_PLAN ] Start traveling following plan: \n{action_text}\n\nReasoning (consumption) for decision: {reasoning}"

                    # TODO: this is duplicated with `add_short_term_memeory`?
                    # history_logger.log_shortterm_memory(
                    #     timestamp=move.current_time,
                    #     person_id=person.person_id,
                    #     activity_id=move.for_activity.id,
                    #     message=action_text,
                    #     data={
                    #         "target_location": move.target_location.model_dump(exclude_none=True),
                    #         "purpose": move.purpose,
                    #         "plan": move.plan.model_dump(exclude_none=True),
                    #     }
                    # )

                    # Add short-term memory for the move
                    self.agent.add_short_term_memory(
                        context=Context(
                            person=person,
                            activity_id=move.for_activity.id,
                            timestamp=move.current_time,
                            data={
                                "target_location": move.target_location.model_dump(exclude_none=True),
                                "purpose": move.purpose,
                                "plan": move.plan.model_dump(exclude_none=True),
                            }
                        ),
                        msg=action_text,
                        timestamp=move.current_time
                    )

                    # Update person's state
                    self.population.get_person_default_scheduler(person).start_on_activity(
                        activity=move.for_activity,
                    )

        tasks = [process_person(person) for person in idle_people]
        await asyncio.gather(*tasks)

    # def log_travel_plan_to_shortterm(self, plan: TravelPlan, reasoning: str):
    #     """Log the travel plan to the person's short-term memory"""
    #     if not plan or not plan.id:
    #         return
    #     text = env_ob_to_text(
    #         code="travel_plan_query",
    #         ob=plan.model_dump(exclude_none=True)
    #     )
    #     if reasoning:
    #         text += f"\nReasoning: {reasoning}"
    #     history_logger.log_shortterm_memory(
    #         timestamp=plan.start_time,
    #         person_id=plan.id,
    #         message=text,
    #         data={
    #             "plan": plan.model_dump(exclude_none=True),
    #             "reasoning": reasoning,
    #         }
    #     )

    async def next_person_move(self, 
                person: Person, 
                timestamp: int = None,
                depth: int = 0
            ) -> Tuple[Optional[PersonMove], Optional[str]]:
        # Find the next move
        next_activity = self.population.get_person_default_scheduler(person).next_activity(
            timestamp,
            pre_schedule_duration=None,
        )
        if not next_activity:
            # logger.debug(f"[timestamp: {timestamp}] Person {person_id} has no next activity, waiting...")
            return None, None
        
        # Query a new trip plan
        from_location = person.state.last_location

        itineraries = await self.trip_helper.get_itineraries(
            origin=from_location,
            destination=next_activity.location,
            departure_time=timestamp,
        )
        # Populate purpose
        for itinerary in itineraries:
            itinerary.purpose = next_activity.purpose

        if not itineraries:
            logger.debug(f"[timestamp: {humanize_date(timestamp)}] Can't get to destination {next_activity.location} by public transport, move to the destination anyway")
            plan = TravelPlan(
                id=random_uuid(),
                start_location=from_location,
                end_location=next_activity.location,
                start_time=timestamp,
                end_time=timestamp + 30*60,  # Assume 30 minutes travel time
                purpose=next_activity.purpose,
                legs=[],
            )
            plan_index = 0
            reasoning = "Can't find a suitable public transport plan, walk to the destination anyway"
        else:
            plan_index = 0
            reasoning = "Hard to choice, just pick the first one"

            # Ask LLM agent to choose a best plan
            if person.is_llm_based and self.agent:
                # Use the agent to choose the best plan
                context = Context(
                    person=person,
                    timestamp=timestamp,
                    activity_id=next_activity.id,
                    data={"type": "travel_plan"},
                )
                plan_index, reasoning = await self.agent.aplan_trip(
                    context=context,
                    options=itineraries,
                    destination=next_activity.purpose,
                )
                if plan_index and isinstance(plan_index, int) and len(itineraries) > plan_index and plan_index >= 0:
                    pass
                else:
                    plan_index = 0
                    logger.debug(f"[timestamp: {humanize_date(timestamp)}] No suitable plan found for person {person.person_id} to {next_activity.location}")

            plan: TravelPlan = itineraries[plan_index]
            plan.purpose = next_activity.purpose

        # Define the person move based on the plan
        move = PersonMove(
            id=random_uuid(),
            person_id=person.person_id,
            current_time=timestamp,
            expected_arrive_at=to_timestamp_based_on_day(
                target_24h_timestamp=next_activity.start_time,
                based_on=timestamp,
            ),
            prepare_before_seconds=0,
            purpose=next_activity.purpose,
            target_location=next_activity.location,
            for_activity=next_activity,
            plan=plan,
        )

        history_logger.log_query_travel_plan(
            timestamp=timestamp,
            person_id=person.person_id,
            message=f"Querying travel plan for {next_activity.purpose}",
            data={
                "purpose": next_activity.purpose,
                "activity_id": next_activity.id,
                "itineraries": [plan.get_code() for plan in itineraries],
                "selected_plan_index": plan_index,
            }
        )

        history_logger.log_travel_plan(
            timestamp=timestamp,
            person_id=person.person_id,
            message=f"Planning trip for {next_activity.purpose}",
            data={
                "purpose": next_activity.purpose,
                "activity_id": next_activity.id,
                "plan_code": plan.get_code(),
            }
        )

        return move, reasoning

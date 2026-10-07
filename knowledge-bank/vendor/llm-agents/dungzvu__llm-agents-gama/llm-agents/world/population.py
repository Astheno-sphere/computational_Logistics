import json
import os
from typing import Dict, List, Optional
from models import Activity, BBox, Location, Person, PersonId
from settings import settings
from inputs.population import PopulationLoader
from errors import PersonNotFoundException
from helper import to_24h_timestamp_full
from loguru import logger
import random


class PersonScheduler:
    DEFAULT_PRE_SCHEDULE_DURATION = 0

    def __init__(self, person: Person):
        self.person = person

    def start_on_activity(self, activity: Activity):
        state = self.person.state
        state.heading_to = activity.purpose
        state.last_activity_index = self.person.identity.activities.index(activity)
        state.cache_current_activity = activity

    def get_activity(self, activity_id: str) -> Optional[Activity]:
        return next((activity for activity in self.person.identity.activities if activity.id == activity_id), None)

    def finish_activity(self):
        state = self.person.state
        state.cache_current_activity = None
        state.heading_to = None

    def reschedule_activity(self, activity: Activity, delta: int):
        logger.debug(f"Adjusting activity <{activity.purpose}> of person {self.person.person_id} scheduled start time based on arrival duration: {delta}")
        # _new_time = max(0, activity.scheduled_start_time - delta)
        # _new_time = min(_new_time, 24*3600)
        activities = self.person.identity.activities
        prev_idx = activities.index(activity) - 1
        next_idx = prev_idx + 2
        min_time = activities[prev_idx].scheduled_start_time + 1 if prev_idx > 0 else 4.5*3600 # public transport start from 4h30
        max_time = activities[next_idx].scheduled_start_time - 1 if next_idx < len(activities) else 24*3600 - 30*60
        _new_time = max(min_time, activity.scheduled_start_time - delta)
        _new_time = min(_new_time, max_time)
        activity.scheduled_start_time = _new_time

    def next_activity(self, 
                      timestamp: int, 
                      pre_schedule_duration: Optional[int] = None
            ) -> Optional[Activity]:
        if pre_schedule_duration is None:
            pre_schedule_duration = max(settings.agent.pre_schedule_duration, self.DEFAULT_PRE_SCHEDULE_DURATION)

        state = self.person.state
        day_of_week, time24h = to_24h_timestamp_full(timestamp)
        day24h_seconds = 24 * 60 * 60
        activities = self.person.identity.activities

        # Find the latest activity that starts before the current time
        selected_activity = None
        for i in range(len(activities)):
            activity = activities[i]
            next_activity = None if i + 1 >= len(activities) else activities[i + 1]

            # TODO: possible bug: if activity.start_time - pre_schedule_duration < 0?
            # Filter data: activity.start_time > 2h and < 24h
            # All activity.start_time in ascending order
            # filter out the home activity
            if activity.start_time < 0:
                continue
            if activity.scheduled_start_time is None or activity.scheduled_start_time == -1:
                activity.scheduled_start_time = activity.start_time - pre_schedule_duration
            start_journey_time = activity.scheduled_start_time
            next_end_time = None if next_activity is None else next_activity.start_time

            if start_journey_time > day24h_seconds or (next_end_time or -1) > day24h_seconds:
                time24h += day24h_seconds

            if (start_journey_time > 0 and start_journey_time <= time24h) and \
               (next_end_time is None or next_end_time == -1 or time24h <= next_end_time):
                selected_activity = activity
                break

        # validate activity is done
        if selected_activity:
            selected_index = self.person.identity.activities.index(selected_activity)
            if selected_index == state.last_activity_index:
                return None
        
        return selected_activity
    
    def get_home_location(self) -> Optional[Location]:
        if self.person.identity.home:
            return self.person.identity.home
        return None
 
class WorldPopulation:
    def __init__(self, population_loader: PopulationLoader):
        self.population_loader = population_loader
        self.people: Dict[PersonId, Person] = {}

    def init(self, world_bbox: BBox) -> "WorldPopulation":
        self.load_population(world_bbox)
        self.load_population_state()
        if settings.data.debug_people_ids:
            logger.info(f"Debugging with people: {settings.data.debug_people_ids}")
            self.people = {
                person_id: person
                for person_id, person in self.people.items()
                if person_id in settings.data.debug_people_ids
            }
        return self
    
    def dump_population_state(self):
        file_path = settings.data.state_file
        d = [
            {"person_id": p.person_id, "activity_id": act.id, "scheduled_start_time": act.scheduled_start_time}
            for p in self.get_people_list()
            for act in p.identity.activities
        ]
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=4)

    def load_population_state(self):
        file_path = settings.data.state_file
        if not os.path.isfile(file_path):
            return
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            m = {}
            for item in data:
                activity_id = item.get("activity_id")
                scheduled_start_time = item.get("scheduled_start_time")
                m[activity_id] = (scheduled_start_time, )

        for p in self.get_people_list():
            for act in p.identity.activities:
                if act.id in m:
                    (scheduled_start_time, ) = m[act.id]
                    act.scheduled_start_time = scheduled_start_time
                    logger.debug(f"Loaded activity {act.id} of person {p.person_id} with scheduled_start_time {scheduled_start_time}")

    def load_population(self, world_bbox: BBox):
        file_name = f"{settings.data.population_cache_prefix}{settings.data.population_max_size}_{settings.data.number_of_llm_based_agents}.json"
        if os.path.exists(file_name):
            logger.info(f"Loading population from {file_name}")
            with open(file_name, "r", encoding="utf-8") as f:
                people = json.load(f)
                self.people = {
                    person["person_id"]: Person.model_validate(person)
                    for person in people
                }
            return
        
        people = self.population_loader.load_population(
            max_size=settings.data.population_max_size,
            bbox=world_bbox,
        )

        n_llm_based = settings.data.number_of_llm_based_agents
        if n_llm_based > 0:
            llm_based_persons = random.sample(
                list(people),
                n_llm_based,
            )
            for person in llm_based_persons:
                person.is_llm_based = True

        self.people = {person.person_id: person for person in people}
        # cache to the file
        with open(file_name, "w", encoding="utf-8") as f:
            json.dump([
                person.model_dump() for person in self.people.values()
            ], f, ensure_ascii=False, indent=4)

    def get_people_list(self) -> List[Person]:
        return list(self.people.values())
    
    def get_llm_based_people_list(self) -> List[Person]:
        return [
            person for person in self.people.values() 
            if person.is_llm_based
        ]
    
    def get_person(self, person_id: PersonId) -> Person:
        return self.people.get(person_id)
    
    def get_person_home_location(self, person_id: PersonId) -> Location:
        person = self.get_person(person_id)
        if person is None:
            raise PersonNotFoundException(f"Person {person_id} not found")
        return PersonScheduler(person).get_home_location()
    
    @classmethod
    def get_person_default_scheduler(cls, person: Person) -> PersonScheduler:
        return PersonScheduler(person)

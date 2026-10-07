import sys
import os

this_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(this_dir, "../.."))

from helper import setup_logging
from settings import settings
settings.force_reload_paths(workdir=os.path.join(this_dir, "workdir"))
os.makedirs(settings.workdir , exist_ok=True)

settings.app.log_level = "DEBUG"
setup_logging(settings)

from scenarios.scenario_v1.agent import Context
from trip_helper.base import TripHelper
from models import Location, Person, TravelPlan
from text_helper import env_ob_to_text
from scenarios.scenario_v1.factory import bootstrap
import datetime
import asyncio
import pandas as pd
from tqdm.asyncio import tqdm

settings.data.number_of_llm_based_agents = 1
settings.data.population_max_size = 1
settings.gtfs.cache_enabled = False

sim = bootstrap()
agent = sim.agent
trip_helper = sim.trip_helper

default_person: Person = sim.population.get_people_list()[0]

async def test_plan():
    """Test travel plan generation"""
    person = default_person
    activities = person.identity.activities
    start_location = activities[0].location
    end_location = activities[1].location

    timestamp = int(datetime.datetime(2025, 3, 12, 10, 0, 0).timestamp())
    itineraries = await trip_helper.get_itineraries(
        origin=start_location,
        destination=end_location,
        departure_time=timestamp,
    )
    print(f"Found {len(itineraries)} itineraries")
    for itinerary in itineraries:
        print(f"----")
        print(itinerary.model_dump_json(indent=2))
    agent.plan_trip(
        Context(
            person=person,
            timestamp=timestamp,
        ),
        options=itineraries,
        destination=activities[1].purpose,
    )


def test_reflection():
    """Test reflection memory"""
    person = default_person
    sm = agent.get_short_term_memory(person.person_id)

    texts = [
        "Plan to head <leisure> with 1 transits, 0 transfers, including 1 Bus - estimated total time: 15 minutes.",
        "Walked 180 meters to 'Castanet-Tolosan'. Total walking time: 11 minutes.",
        "Waited at 'Castanet-Tolosan' for the Bus on the route 'Ramonville / Castanet-Tolosan'. Total waiting time: 16 minutes.",
        "I take Bus on the route 'Ramonville / Castanet-Tolosan', departed from 'Castanet-Tolosan' to 'Blum'. Total time: 20 minutes.",
        "Walked 36 meters to 'leisure'. Total walking time: 18 seconds.",
        "Arrived <leisure>. In ideally, it would take 15 minutes. Actual travel time is 32 minutes.",
        "Plan to head <shop> with 1 transits, 1 transfers, including 1 Bus - estimated total time: 8 minutes.",
        "Walked 36 meters to 'Blum'. Total walking time: 20 minutes.",
        "Waited at 'Blum' for the Bus on the route 'Malepère / Castanet-Tolosan'. Total waiting time: 31 minutes.",
        "I take Bus on the route 'Malepère / Castanet-Tolosan', departed from 'Blum' to 'Castanet République'. Total time: 31 minutes.",
        "Walked 382 meters to 'Halles'. Total walking time: 3 minutes.",
        "Walked 2 meters to 'shop'. Total walking time: 1 second.",
        "Arrived shop. In ideally, it would take 8 minutes. Actual travel time is 55 minutes.",
    ]
    
    for text in texts:
        # Simulate the agent processing the text
        sm.add_message(text, datetime.datetime.now())
    
    # Reflect on the conversation
    agent.reflect_memory(Context(
        person=person,
        timestamp=int(datetime.datetime.now().timestamp()),
        data=None
    ))

    # Print the reflection memory
    reflection_memory = agent.long_term_memory.get_user_all_memories(person.person_id)
    for entry in reflection_memory:
        print(f"Reflection Memory - {entry.timestamp}: {entry.content}")

if __name__ == "__main__":
    test_reflection()
    # asyncio.run(test_plan())

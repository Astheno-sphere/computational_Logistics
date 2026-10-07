from typing import Optional
from pydantic import BaseModel
from models import Location
from scenarios.scenario_v1.agent import LLMAgent
from world.population import WorldPopulation

class Action(BaseModel):
    person_id: str
    action: dict

class Observation(BaseModel):
    person_id: str
    activity_id: Optional[str] = None
    timestamp: int
    location: Location
    env_ob_code: str
    data: dict
    
class BaseScenario:
    agent: "LLMAgent"

    async def sync(self, timestamp: int, idle_people: list[Observation] = None):
        """Synchronize the scenario with a given timestamp"""
        raise NotImplementedError("This method should be overridden by subclasses")

    async def handle_observation(self, observation: Observation):
        """Handle observation data"""
        raise NotImplementedError("This method should be overridden by subclasses")

    async def has_messages(self) -> bool:
        """Check if there are messages to process"""
        raise NotImplementedError("This method should be overridden by subclasses")

    async def pop_all_messages(self) -> list[Action]:
        """Pop all messages from the queue"""
        raise NotImplementedError("This method should be overridden by subclasses")

    @property
    def population(self) -> "WorldPopulation":
        """Get the current population of the scenario"""
        raise NotImplementedError("This method should be overridden by subclasses")

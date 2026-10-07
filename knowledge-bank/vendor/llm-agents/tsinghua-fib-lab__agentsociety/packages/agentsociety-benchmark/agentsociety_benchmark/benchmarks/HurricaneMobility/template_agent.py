from agentsociety.agent import CitizenAgentBase
from pycityproto.city.person.v2.motion_pb2 import Status
import random

class HurricaneMobilityAgent(CitizenAgentBase):
    """
    A template agent for the Hurricane Mobility Generation benchmark.
    A simple agent that moves to a random destination every hour.
    """    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.movement_status = [Status.STATUS_WALKING, Status.STATUS_DRIVING]

    async def go_to_aoi(self, aoi_id: int):
        assert self.environment is not None
        await self.environment.set_aoi_schedules(
            self.id,
            target_positions = aoi_id,
        )

    def get_current_weather(self):
        assert self.environment is not None
        weather_statement = self.environment.sense("weather")
        return weather_statement

    async def forward(self):
        # ======================== Result Related API ========================
        # You need to choose a destination and go to it with intention
        # 1. Go to a destination with go_to_aoi
        # randomly select a destination
        assert self.environment is not None
        aoi_ids = self.environment.get_aoi_ids()
        destination_aoi_id = random.choice(aoi_ids)
        # move to the destination
        await self.go_to_aoi(destination_aoi_id)
        # ======================== Result Related API ========================
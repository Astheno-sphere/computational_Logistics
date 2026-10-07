from typing import List
from models import Location, TravelPlan


class TripHelper:
    def __init__(self):
        pass

    async def get_itineraries(self, 
                              origin: Location, 
                              destination: Location, 
                              departure_time: int) -> List[TravelPlan]:
        """
        Get itineraries for a given origin, destination and departure time.
        """
        raise NotImplementedError()

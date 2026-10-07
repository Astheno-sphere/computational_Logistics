from typing import Optional
from pydantic import BaseModel
from text_helper.templates.repository import tpl_describe_the_ob_transit
from text_helper.type import EnvOb

class EnvObTransit(EnvOb):
    waiting_time: int
    is_crowded: Optional[bool] = False
    distance: float
    duration: int
    arrival_stop_name: str
    departure_stop_name: str
    # n_persons_at_arrival_stop: int
    # n_persons_at_departure_stop: int
    # waiting_trip_count: Optional[int] = None
    by_vehicle_route_id: str

    def describe(self) -> str:
        # Describe the transit observation in a human-readable format
        return tpl_describe_the_ob_transit.render(
            ob=self,
        )


if __name__ == "__main__":
    # Example usage
    event = EnvObTransit(
        timestamp=1234567890,
        moving_id="123",
        waiting_time=0,
        capacity_utilization=0.8,
        distance=100.0,
        duration=10,
        arrival_stop_name="A",
        departure_stop_name="B",
        by_vehicle_route_id="route_1"
    )
    print(event.describe())
    # Example usage
    event = EnvObTransit(
        timestamp=1234567890,
        moving_id="123",
        waiting_time=10,
        capacity_utilization=0.8,
        distance=100.0,
        duration=10,
        arrival_stop_name="A",
        departure_stop_name="B",
        by_vehicle_route_id="route_1"
    )
    print(event.describe())

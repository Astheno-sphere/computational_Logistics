from typing import Optional
from pydantic import BaseModel
from text_helper.templates.repository import tpl_describe_the_ob_trip_feedback
from text_helper.type import EnvOb

class EnvObArrival(EnvOb):
    expected_arrive_at: int
    prepare_before_seconds: Optional[int] = 0
    arrive_at: int
    purpose: str
    duration: Optional[float]
    plan_duration: Optional[float]
    moving_id: Optional[str] = None

    @property
    def late(self) -> int:
        return max(0, self.arrive_at - self.expected_arrive_at)

    @property
    def is_late(self) -> bool:
        return self.late > 0

    def describe(self) -> str:
        # Describe the trip feedback observation in a human-readable format
        return tpl_describe_the_ob_trip_feedback.render(
            ob=self,
        )
    

if __name__ == "__main__":
    # Example usage
    event = EnvObArrival(
        type="arrival",
        timestamp=1234567890,
        moving_id="123",
        expected_arrive_at=1234567890,
        arrive_at=1234567890,
        purpose="work",
        duration=3600.0,
        plan_duration=2600.0,
    )
    print(event.describe())


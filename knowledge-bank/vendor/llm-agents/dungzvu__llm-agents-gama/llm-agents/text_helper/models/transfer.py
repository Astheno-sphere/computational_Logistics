from typing import Optional
from pydantic import BaseModel
from text_helper.templates.repository import tpl_describe_the_ob_transfer
from text_helper.type import EnvOb

class EnvObTransfer(EnvOb):
    """Transfer event from A to B by walking"""
    distance: float
    duration: float
    from_name: Optional[str] = None
    destination_name: str

    @property
    def is_arrival(self) -> bool:
        return self.destination_name in ["home", "education", "work", "leisure", "shop"]

    def describe(self) -> str:
        # Describe the transfer observation in a human-readable format
        return tpl_describe_the_ob_transfer.render(
            ob=self,
        )

if __name__ == "__main__":
    # Example usage
    event = EnvObTransfer(
        timestamp=1234567890,
        moving_id="123",
        distance=100.0,
        duration=10.0,
        from_name="A",
        destination_name="B"
    )
    print(event.describe())
    # Example usage
    event = EnvObTransfer(
        timestamp=1234567890,
        moving_id="123",
        distance=100.0,
        duration=10.0,
        destination_name="B"
    )
    print(event.describe())

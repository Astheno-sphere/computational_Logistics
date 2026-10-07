from typing import Optional
from models import Person, BBox


class PopulationLoader:
    def load_population(self, max_size: int, bbox: Optional[BBox]=None) -> list[Person]:
        raise NotImplementedError("This method should be overridden by subclasses")

class Filter:
    def is_valid(self, person: Person) -> bool:
        raise NotImplementedError("This method should be overridden by subclasses")

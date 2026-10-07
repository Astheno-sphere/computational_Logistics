from settings import settings
from models import BBox, Location
from inputs.gtfs.reader import GTFSData
from world.population import WorldPopulation
from pydantic import BaseModel
from utils import world_projection
import math


class WorldTime:
    def __init__(self):
        self.timestamp = 0

    @property
    def CURRENT_TIMESTAMP(self) -> float:
        return self.timestamp
    
    def update_timestamp(self, timestamp: float):
        self.timestamp = timestamp

class TimeGrid:
    def __init__(self):
        self.time_step = settings.world.time_step
        self.time_slots = math.ceil(24 * 3600 / self.time_step)

    def get_time_slot(self, time: float) -> int:
        return int(time // self.time_step) % self.time_slots
    
    def time_slot_to_text(self, time_slot: int) -> str:
        start_from = time_slot * self.time_step
        end_to = (time_slot + 1) * self.time_step
        start_hour = int(start_from // 3600)
        start_minute = int((start_from % 3600) // 60)
        end_hour = int(end_to // 3600)
        end_minute = int((end_to % 3600) // 60)
        return f"{start_hour:02d}:{start_minute:02d} - {end_hour:02d}:{end_minute:02d}"

class WorldGrid:
    def __init__(self, bbox: BBox):
        self.grid_size = settings.world.grid_size
        x1, y1 = world_projection(Location(lon=bbox.min_lon, lat=bbox.min_lat))
        x2, y2 = world_projection(Location(lon=bbox.max_lon, lat=bbox.max_lat))
        self.bbox = (x1, y1, x2, y2)
        self.x_cells = math.ceil((x2 - x1) / self.grid_size)
        self.y_cells = math.ceil((y2 - y1) / self.grid_size)

    def get_location_grid(self, location: Location) -> tuple[int, int]:
        x, y = world_projection(location)
        assert (
            self.bbox[0] <= x <= self.bbox[2]
            and self.bbox[1] <= y <= self.bbox[3]
        ), "Location is outside the bounding box"
        x_cell = int((x - self.bbox[0]) / self.grid_size)
        y_cell = int((y - self.bbox[1]) / self.grid_size)
        return x_cell, y_cell


class WorldModel(BaseModel):
    world_grid: WorldGrid
    time_grid: TimeGrid
    # world_time: WorldTime
    gtfs_data: GTFSData
    population: WorldPopulation
    bbox: BBox

    class Config:
        arbitrary_types_allowed = True

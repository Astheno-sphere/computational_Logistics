from typing import List, Optional, TypeAlias
from enum import Enum
from pydantic import BaseModel

""" Base models
"""
class LocationType(str, Enum):
    HOME = "home"
    WORK = "work"
    EDUCATION = "education"
    OTHER = "other"


class Location(BaseModel):
    lon: float
    lat: float


class BBox(BaseModel):
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float


""" Schedule
"""
ActivityPurpose: TypeAlias = str

class Activity(BaseModel):
    id: str
    # scheduled start time over the day
    scheduled_start_time: Optional[float] = None
    start_time: float
    end_time: float
    purpose: ActivityPurpose
    location: Optional[Location] = None
    # TODO: how to populate this from location?
    # location_name: Optional[str] = None


""" Travel plan
"""
RouteShape: TypeAlias = str

class TransitLocation(Location):
    stop: str
    lat: float
    lon: float

class Transit(BaseModel):
    start_time: int
    end_time: int
    start_location: TransitLocation
    end_location: TransitLocation
    # route_shape: Optional[RouteShape] = None
    is_transfer: bool = False
    transit_route: Optional[str] = None
    shape_id: Optional[List[str]] = None
    transit_agency: Optional[str] = None
    duration: Optional[int] = None
    distance: Optional[float] = None
    mode: Optional[str] = None

    def get_duration(self) -> int:
        return self.duration or int((self.end_time - self.start_time) // 1000)
    
    def get_distance(self) -> float:
        return self.distance or 100.0

    def get_code(self) -> str:
        return "^".join([self.transit_route, self.start_location.stop, self.end_location.stop])
    
class TravelPlan(BaseModel):
    id: str
    start_location: Location
    end_location: Location
    start_time: int
    end_time: int
    start_in: Optional[int] = 0  # seconds from now
    purpose: Optional[str] = None
    duration: Optional[int] = None
    distance: Optional[float] = None
    legs: List[Transit]

    def get_code(self) -> str:
        """
        Generate a code for the travel plan based on its attributes.
        This can be used to identify the plan in logs or messages.
        """
        return "+".join([
            leg.get_code() for leg in self.legs if not leg.is_transfer
        ])


""" Agent & Simulation
"""
class PersonMove(BaseModel):
    # the id for quickly identifying and updating the move
    id: str
    person_id: str
    current_time: int
    expected_arrive_at: int
    prepare_before_seconds: Optional[int] = 0
    purpose: Optional[str] = None
    target_location: Optional[Location] = None
    for_activity: Optional[Activity] = None
    plan: Optional[TravelPlan] = None


""" Personal Identity
"""
PersonId: TypeAlias = str

class PersonalIdentity(BaseModel):
    name: str
    traits_json: dict
    home: Optional[Location] = None
    activities: Optional[List[Activity]] = None


class PersonState(BaseModel):
    last_location: Optional[Location] = None
    last_activity_index: Optional[int] = 0
    cache_current_activity: Optional[Activity] = None  # current activity
    heading_to: Optional[str] = None  # purpose of the next activity


class Person(BaseModel):
    person_id: PersonId
    identity: PersonalIdentity
    state: PersonState = PersonState()
    # hybrid technique
    is_llm_based: bool = False

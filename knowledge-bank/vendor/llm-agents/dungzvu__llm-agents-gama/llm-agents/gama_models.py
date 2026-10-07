from enum import Enum
from pydantic import BaseModel
from models import Location, PersonId
from typing import Any, Generic, Optional, TypeVar


class MessageType(str, Enum):
    # Agent to GAMA
    AG_WORLD_INIT = "ag_world_init"
    AG_PEOPLE_NEXT_MOVE = "ag_people_next_move"
    AG_PEOPLE_BATCH_NEXT_MOVE = "ag_people_batch_next_move"
    AG_ACK = "ag_ack"
    UNKNOWN = "unknown"
    # GAMA to Agent
    # GA_PEOPLE_OBSERVATION_UPDATE = "ga_people_observation_update"
    # GA_PEOPLE_ASK_MOVE = "ga_people_ask_move"


T = TypeVar("T")

class MessageResponse(BaseModel, Generic[T]):
    success: bool = True
    error: Optional[str] = None
    error_code: Optional[str] = None
    message_type: Optional[MessageType] = MessageType.UNKNOWN
    data: Optional[T] = None


class BaseRequest(BaseModel):
    timestamp: int

""" World Initialization
"""
class WorldInitRequest(BaseRequest):
    pass

class WorldSyncIdlePeople(BaseModel):
    person_id: PersonId
    location: Location

class WorldSyncRequest(BaseRequest):
    idle_people: Optional[list[WorldSyncIdlePeople]] = None

class GamaPersonData(BaseModel):
    person_id: PersonId
    name: str
    location: Location
    is_llm_based: bool = False


class WorldInitResponse(BaseModel):
    people: list[GamaPersonData]
    num_people: int
    timestamp: int


""" People Next Move
"""
class PeopleNextMoveRequest(BaseRequest):
    person_id: PersonId
    from_purpose: Optional[str] = None
    from_location: Optional[Location] = None

""" People Next Move Batch
"""
class PeopleBatchNextMoveRequest(BaseRequest):
    people: list[PeopleNextMoveRequest]

""" Observation Update
"""
class ObservationUpdateRequest(BaseRequest):
    person_id: PersonId
    type: str
    data: Any

class ObservationBatchUpdateRequest(BaseRequest):
    observations: list[ObservationUpdateRequest]

""" Daily cron
"""
class DailyCronRequest(BaseRequest):
    pass

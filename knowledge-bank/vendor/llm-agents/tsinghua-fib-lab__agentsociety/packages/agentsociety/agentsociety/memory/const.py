from enum import Enum
from typing import Optional

from pycityproto.city.person.v2.motion_pb2 import Status
from pydantic import BaseModel, Field

__all__ = [
    "RelationType",
    "SocialRelation",
    "PROFILE_ATTRIBUTES",
    "STATE_ATTRIBUTES",
]


class RelationType(str, Enum):
    """
    The type of the relation.
    """

    FRIEND = "friend"
    FAMILY = "family"
    COLLEAGUE = "colleague"
    FOLLOWER = "follower"
    FOLLOWING = "following"


class SocialRelation(BaseModel):
    """
    Social relation between two agents.
    """

    source_id: Optional[int] = Field(
        default=None, description="The id of the source agent"
    )
    target_id: int = Field(..., description="The id of the target agent")
    kind: RelationType = Field(..., description="The type of the relation")
    strength: Optional[float] = Field(
        default=0.0, description="The strength of the relation", ge=0.0, le=1.0
    )


PROFILE_ATTRIBUTES = {
    "name": str(),
    "gender": str(),
    "age": float(),
    "education": str(),
    "skill": str(),
    "occupation": str(),
    "family_consumption": str(),
    "consumption": str(),
    "personality": str(),
    "income": float(),
    "currency": float(),
    "residence": str(),
    "race": str(),
    "city": str(),
    "religion": str(),
    "marriage_status": str(),
    "background_story": str(),
    "social_network": list[SocialRelation](),
    "status_summary": str(),
}

STATE_ATTRIBUTES = {
    # base
    "id": -1,
    "attribute": dict(),
    "home": dict(),
    "work": dict(),
    "schedules": [],
    "vehicle_attribute": dict(),
    "bus_attribute": dict(),
    "pedestrian_attribute": dict(),
    "bike_attribute": dict(),
    # motion
    "status": Status.STATUS_UNSPECIFIED,
    "position": dict(),
    "v": float(),
    "direction": float(),
    "activity": str(),
    "l": float(),
    "survey_responses": list(),
}

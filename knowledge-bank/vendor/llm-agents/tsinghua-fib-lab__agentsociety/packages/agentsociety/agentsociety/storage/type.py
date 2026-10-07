import enum
from typing import Optional
from pydantic import BaseModel
from datetime import datetime
import uuid

__all__ = [
    "StorageSurvey",
    "StorageDialogType",
    "StorageDialog",
    "StorageGlobalPrompt",
    "StorageProfile",
    "StorageStatus",
    "StoragePendingDialog",
    "StoragePendingSurvey",
    "StorageTaskResult",
]


class StorageExpInfo(BaseModel):
    tenant_id: str
    id: str
    name: str
    num_day: int
    status: int
    cur_day: int
    cur_t: float
    config: str
    error: str
    input_tokens: int
    output_tokens: int
    created_at: datetime
    updated_at: datetime


class StorageSurvey(BaseModel):
    id: int
    day: int
    t: float
    survey_id: uuid.UUID
    result: str
    created_at: datetime


class StorageDialogType(enum.IntEnum):
    """Storage dialog type"""

    Thought = 0  # Dialog in agent self
    Talk = 1  # Dialog with other agents
    User = 2  # Dialog with user


class StorageDialog(BaseModel):
    id: int
    day: int
    t: float
    type: int
    speaker: str
    content: str
    created_at: datetime


class StorageGlobalPrompt(BaseModel):
    day: int
    t: float
    prompt: str
    created_at: datetime


class StorageProfile(BaseModel):
    id: int
    name: str
    profile: str


class StorageStatus(BaseModel):
    id: int
    day: int
    t: float
    lng: Optional[float]
    lat: Optional[float]
    parent_id: Optional[int]
    action: str
    status: str
    created_at: datetime


class StoragePendingDialog(BaseModel):
    """Pending dialog storage type"""

    id: int
    """Pending dialog ID"""
    agent_id: int
    """Agent ID"""
    day: int
    """Day"""
    t: float
    """Time"""
    content: str
    """Content"""
    created_at: datetime
    """Created time"""
    processed: bool
    """Whether the dialog has been processed"""


class StoragePendingSurvey(BaseModel):
    """Pending survey storage type"""

    id: int
    """Pending survey ID"""
    agent_id: int
    """Agent ID"""
    day: int
    """Day"""
    t: float
    """Time"""
    survey_id: uuid.UUID
    """Survey ID"""
    data: dict
    """Data"""
    created_at: datetime
    """Created time"""
    processed: bool
    """Whether the survey has been processed"""


class StorageTaskResult(BaseModel):
    id: int
    """Task ID"""
    agent_id: int
    """Agent ID"""
    context: dict
    """Context"""
    ground_truth: dict
    """Ground truth"""
    result: dict
    """Result"""
    created_at: datetime

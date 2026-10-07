import enum
import uuid
from datetime import datetime

from pydantic import AwareDatetime, BaseModel
from sqlalchemy.orm import Mapped, mapped_column

from ._base import TABLE_PREFIX, Base
from ...storage import Experiment

__all__ = [
    "Experiment",
    "ExperimentStatus",
    "ApiExperiment",
    "ApiTime",
    "RunningExperiment",
]

# Database Models


class RunningExperiment(Base):
    """Running experiment model"""

    __tablename__ = f"{TABLE_PREFIX}running_experiment"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column()
    callback_auth_token: Mapped[str] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)


class ExperimentStatus(enum.IntEnum):
    """Experiment status"""

    NOT_STARTED = 0  # The experiment is not started
    RUNNING = 1  # The experiment is running
    FINISHED = 2  #  The experiment is finished
    ERROR = 3  # The experiment has error and stopped
    STOPPED = 4  # The experiment is stopped by user


class ApiExperiment(BaseModel):
    """Experiment model for API"""

    tenant_id: str
    """Tenant ID"""
    id: uuid.UUID
    """Experiment ID"""
    name: str
    """Experiment name"""
    num_day: int
    """Number of days"""
    status: ExperimentStatus
    """Experiment status"""
    cur_day: int
    """Current day"""
    cur_t: float
    """Current time (second)"""
    config: str
    """Experiment configuration"""
    error: str
    """Error message"""
    input_tokens: int
    """Input tokens"""
    output_tokens: int
    """Output tokens"""
    created_at: AwareDatetime
    """Created time"""
    updated_at: AwareDatetime
    """Updated time"""

    class Config:
        from_attributes = True


class ApiTime(BaseModel):
    """Time model for API"""

    day: int
    t: float

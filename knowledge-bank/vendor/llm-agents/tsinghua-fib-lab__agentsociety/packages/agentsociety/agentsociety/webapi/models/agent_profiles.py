import uuid
from datetime import datetime
from typing import Optional

from pydantic import AwareDatetime, BaseModel
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import DateTime
from sqlalchemy.sql import func

from ._base import Base, TABLE_PREFIX

__all__ = [
    "AgentProfile",
    "ApiAgentProfile",
]


class AgentProfile(Base):
    """Agent profile data model for storing metadata about agent data files"""

    __tablename__ = f"{TABLE_PREFIX}agent_profile_data"

    tenant_id: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column()
    description: Mapped[Optional[str]] = mapped_column()
    agent_type: Mapped[str] = mapped_column()
    file_path: Mapped[str] = mapped_column()  # Path to the S3 file
    record_count: Mapped[int] = mapped_column()  # Number of records in the file
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False
    )


class ApiAgentProfile(BaseModel):
    """Agent profile model for API"""

    tenant_id: Optional[str] = None
    """Tenant ID"""
    id: Optional[uuid.UUID] = None
    """Profile ID"""
    name: str
    """Profile name"""
    description: Optional[str] = None
    """Profile description"""
    agent_type: str
    """Agent type"""
    file_path: str
    """Path to the S3 file"""
    record_count: int
    """Number of records in the file"""
    created_at: Optional[AwareDatetime] = None
    """Created time"""
    updated_at: Optional[AwareDatetime] = None
    """Updated time"""

    class Config:
        from_attributes = True

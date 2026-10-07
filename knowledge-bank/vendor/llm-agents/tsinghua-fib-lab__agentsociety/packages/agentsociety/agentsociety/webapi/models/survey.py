import uuid
from datetime import datetime
from typing import Any

from pydantic import AwareDatetime, BaseModel
from sqlalchemy.orm import Mapped, mapped_column

from ._base import Base, TABLE_PREFIX

__all__ = ["Survey"]

# Database Models


class Survey(Base):
    """Survey model"""

    __tablename__ = f"{TABLE_PREFIX}survey"

    tenant_id: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column()
    data: Mapped[Any] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now, onupdate=datetime.now
    )


# API Models


class ApiSurvey(BaseModel):
    """Survey model for API"""

    id: uuid.UUID
    """Survey ID"""
    name: str
    """Survey name"""
    data: Any
    """Survey data (any JSON object)"""
    created_at: AwareDatetime
    """Created time"""
    updated_at: AwareDatetime
    """Updated time"""

    class Config:
        from_attributes = True

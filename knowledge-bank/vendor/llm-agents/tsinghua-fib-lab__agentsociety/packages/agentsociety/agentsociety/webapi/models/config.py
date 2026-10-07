import uuid
from datetime import datetime
from typing import Optional, Any
from fastapi import HTTPException, status
from pydantic import AwareDatetime, BaseModel
from sqlalchemy.orm import Mapped, mapped_column

# RealXXXConfig is used to define the real pydantic model of the config used in AgentSociety
from ...llm import LLMConfig as RealLLMConfig
from ...environment import MapConfig as RealMapConfig
from ...configs import AgentsConfig as RealAgentsConfig
from ...configs import WorkflowStepConfig as RealWorkflowStepConfig

from ._base import Base, TABLE_PREFIX

__all__ = [
    "RealLLMConfig",
    "RealMapConfig",
    "RealAgentsConfig",
    "RealWorkflowStepConfig",
    "LLMConfig",
    "ApiLLMConfig",
    "MapConfig",
    "MapTempDownloadLink",
    "ApiMapConfig",
    "AgentConfig",
    "ApiAgentConfig",
    "WorkflowConfig",
    "ApiWorkflowConfig",
]


class LLMConfig(Base):
    """LLM model"""

    __tablename__ = f"{TABLE_PREFIX}llm_config"

    tenant_id: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column()
    description: Mapped[Optional[str]] = mapped_column()
    config: Mapped[Any] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now, onupdate=datetime.now
    )


class ApiLLMConfig(BaseModel):
    """LLM model for API"""

    tenant_id: Optional[str] = None
    """Tenant ID"""
    id: Optional[uuid.UUID] = None
    """LLM Config ID"""
    name: str
    """LLM Config name"""
    description: Optional[str] = None
    """LLM Config description"""
    config: list[dict[str, Any]]
    """LLM Config configuration"""
    created_at: Optional[AwareDatetime] = None
    """Created time"""
    updated_at: Optional[AwareDatetime] = None
    """Updated time"""

    class Config:
        from_attributes = True

    def validate_config(self):
        for config in self.config:
            RealLLMConfig.model_validate(config)


class MapConfig(Base):
    """Map model"""

    __tablename__ = f"{TABLE_PREFIX}map_config"

    tenant_id: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column()
    description: Mapped[Optional[str]] = mapped_column()
    config: Mapped[Any] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now, onupdate=datetime.now
    )

class MapTempDownloadLink(Base):
    """Map temp download link model"""

    __tablename__ = f"{TABLE_PREFIX}map_temp_download_link"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    map_config_id: Mapped[uuid.UUID] = mapped_column()
    token: Mapped[str] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    expire_at: Mapped[datetime] = mapped_column()

class ApiMapConfig(BaseModel):
    """Map model for API"""

    tenant_id: Optional[str] = None
    """Tenant ID"""
    id: Optional[uuid.UUID] = None
    """Map Config ID"""
    name: str
    """Map Config name"""
    description: Optional[str] = None
    """Map Config description"""
    config: dict[str, Any]
    """Map Config configuration"""
    created_at: Optional[AwareDatetime] = None
    """Created time"""
    updated_at: Optional[AwareDatetime] = None
    """Updated time"""

    class Config:
        from_attributes = True

    def validate_config(self):
        real_config = RealMapConfig.model_validate(self.config)
        # the map file path must have prefix: maps/{tenant_id}/
        check_path = f"maps/{self.tenant_id}/" if self.tenant_id else "maps/"
        if not real_config.file_path.startswith(check_path):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"the map file path must have prefix: {check_path}, but got {real_config.file_path}",
            )
        self.config = real_config.model_dump()


class AgentConfig(Base):
    """Agent model"""

    __tablename__ = f"{TABLE_PREFIX}agent_config"

    tenant_id: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column()
    description: Mapped[Optional[str]] = mapped_column()
    config: Mapped[Any] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now, onupdate=datetime.now
    )


class ApiAgentConfig(BaseModel):
    """Agent model for API"""

    tenant_id: Optional[str] = None
    """Tenant ID"""
    id: Optional[uuid.UUID] = None
    """Agent Config ID"""
    name: str
    """Agent Config name"""
    description: Optional[str] = None
    """Agent Config description"""
    config: dict[str, Any]
    """Agent Config configuration"""
    created_at: Optional[AwareDatetime] = None
    """Created time"""
    updated_at: Optional[AwareDatetime] = None
    """Updated time"""

    class Config:
        from_attributes = True

    def validate_config(self):
        RealAgentsConfig.model_validate(self.config)


class WorkflowConfig(Base):
    """Workflow model"""

    __tablename__ = f"{TABLE_PREFIX}workflow_config"

    tenant_id: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column()
    description: Mapped[Optional[str]] = mapped_column()
    config: Mapped[Any] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now, onupdate=datetime.now
    )


class ApiWorkflowConfig(BaseModel):
    """Workflow model for API"""

    tenant_id: Optional[str] = None
    """Tenant ID"""
    id: Optional[uuid.UUID] = None
    """Workflow Config ID"""
    name: str
    """Workflow Config name"""
    description: Optional[str] = None
    """Workflow Config description"""
    config: list[dict[str, Any]]
    """Workflow Config configuration"""
    created_at: Optional[AwareDatetime] = None
    """Created time"""
    updated_at: Optional[AwareDatetime] = None
    """Updated time"""

    class Config:
        from_attributes = True

    def validate_config(self):
        for config in self.config:
            RealWorkflowStepConfig.model_validate(config)

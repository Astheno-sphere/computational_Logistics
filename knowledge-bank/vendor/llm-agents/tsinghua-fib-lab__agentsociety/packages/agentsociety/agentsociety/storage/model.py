import uuid
from datetime import datetime

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    Column,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    JSON,
    UUID,
)
from sqlalchemy.orm import Mapped, mapped_column

from ._base import TABLE_PREFIX, Base

__all__ = [
    "agent_profile",
    "agent_status",
    "agent_survey",
    "agent_dialog",
    "global_prompt",
    "pending_dialog",
    "pending_survey",
    "metric",
    "task_result",
]


def agent_profile(table_name: str):
    """Create agent profile table"""
    metadata = MetaData()
    return Table(
        table_name,
        metadata,
        Column("id", Integer),
        Column("name", String),
        Column("profile", JSON),
    ), ["id", "name", "profile"]


def agent_status(table_name: str):
    """Create agent status table"""
    metadata = MetaData()
    return Table(
        table_name,
        metadata,
        Column("id", Integer),
        Column("day", Integer),
        Column("t", Float),
        Column("lng", Float, nullable=True),
        Column("lat", Float, nullable=True),
        Column("parent_id", Integer),
        Column("action", String),
        Column("status", JSON),
        Column("created_at", TIMESTAMP(timezone=True)),
    ), ["id", "day", "t", "lng", "lat", "parent_id", "action", "status", "created_at"]


def agent_survey(table_name: str):
    """Create agent survey table"""
    metadata = MetaData()
    return Table(
        table_name,
        metadata,
        Column("id", Integer),
        Column("day", Integer),
        Column("t", Float),
        Column("survey_id", UUID),
        Column("result", JSON),
        Column("created_at", TIMESTAMP(timezone=True)),
    ), ["id", "day", "t", "survey_id", "result", "created_at"]


def agent_dialog(table_name: str):
    """Create agent dialog table"""
    metadata = MetaData()
    return Table(
        table_name,
        metadata,
        Column("id", Integer),
        Column("day", Integer),
        Column("t", Float),
        Column("type", Integer),
        Column("speaker", String),
        Column("content", String),
        Column("created_at", TIMESTAMP(timezone=True)),
    ), ["id", "day", "t", "type", "speaker", "content", "created_at"]


def global_prompt(table_name: str):
    """Create global prompt table"""
    metadata = MetaData()
    return Table(
        table_name,
        metadata,
        Column("day", Integer),
        Column("t", Float),
        Column("prompt", String),
        Column("created_at", TIMESTAMP(timezone=True)),
    ), ["day", "t", "prompt", "created_at"]


def pending_dialog(table_name: str):
    """Create pending dialog table"""
    metadata = MetaData()
    return Table(
        table_name,
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("agent_id", Integer),
        Column("day", Integer),
        Column("t", Float),
        Column("content", String),
        Column("created_at", TIMESTAMP(timezone=True)),
        Column("processed", Boolean, default=False),
    ), ["id", "agent_id", "day", "t", "content", "created_at", "processed"]


def pending_survey(table_name: str):
    """Create pending survey table"""
    metadata = MetaData()
    return Table(
        table_name,
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("agent_id", Integer),
        Column("day", Integer),
        Column("t", Float),
        Column("survey_id", UUID),
        Column("data", JSON),
        Column("created_at", TIMESTAMP(timezone=True)),
        Column("processed", Boolean, default=False),
    ), ["id", "agent_id", "day", "t", "survey_id", "data", "created_at", "processed"]


def task_result(table_name: str):
    """Create task result table"""
    metadata = MetaData()
    return Table(
        table_name,
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("agent_id", Integer),
        Column("context", JSON),
        Column("ground_truth", JSON),
        Column("result", JSON),
        Column("created_at", TIMESTAMP(timezone=True)),
    ), ["id", "agent_id", "context", "ground_truth", "result", "created_at"]


def metric(table_name: str):
    """Create metric table"""
    metadata = MetaData()
    return Table(
        table_name,
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("key", String),
        Column("value", Float),
        Column("step", Integer),
        Column("created_at", TIMESTAMP(timezone=True)),
    ), ["id", "key", "value", "step", "created_at"]


class Experiment(Base):
    """Experiment model"""

    __tablename__ = f"{TABLE_PREFIX}experiment"

    tenant_id: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column()
    num_day: Mapped[int] = mapped_column()
    status: Mapped[int] = mapped_column()
    cur_day: Mapped[int] = mapped_column()
    cur_t: Mapped[float] = mapped_column()
    config: Mapped[str] = mapped_column()
    error: Mapped[str] = mapped_column()
    input_tokens: Mapped[int] = mapped_column(default=0)
    output_tokens: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now, onupdate=datetime.now
    )

    @property
    def agent_profile_tablename(self):
        """Get agent profile table name"""
        return f"{TABLE_PREFIX}{str(self.id).replace('-', '_')}_agent_profile"

    @property
    def agent_status_tablename(self):
        """Get agent status table name"""
        return f"{TABLE_PREFIX}{str(self.id).replace('-', '_')}_agent_status"

    @property
    def agent_dialog_tablename(self):
        """Get agent dialog table name"""
        return f"{TABLE_PREFIX}{str(self.id).replace('-', '_')}_agent_dialog"

    @property
    def agent_survey_tablename(self):
        """Get agent survey table name"""
        return f"{TABLE_PREFIX}{str(self.id).replace('-', '_')}_agent_survey"

    @property
    def global_prompt_tablename(self):
        """Get global prompt table name"""
        return f"{TABLE_PREFIX}{str(self.id).replace('-', '_')}_global_prompt"

    @property
    def pending_dialog_tablename(self):
        """Get pending dialog table name"""
        return f"{TABLE_PREFIX}{str(self.id).replace('-', '_')}_pending_dialog"

    @property
    def pending_survey_tablename(self):
        """Get pending survey table name"""
        return f"{TABLE_PREFIX}{str(self.id).replace('-', '_')}_pending_survey"
    
    @property
    def task_result_tablename(self):
        """Get task result table name"""
        return f"{TABLE_PREFIX}{str(self.id).replace('-', '_')}_task_result"

    @property
    def metric_tablename(self):
        """Get metric table name"""
        return f"{TABLE_PREFIX}{str(self.id).replace('-', '_')}_metric"

    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "num_day": self.num_day,
            "status": self.status,
            "cur_day": self.cur_day,
            "cur_t": self.cur_t,
            "config": self.config,
            "error": self.error,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
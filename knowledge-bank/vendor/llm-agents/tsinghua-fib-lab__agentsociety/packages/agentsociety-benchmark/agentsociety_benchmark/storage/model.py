
import uuid
from datetime import datetime

from sqlalchemy.orm import Mapped, mapped_column

from ._base import TABLE_PREFIX, Base


class Benchmark(Base):
    """Benchmark model"""

    __tablename__ = f"{TABLE_PREFIX}benchmark"

    tenant_id: Mapped[str] = mapped_column(primary_key=True)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    benchmark_name: Mapped[str] = mapped_column()
    llm: Mapped[str] = mapped_column()
    agent: Mapped[str] = mapped_column()
    agent_filename: Mapped[str] = mapped_column()
    result_filename: Mapped[str] = mapped_column()
    status: Mapped[int] = mapped_column()
    result_info: Mapped[str] = mapped_column()
    final_score: Mapped[float] = mapped_column()
    config: Mapped[str] = mapped_column()
    error: Mapped[str] = mapped_column()
    official_validated: Mapped[bool] = mapped_column(default=False)
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
            "benchmark_name": self.benchmark_name,
            "llm": self.llm,
            "agent": self.agent,
            "agent_filename": self.agent_filename,
            "result_filename": self.result_filename,
            "status": self.status,
            "result_info": self.result_info,
            "final_score": self.final_score,
            "config": self.config,
            "error": self.error,
            "official_validated": self.official_validated,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

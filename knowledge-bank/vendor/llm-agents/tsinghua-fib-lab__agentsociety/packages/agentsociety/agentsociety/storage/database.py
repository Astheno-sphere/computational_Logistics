import asyncio
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional, Dict, List, Any
import uuid

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select, update, text, and_, desc, asc
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
import yaml

from ..logger import get_logger
from ..utils.decorators import lock_decorator
from .model import (
    Experiment,
    agent_profile,
    agent_status,
    agent_survey,
    agent_dialog,
    global_prompt,
    pending_dialog,
    pending_survey,
    metric,
    task_result,
)
from ._base import Base, TABLE_PREFIX
from .type import (
    StorageDialog,
    StorageExpInfo,
    StorageGlobalPrompt,
    StoragePendingDialog,
    StoragePendingSurvey,
    StorageProfile,
    StorageStatus,
    StorageSurvey,
    StorageTaskResult,
)

__all__ = ["DatabaseWriter", "DatabaseConfig"]


class DatabaseConfig(BaseModel):
    """Database configuration class supporting multiple database types."""

    enabled: bool = Field(True)
    """Whether database storage is enabled"""

    db_type: Literal["postgresql", "sqlite"] = Field("sqlite")
    """Database type"""

    pg_dsn: Optional[str] = Field(None)
    """Database connection string (PostgreSQL)"""

    @model_validator(mode="after")
    def validate_config(self):
        if not self.enabled:
            return self
        if self.db_type == "postgresql" and not self.pg_dsn:
            raise ValueError("PostgreSQL DSN is required")
        return self
    
    def get_dsn(self, sqlite_path: Path):
        """Create async SQLAlchemy engine based on configuration"""
        if self.db_type == "postgresql":
            assert self.pg_dsn is not None
            # Convert postgresql:// to postgresql+asyncpg://
            if self.pg_dsn.startswith("postgresql://"):
                async_dsn = self.pg_dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
            else:
                async_dsn = self.pg_dsn
            return async_dsn
        elif self.db_type == "sqlite":
            # Ensure directory exists for SQLite
            sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite+aiosqlite:///{sqlite_path}"
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")

def _create_async_engine_from_config(config: DatabaseConfig, sqlite_path: Path):
    return create_async_engine(config.get_dsn(sqlite_path))


async def _create_tables(exp_id: str, config: DatabaseConfig, sqlite_path: Path):
    """Create tables using SQLAlchemy"""
    engine = _create_async_engine_from_config(config, sqlite_path)
    
    try:
        async with engine.begin() as conn:
            # Create experiment table if not exists
            await conn.run_sync(Base.metadata.create_all, tables=[Experiment.__table__])
            
            # Create other tables for specific experiment
            table_functions = {
                "agent_profile": agent_profile,
                "agent_status": agent_status,
                "agent_survey": agent_survey,
                "agent_dialog": agent_dialog,
                "global_prompt": global_prompt,
                "pending_dialog": pending_dialog,
                "pending_survey": pending_survey,
                "metric": metric,
                "task_result": task_result,
            }
            
            for table_type, table_func in table_functions.items():
                table_name = f"{TABLE_PREFIX}{exp_id.replace('-', '_')}_{table_type}"
                table_obj, _ = table_func(table_name)
                
                # Drop existing table if exists
                await conn.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
                
                # Create new table
                await conn.run_sync(table_obj.create, checkfirst=True)
                
                get_logger().debug(f"Created {config.db_type} table: {table_name}")
                
    finally:
        await engine.dispose()

class DatabaseWriter:
    def __init__(self, tenant_id: str, exp_id: str, config: DatabaseConfig, home_dir: str):
        """
        Initialize database writer.

        - **Args**:
            - `tenant_id` (str): Tenant ID.
            - `exp_id` (str): Experiment ID.
            - `config` (DatabaseConfig): Database configuration.
            - `home_dir` (str): Home directory. sqlite will be stored in home_dir/sqlite.db
        """
        self.tenant_id = tenant_id
        self.exp_id = exp_id
        self._config = config
        self._lock = asyncio.Lock()
        self._sqlite_path = Path(home_dir) / "sqlite.db"
        self._engine = _create_async_engine_from_config(config, sqlite_path=self._sqlite_path)
        self._async_session = async_sessionmaker(self._engine, expire_on_commit=False)
        
        # Setup storage path
        self._storage_path = Path(home_dir) / "exps" / tenant_id / exp_id
        self._storage_path.mkdir(parents=True, exist_ok=True)
        
        # Cache table objects
        self._tables = {}
        self._init_tables()

    async def init(self):
        """Initialize database tables"""
        await self._create_tables()

    def _init_tables(self):
        """Initialize table object cache"""
        table_functions = {
            "agent_profile": agent_profile,
            "agent_status": agent_status,
            "agent_survey": agent_survey,
            "agent_dialog": agent_dialog,
            "global_prompt": global_prompt,
            "pending_dialog": pending_dialog,
            "pending_survey": pending_survey,
            "metric": metric,
            "task_result": task_result,
        }
        
        for table_type, table_func in table_functions.items():
            table_name = f"{TABLE_PREFIX}{self.exp_id.replace('-', '_')}_{table_type}"
            table_obj, columns = table_func(table_name)
            self._tables[table_type] = {"table": table_obj, "columns": columns}

    async def _create_tables(self):
        """Create tables"""
        await _create_tables(self.exp_id, self._config, self._sqlite_path)

    def _get_insert_func(self):
        """Get insert function based on database type"""
        if self._config.db_type == "postgresql":
            return pg_insert
        elif self._config.db_type == "sqlite":
            return sqlite_insert
        else:
            raise ValueError(f"Unsupported database type: {self._config.db_type}")

    @property
    def exp_info_file(self):
        """Experiment info file path"""
        return self._storage_path / "experiment_info.yaml"

    @property
    def storage_path(self):
        """Storage path"""
        return self._storage_path

    # ==================== READ METHODS ====================

    async def read_dialogs(
        self, 
        day: Optional[int] = None, 
        speaker: Optional[str] = None, 
        dialog_type: Optional[int] = None,
        start_t: Optional[float] = None,
        end_t: Optional[float] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        order_by: str = "created_at",
        order_direction: str = "asc"
    ) -> List[Dict[str, Any]]:
        """
        Read dialog records with filtering and pagination.

        - **Args**:
            - `day` (Optional[int]): Filter by day.
            - `speaker` (Optional[str]): Filter by speaker.
            - `dialog_type` (Optional[int]): Filter by dialog type.
            - `start_t` (Optional[float]): Filter by start time.
            - `end_t` (Optional[float]): Filter by end time.
            - `limit` (Optional[int]): Limit number of records.
            - `offset` (Optional[int]): Offset for pagination.
            - `order_by` (str): Column to order by.
            - `order_direction` (str): Order direction ('asc' or 'desc').

        - **Returns**:
            - `List[Dict[str, Any]]`: List of dialog records.
        """
        table_obj = self._tables["agent_dialog"]["table"]
        
        async with self._async_session() as session:
            try:
                # Build query
                stmt = select(table_obj)
                
                # Add filters
                conditions = []
                if day is not None:
                    conditions.append(table_obj.c.day == day)
                if speaker is not None:
                    conditions.append(table_obj.c.speaker == speaker)
                if dialog_type is not None:
                    conditions.append(table_obj.c.type == dialog_type)
                if start_t is not None:
                    conditions.append(table_obj.c.t >= start_t)
                if end_t is not None:
                    conditions.append(table_obj.c.t <= end_t)
                
                if conditions:
                    stmt = stmt.where(and_(*conditions))
                
                # Add ordering
                order_column = getattr(table_obj.c, order_by, table_obj.c.created_at)
                if order_direction.lower() == "desc":
                    stmt = stmt.order_by(desc(order_column))
                else:
                    stmt = stmt.order_by(asc(order_column))
                
                # Add pagination
                if limit is not None:
                    stmt = stmt.limit(limit)
                if offset is not None:
                    stmt = stmt.offset(offset)
                
                result = await session.execute(stmt)
                rows = result.fetchall()
                
                # Convert to list of dictionaries
                return [dict(row._mapping) for row in rows]
                
            except Exception as e:
                get_logger().error(f"Error reading dialogs from {self._config.db_type}: {e}")
                raise

    async def read_statuses(
        self,
        day: Optional[int] = None,
        agent_id: Optional[int] = None,
        start_t: Optional[float] = None,
        end_t: Optional[float] = None,
        action: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        order_by: str = "created_at",
        order_direction: str = "asc"
    ) -> List[Dict[str, Any]]:
        """
        Read status records with filtering and pagination.

        - **Args**:
            - `day` (Optional[int]): Filter by day.
            - `agent_id` (Optional[int]): Filter by agent ID.
            - `start_t` (Optional[float]): Filter by start time.
            - `end_t` (Optional[float]): Filter by end time.
            - `action` (Optional[str]): Filter by action.
            - `limit` (Optional[int]): Limit number of records.
            - `offset` (Optional[int]): Offset for pagination.
            - `order_by` (str): Column to order by.
            - `order_direction` (str): Order direction ('asc' or 'desc').

        - **Returns**:
            - `List[Dict[str, Any]]`: List of status records.
        """
        table_obj = self._tables["agent_status"]["table"]
        
        async with self._async_session() as session:
            try:
                stmt = select(table_obj)
                
                conditions = []
                if day is not None:
                    conditions.append(table_obj.c.day == day)
                if agent_id is not None:
                    conditions.append(table_obj.c.id == agent_id)
                if start_t is not None:
                    conditions.append(table_obj.c.t >= start_t)
                if end_t is not None:
                    conditions.append(table_obj.c.t <= end_t)
                if action is not None:
                    conditions.append(table_obj.c.action == action)
                
                if conditions:
                    stmt = stmt.where(and_(*conditions))
                
                order_column = getattr(table_obj.c, order_by, table_obj.c.created_at)
                if order_direction.lower() == "desc":
                    stmt = stmt.order_by(desc(order_column))
                else:
                    stmt = stmt.order_by(asc(order_column))
                
                if limit is not None:
                    stmt = stmt.limit(limit)
                if offset is not None:
                    stmt = stmt.offset(offset)
                
                result = await session.execute(stmt)
                rows = result.fetchall()
                
                return [dict(row._mapping) for row in rows]
                
            except Exception as e:
                get_logger().error(f"Error reading statuses from {self._config.db_type}: {e}")
                raise

    async def read_surveys(
        self,
        day: Optional[int] = None,
        survey_id: Optional[str] = None,
        start_t: Optional[float] = None,
        end_t: Optional[float] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        order_by: str = "created_at",
        order_direction: str = "asc"
    ) -> List[Dict[str, Any]]:
        """
        Read survey records with filtering and pagination.

        - **Args**:
            - `day` (Optional[int]): Filter by day.
            - `survey_id` (Optional[str]): Filter by survey ID.
            - `start_t` (Optional[float]): Filter by start time.
            - `end_t` (Optional[float]): Filter by end time.
            - `limit` (Optional[int]): Limit number of records.
            - `offset` (Optional[int]): Offset for pagination.
            - `order_by` (str): Column to order by.
            - `order_direction` (str): Order direction ('asc' or 'desc').

        - **Returns**:
            - `List[Dict[str, Any]]`: List of survey records.
        """
        table_obj = self._tables["agent_survey"]["table"]
        
        async with self._async_session() as session:
            try:
                stmt = select(table_obj)
                
                conditions = []
                if day is not None:
                    conditions.append(table_obj.c.day == day)
                if survey_id is not None:
                    conditions.append(table_obj.c.survey_id == uuid.UUID(survey_id))
                if start_t is not None:
                    conditions.append(table_obj.c.t >= start_t)
                if end_t is not None:
                    conditions.append(table_obj.c.t <= end_t)
                
                if conditions:
                    stmt = stmt.where(and_(*conditions))
                
                order_column = getattr(table_obj.c, order_by, table_obj.c.created_at)
                if order_direction.lower() == "desc":
                    stmt = stmt.order_by(desc(order_column))
                else:
                    stmt = stmt.order_by(asc(order_column))
                
                if limit is not None:
                    stmt = stmt.limit(limit)
                if offset is not None:
                    stmt = stmt.offset(offset)
                
                result = await session.execute(stmt)
                rows = result.fetchall()
                
                # Convert UUID to string for JSON serialization
                results = []
                for row in rows:
                    row_dict = dict(row._mapping)
                    row_dict["survey_id"] = str(row_dict["survey_id"])
                    results.append(row_dict)
                
                return results
                
            except Exception as e:
                get_logger().error(f"Error reading surveys from {self._config.db_type}: {e}")
                raise

    async def read_profiles(self) -> List[Dict[str, Any]]:
        """
        Read all agent profiles.

        - **Returns**:
            - `List[Dict[str, Any]]`: List of agent profile records.
        """
        table_obj = self._tables["agent_profile"]["table"]
        
        async with self._async_session() as session:
            try:
                stmt = select(table_obj)
                result = await session.execute(stmt)
                rows = result.fetchall()
                
                return [dict(row._mapping) for row in rows]
                
            except Exception as e:
                get_logger().error(f"Error reading profiles from {self._config.db_type}: {e}")
                raise

    async def read_global_prompts(
        self,
        day: Optional[int] = None,
        start_t: Optional[float] = None,
        end_t: Optional[float] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        order_by: str = "created_at",
        order_direction: str = "asc"
    ) -> List[Dict[str, Any]]:
        """
        Read global prompt records with filtering and pagination.

        - **Args**:
            - `day` (Optional[int]): Filter by day.
            - `start_t` (Optional[float]): Filter by start time.
            - `end_t` (Optional[float]): Filter by end time.
            - `limit` (Optional[int]): Limit number of records.
            - `offset` (Optional[int]): Offset for pagination.
            - `order_by` (str): Column to order by.
            - `order_direction` (str): Order direction ('asc' or 'desc').

        - **Returns**:
            - `List[Dict[str, Any]]`: List of global prompt records.
        """
        table_obj = self._tables["global_prompt"]["table"]
        
        async with self._async_session() as session:
            try:
                stmt = select(table_obj)
                
                conditions = []
                if day is not None:
                    conditions.append(table_obj.c.day == day)
                if start_t is not None:
                    conditions.append(table_obj.c.t >= start_t)
                if end_t is not None:
                    conditions.append(table_obj.c.t <= end_t)
                
                if conditions:
                    stmt = stmt.where(and_(*conditions))
                
                order_column = getattr(table_obj.c, order_by, table_obj.c.created_at)
                if order_direction.lower() == "desc":
                    stmt = stmt.order_by(desc(order_column))
                else:
                    stmt = stmt.order_by(asc(order_column))
                
                if limit is not None:
                    stmt = stmt.limit(limit)
                if offset is not None:
                    stmt = stmt.offset(offset)
                
                result = await session.execute(stmt)
                rows = result.fetchall()
                
                return [dict(row._mapping) for row in rows]
                
            except Exception as e:
                get_logger().error(f"Error reading global prompts from {self._config.db_type}: {e}")
                raise

    async def read_task_results(
        self,
        agent_id: Optional[int] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        order_by: str = "created_at",
        order_direction: str = "asc"
    ) -> List[Dict[str, Any]]:
        """
        Read task result records with filtering and pagination.

        - **Args**:
            - `agent_id` (Optional[int]): Filter by agent ID.
            - `limit` (Optional[int]): Limit number of records.
            - `offset` (Optional[int]): Offset for pagination.
            - `order_by` (str): Column to order by.
            - `order_direction` (str): Order direction ('asc' or 'desc').

        - **Returns**:
            - `List[Dict[str, Any]]`: List of task result records.
        """
        table_obj = self._tables["task_result"]["table"]
        
        async with self._async_session() as session:
            try:
                stmt = select(table_obj)
                
                if agent_id is not None:
                    stmt = stmt.where(table_obj.c.agent_id == agent_id)
                
                order_column = getattr(table_obj.c, order_by, table_obj.c.created_at)
                if order_direction.lower() == "desc":
                    stmt = stmt.order_by(desc(order_column))
                else:
                    stmt = stmt.order_by(asc(order_column))
                
                if limit is not None:
                    stmt = stmt.limit(limit)
                if offset is not None:
                    stmt = stmt.offset(offset)
                
                result = await session.execute(stmt)
                rows = result.fetchall()
                
                return [dict(row._mapping) for row in rows]
                
            except Exception as e:
                get_logger().error(f"Error reading task results from {self._config.db_type}: {e}")
                raise

    async def read_metrics(
        self,
        key: Optional[str] = None,
        step: Optional[int] = None,
        start_step: Optional[int] = None,
        end_step: Optional[int] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        order_by: str = "step",
        order_direction: str = "asc"
    ) -> List[Dict[str, Any]]:
        """
        Read metric records with filtering and pagination.

        - **Args**:
            - `key` (Optional[str]): Filter by metric key.
            - `step` (Optional[int]): Filter by specific step.
            - `start_step` (Optional[int]): Filter by start step.
            - `end_step` (Optional[int]): Filter by end step.
            - `limit` (Optional[int]): Limit number of records.
            - `offset` (Optional[int]): Offset for pagination.
            - `order_by` (str): Column to order by.
            - `order_direction` (str): Order direction ('asc' or 'desc').

        - **Returns**:
            - `List[Dict[str, Any]]`: List of metric records.
        """
        table_obj = self._tables["metric"]["table"]
        
        async with self._async_session() as session:
            try:
                stmt = select(table_obj)
                
                conditions = []
                if key is not None:
                    conditions.append(table_obj.c.key == key)
                if step is not None:
                    conditions.append(table_obj.c.step == step)
                if start_step is not None:
                    conditions.append(table_obj.c.step >= start_step)
                if end_step is not None:
                    conditions.append(table_obj.c.step <= end_step)
                
                if conditions:
                    stmt = stmt.where(and_(*conditions))
                
                order_column = getattr(table_obj.c, order_by, table_obj.c.step)
                if order_direction.lower() == "desc":
                    stmt = stmt.order_by(desc(order_column))
                else:
                    stmt = stmt.order_by(asc(order_column))
                
                if limit is not None:
                    stmt = stmt.limit(limit)
                if offset is not None:
                    stmt = stmt.offset(offset)
                
                result = await session.execute(stmt)
                rows = result.fetchall()
                
                return [dict(row._mapping) for row in rows]
                
            except Exception as e:
                get_logger().error(f"Error reading metrics from {self._config.db_type}: {e}")
                raise

    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics for the experiment.

        - **Returns**:
            - `Dict[str, Any]`: Statistics including counts, time ranges, and summaries.
        """
        async with self._async_session() as session:
            try:
                stats = {}
                
                # Get counts for each table
                for table_type in self._tables.keys():
                    table_obj = self._tables[table_type]["table"]
                    count_stmt = select(table_obj).select_from(table_obj)
                    result = await session.execute(count_stmt)
                    stats[f"{table_type}_count"] = len(result.fetchall())
                
                # Get time range for dialogs
                dialog_table = self._tables["agent_dialog"]["table"]
                time_stmt = select(
                    dialog_table.c.day,
                    dialog_table.c.t,
                    dialog_table.c.created_at
                ).order_by(asc(dialog_table.c.created_at))
                result = await session.execute(time_stmt)
                dialog_rows = result.fetchall()
                
                if dialog_rows:
                    stats["dialog_time_range"] = {
                        "first_day": dialog_rows[0].day,
                        "last_day": dialog_rows[-1].day,
                        "first_time": dialog_rows[0].t,
                        "last_time": dialog_rows[-1].t,
                        "first_created": dialog_rows[0].created_at.isoformat(),
                        "last_created": dialog_rows[-1].created_at.isoformat(),
                    }
                
                # Get unique speakers
                speaker_stmt = select(dialog_table.c.speaker).distinct()
                result = await session.execute(speaker_stmt)
                stats["unique_speakers"] = [row.speaker for row in result.fetchall()]
                
                # Get dialog type distribution
                type_stmt = select(dialog_table.c.type)
                result = await session.execute(type_stmt)
                type_counts = {}
                for row in result.fetchall():
                    type_counts[row.type] = type_counts.get(row.type, 0) + 1
                stats["dialog_type_distribution"] = type_counts
                
                # Get unique agent IDs from status
                status_table = self._tables["agent_status"]["table"]
                agent_stmt = select(status_table.c.id).distinct()
                result = await session.execute(agent_stmt)
                stats["unique_agents"] = [row.id for row in result.fetchall()]
                
                return stats
                
            except Exception as e:
                get_logger().error(f"Error getting statistics from {self._config.db_type}: {e}")
                raise

    # ==================== WRITE METHODS ====================

    @lock_decorator
    async def write_dialogs(self, rows: list[StorageDialog]):
        table_obj = self._tables["agent_dialog"]["table"]
        insert_func = self._get_insert_func()
        
        async with self._async_session() as session:
            try:
                # Batch insert data
                data = []
                for row in rows:
                    data.append(
                        {
                            "id": row.id,
                            "day": row.day,
                            "t": row.t,
                            "type": row.type,
                            "speaker": row.speaker,
                            "content": row.content,
                            "created_at": row.created_at,
                        }
                    )
                
                stmt = insert_func(table_obj).values(data)
                await session.execute(stmt)
                await session.commit()
                
                get_logger().debug(f"Inserted {len(rows)} dialog records to {self._config.db_type}")
                
            except Exception as e:
                await session.rollback()
                get_logger().error(f"Error writing dialogs to {self._config.db_type}: {e}")
                raise

    @lock_decorator
    async def write_statuses(self, rows: list[StorageStatus]):
        table_obj = self._tables["agent_status"]["table"]
        insert_func = self._get_insert_func()
        
        async with self._async_session() as session:
            try:
                data = []
                for row in rows:
                    data.append(
                        {
                            "id": row.id,
                            "day": row.day,
                            "t": row.t,
                            "lng": row.lng,
                            "lat": row.lat,
                            "parent_id": row.parent_id,
                            "action": row.action,
                            "status": row.status,
                            "created_at": row.created_at,
                        }
                    )
                
                stmt = insert_func(table_obj).values(data)
                await session.execute(stmt)
                await session.commit()
                
                get_logger().debug(f"Inserted {len(rows)} status records to {self._config.db_type}")
                
            except Exception as e:
                await session.rollback()
                get_logger().error(f"Error writing statuses to {self._config.db_type}: {e}")
                raise

    @lock_decorator
    async def write_profiles(self, rows: list[StorageProfile]):
        table_obj = self._tables["agent_profile"]["table"]
        insert_func = self._get_insert_func()
        
        async with self._async_session() as session:
            try:
                data = []
                for row in rows:
                    data.append(
                        {
                            "id": row.id,
                            "name": row.name,
                            "profile": row.profile,
                        }
                    )
                
                stmt = insert_func(table_obj).values(data)
                await session.execute(stmt)
                await session.commit()
                
                get_logger().debug(f"Inserted {len(rows)} profile records to {self._config.db_type}")
                
            except Exception as e:
                await session.rollback()
                get_logger().error(f"Error writing profiles to {self._config.db_type}: {e}")
                raise

    @lock_decorator
    async def write_surveys(self, rows: list[StorageSurvey]):
        table_obj = self._tables["agent_survey"]["table"]
        insert_func = self._get_insert_func()
        
        async with self._async_session() as session:
            try:
                data = []
                for row in rows:
                    data.append(
                        {
                            "id": row.id,
                            "day": row.day,
                            "t": row.t,
                            "survey_id": row.survey_id,
                            "result": row.result,
                            "created_at": row.created_at,
                        }
                    )
                
                stmt = insert_func(table_obj).values(data)
                await session.execute(stmt)
                await session.commit()
                
                get_logger().debug(f"Inserted {len(rows)} survey records to {self._config.db_type}")
                
            except Exception as e:
                await session.rollback()
                get_logger().error(f"Error writing surveys to {self._config.db_type}: {e}")
                raise

    @lock_decorator
    async def write_global_prompt(self, prompt_info: StorageGlobalPrompt):
        table_obj = self._tables["global_prompt"]["table"]
        insert_func = self._get_insert_func()
        
        async with self._async_session() as session:
            try:
                data = {
                    "day": prompt_info.day,
                    "t": prompt_info.t,
                    "prompt": prompt_info.prompt,
                    "created_at": prompt_info.created_at,
                }
                
                stmt = insert_func(table_obj).values([data])
                await session.execute(stmt)
                await session.commit()
                
                get_logger().debug(f"Inserted global prompt record to {self._config.db_type}")
                
            except Exception as e:
                await session.rollback()
                get_logger().error(f"Error writing global prompt to {self._config.db_type}: {e}")
                raise

    @lock_decorator
    async def write_task_result(self, rows: list[StorageTaskResult]):
        table_obj = self._tables["task_result"]["table"]
        insert_func = self._get_insert_func()
        
        async with self._async_session() as session:
            try:
                data = []
                for row in rows:
                    data.append(
                        {
                            "id": row.id,
                            "agent_id": row.agent_id,
                            "context": row.context,
                            "ground_truth": row.ground_truth,
                            "result": row.result,
                            "created_at": row.created_at,
                        }
                    )
                
                stmt = insert_func(table_obj).values(data)
                await session.execute(stmt)
                await session.commit()

                get_logger().debug(f"Inserted {len(rows)} task result records to {self._config.db_type}")
                
            except Exception as e:
                await session.rollback()
                get_logger().error(f"Error writing task results to {self._config.db_type}: {e}")
                raise

    @lock_decorator
    async def log_metric(self, metrics: list[tuple[str, float, int]]):
        """
        Batch insert metric data.

        Args:
            metrics: List of tuples (key, value, step)
        """
        if len(metrics) == 0:
            return
        table_obj = self._tables["metric"]["table"]
        insert_func = self._get_insert_func()
        
        async with self._async_session() as session:
            try:
                data = [
                    {
                        "key": key,
                        "value": value,
                        "step": step,
                        "created_at": datetime.now(),
                    }
                    for key, value, step in metrics
                ]
                stmt = insert_func(table_obj).values(data)
                await session.execute(stmt)
                await session.commit()
                
                get_logger().debug(f"Batch inserted {len(metrics)} metric records to {self._config.db_type}")
            except Exception as e:
                await session.rollback()
                get_logger().error(f"Error batch writing metrics to {self._config.db_type}: {e}")
                raise

    @lock_decorator
    async def update_exp_info(self, exp_info: StorageExpInfo):
        insert_func = self._get_insert_func()

        # save to local
        with open(self.exp_info_file, "w") as f:
            yaml.dump(exp_info.model_dump(), f)

        async with self._async_session() as session:
            try:
                # Use SQLAlchemy upsert operation
                stmt = insert_func(Experiment).values(
                    tenant_id=exp_info.tenant_id,
                    id=uuid.UUID(self.exp_id),
                    name=exp_info.name,
                    num_day=exp_info.num_day,
                    status=exp_info.status,
                    cur_day=exp_info.cur_day,
                    cur_t=exp_info.cur_t,
                    config=exp_info.config,
                    error=exp_info.error,
                    input_tokens=exp_info.input_tokens,
                    output_tokens=exp_info.output_tokens,
                    created_at=exp_info.created_at,
                    updated_at=exp_info.updated_at,
                )
                
                # Database-specific upsert operation
                if self._config.db_type == "postgresql":
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["tenant_id", "id"],
                        set_=dict(
                            name=stmt.excluded.name,
                            num_day=stmt.excluded.num_day,
                            status=stmt.excluded.status,
                            cur_day=stmt.excluded.cur_day,
                            cur_t=stmt.excluded.cur_t,
                            config=stmt.excluded.config,
                            error=stmt.excluded.error,
                            input_tokens=stmt.excluded.input_tokens,
                            output_tokens=stmt.excluded.output_tokens,
                            updated_at=stmt.excluded.updated_at,
                        ),
                    )
                elif self._config.db_type == "sqlite":
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["tenant_id", "id"],
                        set_=dict(
                            name=stmt.excluded.name,
                            num_day=stmt.excluded.num_day,
                            status=stmt.excluded.status,
                            cur_day=stmt.excluded.cur_day,
                            cur_t=stmt.excluded.cur_t,
                            config=stmt.excluded.config,
                            error=stmt.excluded.error,
                            input_tokens=stmt.excluded.input_tokens,
                            output_tokens=stmt.excluded.output_tokens,
                            updated_at=stmt.excluded.updated_at,
                        )
                    )
                
                await session.execute(stmt)
                await session.commit()
                
                get_logger().debug(f"Updated experiment info for {self.exp_id} in {self._config.db_type}")
                
            except Exception as e:
                await session.rollback()
                get_logger().error(f"Error updating experiment info in {self._config.db_type}: {e}")
                raise

    async def fetch_pending_dialogs(self):
        """
        Fetch all unprocessed pending dialogs from the database.

        - **Returns**:
            - `list[StoragePendingDialog]`: List of pending dialogs.
        """
        table_obj = self._tables["pending_dialog"]["table"]
        
        async with self._async_session() as session:
            try:
                stmt = select(table_obj).where(table_obj.c.processed == False)
                result = await session.execute(stmt)
                rows = result.fetchall()
                
                return [StoragePendingDialog(**row._asdict()) for row in rows]
                
            except Exception as e:
                get_logger().error(f"Error fetching pending dialogs from {self._config.db_type}: {e}")
                raise

    @lock_decorator
    async def mark_dialogs_as_processed(self, pending_ids: list[int]):
        """
        Mark specified dialogs as processed.

        - **Args**:
            - `pending_ids` (list[int]): List of pending dialog IDs to mark as processed.
        """
        if not pending_ids:
            return

        table_obj = self._tables["pending_dialog"]["table"]
        
        async with self._async_session() as session:
            try:
                stmt = (
                    update(table_obj)
                    .where(table_obj.c.id.in_(pending_ids))
                    .values(processed=True)
                )
                
                await session.execute(stmt)
                await session.commit()
                
                get_logger().debug(f"Marked {len(pending_ids)} dialogs as processed in {self._config.db_type}")
                
            except Exception as e:
                await session.rollback()
                get_logger().error(f"Error marking dialogs as processed in {self._config.db_type}: {e}")
                raise

    async def fetch_pending_surveys(self):
        """
        Fetch all unprocessed pending surveys from the database.

        - **Returns**:
            - `list[StoragePendingSurvey]`: List of pending surveys.
        """
        table_obj = self._tables["pending_survey"]["table"]
        
        async with self._async_session() as session:
            try:
                stmt = select(table_obj).where(table_obj.c.processed == False)
                result = await session.execute(stmt)
                rows = result.fetchall()
                
                results = []
                for row in rows:
                    row_dict = row._asdict()
                    row_dict["survey_id"] = str(row_dict["survey_id"])
                    results.append(StoragePendingSurvey(**row_dict))
                
                return results
                
            except Exception as e:
                get_logger().error(f"Error fetching pending surveys from {self._config.db_type}: {e}")
                raise

    @lock_decorator
    async def mark_surveys_as_processed(self, pending_ids: list[int]):
        """
        Mark specified surveys as processed.

        - **Args**:
            - `pending_ids` (list[int]): List of pending survey IDs to mark as processed.
        """
        if not pending_ids:
            return

        table_obj = self._tables["pending_survey"]["table"]
        
        async with self._async_session() as session:
            try:
                stmt = (
                    update(table_obj)
                    .where(table_obj.c.id.in_(pending_ids))
                    .values(processed=True)
                )
                
                await session.execute(stmt)
                await session.commit()
                
                get_logger().debug(f"Marked {len(pending_ids)} surveys as processed in {self._config.db_type}")
                
            except Exception as e:
                await session.rollback()
                get_logger().error(f"Error marking surveys as processed in {self._config.db_type}: {e}")
                raise

    async def close(self):
        """Close database connection"""
        if hasattr(self, "_engine"):
            await self._engine.dispose()

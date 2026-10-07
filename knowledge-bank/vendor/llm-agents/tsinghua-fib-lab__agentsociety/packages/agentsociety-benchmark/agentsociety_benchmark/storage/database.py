import asyncio
from pathlib import Path
import uuid

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from agentsociety.storage import DatabaseConfig
from agentsociety.utils.decorators import lock_decorator
from .model import (
    Benchmark,
)
from ._base import Base
from .type import (
    StorageBenchmark,
)

__all__ = ["DatabaseWriter", "DatabaseConfig"]


def _create_async_engine_from_config(config: DatabaseConfig, sqlite_path: Path):
    return create_async_engine(config.get_dsn(sqlite_path))


async def _create_tables(config: DatabaseConfig, sqlite_path: Path):
    """Create tables using SQLAlchemy"""
    engine = _create_async_engine_from_config(config, sqlite_path)
    
    try:
        async with engine.begin() as conn:
            # Create benchmark table if not exists
            await conn.run_sync(Base.metadata.create_all, tables=[Benchmark.__table__])
                
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

    async def init(self):
        """Initialize database tables"""
        await self._create_tables()

    async def _create_tables(self):
        """Create tables"""
        await _create_tables(self._config, self._sqlite_path)

    def _get_insert_func(self):
        """Get insert function based on database type"""
        if self._config.db_type == "postgresql":
            return pg_insert
        elif self._config.db_type == "sqlite":
            return sqlite_insert
        else:
            raise ValueError(f"Unsupported database type: {self._config.db_type}")

    @lock_decorator
    async def update_benchmark_info(self, benchmark_info: StorageBenchmark):
        insert_func = self._get_insert_func()
        
        async with self._async_session() as session:
            try:
                # Use SQLAlchemy upsert operation
                stmt = insert_func(Benchmark).values(
                    tenant_id=benchmark_info.tenant_id,
                    id=uuid.UUID(self.exp_id),
                    benchmark_name=benchmark_info.benchmark_name,
                    llm=benchmark_info.llm,
                    agent=benchmark_info.agent,
                    status=benchmark_info.status,
                    result_info=benchmark_info.result_info,
                    final_score=benchmark_info.final_score,
                    config=benchmark_info.config,
                    error=benchmark_info.error,
                    official_validated=benchmark_info.official_validated,
                    agent_filename=benchmark_info.agent_filename,
                    result_filename=benchmark_info.result_filename,
                    created_at=benchmark_info.created_at,
                    updated_at=benchmark_info.updated_at,
                )
                
                # Database-specific upsert operation
                if self._config.db_type == "postgresql":
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["tenant_id", "id"],
                        set_=dict(
                            benchmark_name=stmt.excluded.benchmark_name,
                            llm=stmt.excluded.llm,
                            agent=stmt.excluded.agent,
                            status=stmt.excluded.status,
                            result_info=stmt.excluded.result_info,
                            final_score=stmt.excluded.final_score,
                            config=stmt.excluded.config,
                            error=stmt.excluded.error,
                            official_validated=stmt.excluded.official_validated,
                            agent_filename=stmt.excluded.agent_filename,
                            result_filename=stmt.excluded.result_filename,
                            updated_at=stmt.excluded.updated_at,
                        ),
                    )
                elif self._config.db_type == "sqlite":
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["tenant_id", "id"],
                        set_=dict(
                            benchmark_name=stmt.excluded.benchmark_name,
                            llm=stmt.excluded.llm,
                            agent=stmt.excluded.agent,
                            status=stmt.excluded.status,
                            result_info=stmt.excluded.result_info,
                            final_score=stmt.excluded.final_score,
                            config=stmt.excluded.config,
                            error=stmt.excluded.error,
                            official_validated=stmt.excluded.official_validated,
                            agent_filename=stmt.excluded.agent_filename,
                            result_filename=stmt.excluded.result_filename,
                            updated_at=stmt.excluded.updated_at,
                        )
                    )
                
                await session.execute(stmt)
                await session.commit()                
            except Exception:
                await session.rollback()
                raise

    async def close(self):
        """Close database connection"""
        if hasattr(self, "_engine"):
            await self._engine.dispose()
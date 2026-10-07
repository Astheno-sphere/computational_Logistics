import enum
from pydantic import BaseModel
from datetime import datetime

__all__ = [
    "StorageBenchmark",
]

class BenchmarkStatus(enum.IntEnum):
    """Benchmark status"""

    NOT_STARTED = 0  # The benchmark is not started
    RUNNING = 1  # The benchmark is running
    FINISHED = 2  #  The benchmark is finished
    EVALUATED = 3  # The benchmark has been evaluated
    ERROR = 4  # The benchmark has error and stopped


class StorageBenchmark(BaseModel):
    tenant_id: str
    id: str
    benchmark_name: str
    llm: str
    agent: str
    agent_filename: str
    result_filename: str
    status: BenchmarkStatus
    result_info: str
    final_score: float
    config: str
    error: str
    official_validated: bool
    created_at: datetime
    updated_at: datetime
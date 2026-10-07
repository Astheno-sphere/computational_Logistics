from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from agentsociety.configs import LLMConfig, EnvConfig
from agentsociety.storage.database import DatabaseConfig

__all__ = ["BenchmarkConfig"]

class BenchmarkConfig(BaseModel):
    """Configuration for the benchmark"""

    llm: Optional[List[LLMConfig]] = Field(default=None, min_length=1)
    """List of LLM configurations, if not provided, you can only use evaluation function"""

    env: EnvConfig = EnvConfig(
        db=DatabaseConfig(
            enabled=True,
            db_type="sqlite",
            pg_dsn=None,
        ),
        home_dir=".agentsociety-benchmark/agentsociety_data"
    )
    """Environment configuration"""

    mode: Literal["test", "inference"] = Field(default="test")
    """Execution mode: 'test' runs full pipeline including evaluation, 'inference' skips evaluation and saves results"""
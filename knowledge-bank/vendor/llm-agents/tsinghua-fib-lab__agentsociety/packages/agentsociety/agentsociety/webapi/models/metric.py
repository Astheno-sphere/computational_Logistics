from pydantic import BaseModel

from ...storage import metric

__all__ = ["metric", "ApiMetric"]

# API Models

class ApiMetric(BaseModel):
    """Metric model for API"""

    key: str
    """Metric key"""
    value: float
    """Metric value"""
    step: int
    """Step number"""

    class Config:
        from_attributes = True

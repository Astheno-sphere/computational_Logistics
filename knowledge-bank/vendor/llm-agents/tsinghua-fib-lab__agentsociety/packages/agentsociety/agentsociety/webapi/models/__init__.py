from typing import Generic, List, TypeVar

from pydantic import BaseModel, Field

__all__ = ["ApiResponseWrapper"]

T = TypeVar("T")


class ApiResponseWrapper(BaseModel, Generic[T]):
    """API Response Wrapper"""

    data: T = Field(..., description="Response Data")


# 分页响应模型
class ApiPaginatedResponseWrapper(BaseModel, Generic[T]):
    """分页响应模型"""

    total: int = Field(..., description="总记录数")
    data: List[T] = Field(..., description="数据项列表")

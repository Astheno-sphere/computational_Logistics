"""
模拟器gRPC接入客户端
Simulator gRPC access client
"""

from .client import CityClient
from .person_service import PersonService

__all__ = [
    "CityClient",
    "PersonService",
]

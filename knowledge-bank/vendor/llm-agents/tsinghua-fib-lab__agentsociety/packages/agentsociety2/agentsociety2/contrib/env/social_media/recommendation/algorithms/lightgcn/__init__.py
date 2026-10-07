"""
LightGCN 算法模块
"""

from .config import LightGCNConfig
from .model import LightGCNRecommender

__all__ = [
    "LightGCNConfig",
    "LightGCNRecommender",
]

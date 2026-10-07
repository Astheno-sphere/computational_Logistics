"""
DeepFM 算法模块
"""

from .config import DeepFMConfig
from .model import DeepFMRecommender

__all__ = [
    "DeepFMConfig",
    "DeepFMRecommender",
]

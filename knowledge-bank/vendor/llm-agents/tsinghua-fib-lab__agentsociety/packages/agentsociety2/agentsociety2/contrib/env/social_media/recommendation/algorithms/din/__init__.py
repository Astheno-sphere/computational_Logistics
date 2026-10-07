"""
DIN (Deep Interest Network) 算法模块
"""

from .config import DINConfig
from .model import DINRecommender

__all__ = [
    "DINConfig",
    "DINRecommender",
]

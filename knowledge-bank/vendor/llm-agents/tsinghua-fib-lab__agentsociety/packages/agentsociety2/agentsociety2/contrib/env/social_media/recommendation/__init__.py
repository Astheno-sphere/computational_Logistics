"""
Recommendation Module for SocialMediaSpace

- RecommenderAlgorithm: 统一的算法接口
- RatingMatrix: 统一的数据格式
- MFRecommender: MF算法实现
- RecommendationService: 核心推荐服务
- IncrementalTrainer: 增量训练器 (可选)
"""

from .algorithms.core import RatingMatrix, RecommenderAlgorithm
from .algorithms.mf import MFConfig, MFRecommender
from .models import FeedCache, Item, Rating, RecommendationHistory, UserPreference
from .service import RecommendationService, ServiceConfig
from .storage import RecommendationStorageManager
from .trainer import IncrementalTrainer, TrainerConfig

__all__ = [
    "FeedCache",
    "IncrementalTrainer",
    # 数据模型
    "Item",
    "MFConfig",
    "MFRecommender",
    "Rating",
    "RatingMatrix",
    "RecommendationHistory",
    "RecommendationService",
    "RecommendationStorageManager",
    "RecommenderAlgorithm",
    "ServiceConfig",
    "TrainerConfig",
    "UserPreference",
]

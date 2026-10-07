"""
核心数据结构和算法基类

- RatingMatrix: 评分矩阵表示
- RecommenderAlgorithm: 算法接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import sparse

from ..models import Rating


@dataclass
class RatingMatrix:
    """
    统一的评分矩阵表示

    提供多种数据格式转换,供不同算法使用:
    - NumPy arrays: 原始数据
    - pandas DataFrame: MF等算法需要
    - SciPy sparse matrix: 协同过滤等算法需要
    """

    user_ids: np.ndarray  # [N] 用户ID数组
    item_ids: np.ndarray  # [N] 物品ID数组
    ratings: np.ndarray  # [N] 评分值数组
    user_map: dict[int, int]  # 原始用户ID → 内部索引
    item_map: dict[int, int]  # 原始物品ID → 内部索引

    @classmethod
    def from_ratings(cls, ratings: list[Rating]) -> "RatingMatrix":
        """
        从 Rating 列表构建 RatingMatrix

        :param ratings: Rating 对象列表

        :returns: RatingMatrix 实例
        """
        if not ratings:
            raise ValueError("评分列表不能为空")

        # 提取数据
        user_ids = np.array([r.user_id for r in ratings])
        item_ids = np.array([r.item_id for r in ratings])
        rating_values = np.array([r.rating for r in ratings])

        # 构建映射 (原始ID → 内部索引)
        unique_users = np.unique(user_ids)
        unique_items = np.unique(item_ids)

        user_map = {uid: idx for idx, uid in enumerate(unique_users)}
        item_map = {iid: idx for idx, iid in enumerate(unique_items)}

        return cls(
            user_ids=user_ids,
            item_ids=item_ids,
            ratings=rating_values,
            user_map=user_map,
            item_map=item_map,
        )

    def to_dataframe(self) -> pd.DataFrame:
        """
        转换为 pandas DataFrame (pivot table 格式)

        用于 MF 等需要矩阵格式的算法

        :returns: DataFrame with users as rows, items as columns
        """
        df = pd.DataFrame(
            {"userId": self.user_ids, "itemId": self.item_ids, "rating": self.ratings}
        )

        return df.pivot_table(
            values="rating", index="userId", columns="itemId", fill_value=np.nan
        )

    def to_sparse(self) -> sparse.csr_matrix:
        """
        转换为稀疏矩阵 (CSR 格式)

        用于协同过滤等需要稀疏表示的算法

        :returns: scipy.sparse.csr_matrix
        """
        n_users = len(self.user_map)
        n_items = len(self.item_map)

        # 将原始ID映射到索引
        row_indices = np.array([self.user_map[uid] for uid in self.user_ids])
        col_indices = np.array([self.item_map[iid] for iid in self.item_ids])

        return sparse.csr_matrix(
            (self.ratings, (row_indices, col_indices)), shape=(n_users, n_items)
        )

    def get_user_count(self) -> int:
        """获取用户数量"""
        return len(self.user_map)

    def get_item_count(self) -> int:
        """获取物品数量"""
        return len(self.item_map)

    def get_rating_count(self) -> int:
        """获取评分数量"""
        return len(self.ratings)

    def __str__(self) -> str:
        return (
            f"RatingMatrix("
            f"users={self.get_user_count()}, "
            f"items={self.get_item_count()}, "
            f"ratings={self.get_rating_count()})"
        )


class RecommenderAlgorithm(ABC):
    """
    推荐算法统一接口

    - 只负责推荐逻辑，异步由服务层处理
    - 可选功能: save/load 不是必需的
    """

    @abstractmethod
    def fit(self, data: RatingMatrix) -> None:
        """
        训练模型

        :param data: 评分矩阵
        """

    @abstractmethod
    def predict(self, user_id: int, item_id: int) -> float:
        """
        预测单个用户对物品的评分

        :param user_id: 用户ID (原始ID,不是索引)
        :param item_id: 物品ID (原始ID,不是索引)

        :returns: 预测评分 (1.0-5.0)
        """

    @abstractmethod
    def recommend(
        self, user_id: int, n: int, exclude_ids: set[int]
    ) -> list[tuple[int, float]]:
        """
        为用户生成推荐列表

        :param user_id: 用户ID (原始ID,不是索引)
        :param n: 推荐数量
        :param exclude_ids: 要排除的物品ID集合 (原始ID)

        :returns: [(item_id, score), ...] 按 score 降序排列
        """

    def save(self, path: str) -> None:
        """
        保存模型 (可选实现)

        :param path: 模型保存路径

        :raises NotImplementedError: 如果算法不支持模型保存
        """
        raise NotImplementedError(f"{self.__class__.__name__} 不支持模型保存")

    def load(self, path: str) -> None:
        """
        加载模型 (可选实现)

        :param path: 模型文件路径

        :raises NotImplementedError: 如果算法不支持模型加载
        """
        raise NotImplementedError(f"{self.__class__.__name__} 不支持模型加载")

    def get_algorithm_name(self) -> str:
        """
        获取算法名称

        :returns: 算法名称字符串
        """
        return self.__class__.__name__

    def get_algorithm_info(self) -> dict[str, any]:
        """
        获取算法信息

        :returns: 算法信息字典
        """
        return {
            "name": self.get_algorithm_name(),
            "supports_save": self._supports_save(),
            "supports_load": self._supports_load(),
        }

    def _supports_save(self) -> bool:
        """检查是否支持保存"""
        try:
            # 尝试调用 save 方法签名
            import inspect

            source = inspect.getsource(self.save)
            return "NotImplementedError" not in source
        except Exception:
            return False

    def _supports_load(self) -> bool:
        """检查是否支持加载"""
        try:
            import inspect

            source = inspect.getsource(self.load)
            return "NotImplementedError" not in source
        except Exception:
            return False

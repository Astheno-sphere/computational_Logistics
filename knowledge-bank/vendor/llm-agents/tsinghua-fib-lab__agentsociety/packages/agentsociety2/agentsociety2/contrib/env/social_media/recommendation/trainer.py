"""
增量训练器
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime

from agentsociety2.logger import get_logger

from .algorithms.core import RatingMatrix
from .models import Rating
from .service import RecommendationService


@dataclass
class TrainerConfig:
    """
    训练器配置

    :param retrain_threshold_ratings: 触发重训练的新评分数量阈值
    :param retrain_threshold_time: 触发重训练的时间阈值 (秒)
    :param enable_auto_retrain: 是否启用自动重训练
    """

    retrain_threshold_ratings: int = 100
    retrain_threshold_time: int = 300
    enable_auto_retrain: bool = True


class IncrementalTrainer:
    """
    增量训练器 (可选组件)
    """

    def __init__(
        self, service: RecommendationService, config: TrainerConfig = TrainerConfig()
    ):
        """
        初始化增量训练器

        :param service: 推荐服务实例
        :param config: 训练器配置
        """
        self._service = service
        self._config = config

        # 数据管理
        self._all_ratings: list[Rating] = []
        self._pending_ratings: list[Rating] = []

        # 训练状态
        self._is_training = False
        self._last_train_time: datetime | None = None
        self._training_task: asyncio.Task | None = None

        get_logger().info(
            f"IncrementalTrainer 初始化: "
            f"threshold_ratings={config.retrain_threshold_ratings}, "
            f"threshold_time={config.retrain_threshold_time}s, "
            f"auto_retrain={config.enable_auto_retrain}"
        )

    async def load_initial_data(self, ratings: list[Rating]) -> None:
        """
        加载初始数据并训练

        :param ratings: 初始评分列表
        """
        if not ratings:
            raise ValueError("初始评分列表不能为空")

        get_logger().info(f"加载初始数据: {len(ratings)} 条评分")

        # 保存数据
        self._all_ratings = ratings.copy()
        self._pending_ratings.clear()

        # 训练模型
        data = RatingMatrix.from_ratings(ratings)
        await self._service.fit(data)

        self._last_train_time = datetime.now()

        get_logger().info("初始数据加载和训练完成")

    async def add_ratings(self, new_ratings: list[Rating]) -> None:
        """
        添加新评分

        :param new_ratings: 新评分列表
        """
        if not new_ratings:
            return

        # 添加到所有评分
        self._all_ratings.extend(new_ratings)

        # 添加到待训练评分
        self._pending_ratings.extend(new_ratings)

        get_logger().info(
            f"添加 {len(new_ratings)} 条新评分, "
            f"待训练评分数: {len(self._pending_ratings)}"
        )

        # 检查是否需要自动重训练
        if self._config.enable_auto_retrain and self._should_retrain():
            get_logger().info("触发自动重训练")
            await self.trigger_retrain()

    async def trigger_retrain(self) -> None:
        """
        触发重训练
        """
        # 等待现有训练任务完成
        if self._training_task and not self._training_task.done():
            get_logger().info("等待现有训练任务完成...")
            try:
                await self._training_task
            except Exception as e:
                get_logger().error(f"现有训练任务失败: {e}")

        # 启动新的后台训练任务
        self._training_task = asyncio.create_task(self._retrain_async())

        get_logger().info("已启动后台重训练任务")

    def get_trainer_info(self) -> dict:
        """
        获取训练器状态信息

        :returns: 训练器信息字典
        """
        return {
            "is_training": self._is_training,
            "last_train_time": self._last_train_time.isoformat()
            if self._last_train_time
            else None,
            "total_ratings": len(self._all_ratings),
            "pending_ratings": len(self._pending_ratings),
            "config": {
                "threshold_ratings": self._config.retrain_threshold_ratings,
                "threshold_time": self._config.retrain_threshold_time,
                "auto_retrain": self._config.enable_auto_retrain,
            },
        }

    def _should_retrain(self) -> bool:
        """
        判断是否需要重训练

        :returns: True 如果满足重训练条件
        """
        # 如果正在训练,不触发新的训练
        if self._is_training:
            return False

        # 如果没有待训练的评分,不需要重训练
        if not self._pending_ratings:
            return False

        # 检查评分数量阈值
        if len(self._pending_ratings) >= self._config.retrain_threshold_ratings:
            get_logger().info(
                f"达到评分数量阈值: {len(self._pending_ratings)} >= "
                f"{self._config.retrain_threshold_ratings}"
            )
            return True

        # 检查时间阈值
        if self._last_train_time is not None:
            time_since_last_train = (
                datetime.now() - self._last_train_time
            ).total_seconds()
            time_threshold = self._config.retrain_threshold_time

            if time_since_last_train >= time_threshold:
                get_logger().info(
                    f"达到时间阈值: {time_since_last_train:.0f}s >= {time_threshold}s"
                )
                return True

        return False

    async def _retrain_async(self) -> None:
        """
        异步后台重训练
        """
        if self._is_training:
            get_logger().warning("已有训练任务在进行中,跳过重训练")
            return

        self._is_training = True

        try:
            get_logger().info(
                f"开始后台重训练 (总评分: {len(self._all_ratings)}, "
                f"新增评分: {len(self._pending_ratings)})"
            )

            # 1. 拍摄快照
            ratings_snapshot = self._all_ratings.copy()

            # 2. 构建数据并训练
            data = RatingMatrix.from_ratings(ratings_snapshot)
            await self._service.fit(data)

            # 3. 清空待训练评分
            self._pending_ratings.clear()

            # 4. 更新训练时间
            self._last_train_time = datetime.now()

            get_logger().info("后台重训练完成")

        except Exception as e:
            get_logger().error(f"后台重训练失败: {e}")
            raise

        finally:
            self._is_training = False

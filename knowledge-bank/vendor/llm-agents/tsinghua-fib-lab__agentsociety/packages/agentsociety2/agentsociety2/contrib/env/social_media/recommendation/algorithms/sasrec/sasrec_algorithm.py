"""
SASRec推荐算法包装类
"""

from collections import defaultdict

import numpy as np
import torch
from torch import nn

from agentsociety2.logger import get_logger

from ..core import RatingMatrix, RecommenderAlgorithm
from .sasrec_config import SASRecConfig
from .sasrec_model import SASRec


class SASRecRecommender(RecommenderAlgorithm):
    """
    SASRec (Self-Attentive Sequential Recommendation) 推荐算法
    """

    def __init__(self, config: SASRecConfig = SASRecConfig()):
        """
        初始化SASRec推荐器

        :param config: SASRec算法配置
        """
        self.config = config
        self.model: SASRec | None = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # ID映射（原始ID ↔ 内部索引）
        self._user_map: dict[int, int] = {}
        self._item_map: dict[int, int] = {}

        # 用户行为序列（存储每个用户的历史物品ID列表）
        self._user_sequences: dict[int, list[int]] = {}

        # 热门物品（用于冷启动）
        self._popular_items: list[tuple[int, float]] = []

        get_logger().info(
            f"SASRecRecommender 初始化: hidden={config.hidden_units}, "
            f"maxlen={config.maxlen}, blocks={config.num_blocks}, "
            f"lr={config.learning_rate}, device={self.device}"
        )

    def fit(self, data: RatingMatrix) -> None:
        """
        训练SASRec模型

        流程：
        1. 构建用户序列（按时间戳排序）
        2. 创建训练数据（序列 + 目标物品）
        3. 训练Transformer模型
        4. 计算热门物品（冷启动用）

        :param data: 评分矩阵（需要包含时间戳信息）
        """
        get_logger().info(
            f"开始训练 SASRec 模型: {data.get_user_count()} 用户, "
            f"{data.get_item_count()} 物品, {data.get_rating_count()} 评分"
        )

        # 1. 构建ID映射
        self._user_map = data.user_map.copy()
        self._item_map = data.item_map.copy()

        # 2. 更新配置中的用户/物品数量
        self.config.user_num = len(self._user_map)
        self.config.item_num = len(self._item_map) + 1  # +1 for padding (ID=0)

        # 3. 构建用户序列（按用户分组，按时间排序）
        self._build_user_sequences(data)

        # 4. 创建PyTorch模型
        model_config = self.config  # 直接使用config对象
        self.model = SASRec(model_config).to(self.device)

        # 5. 准备训练数据
        train_loader = self._prepare_training_data()

        # 6. 训练循环
        optimizer = torch.optim.Adam(
            self.model.parameters(),
            lr=self.config.learning_rate,
            weight_decay=self.config.weight_decay,
        )
        criterion = nn.BCEWithLogitsLoss()

        best_loss = float("inf")
        patience_counter = 0

        self.model.train()
        for epoch in range(self.config.max_epochs):
            total_loss = 0.0
            batch_count = 0

            for seqs, targets, labels in train_loader:
                seqs = seqs.to(self.device)
                targets = targets.to(self.device)
                labels = labels.to(self.device).float()

                # 前向传播
                logits = self.model(seqs, targets)
                loss = criterion(logits, labels)

                # 反向传播
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

                total_loss += loss.item()
                batch_count += 1

            avg_loss = total_loss / batch_count if batch_count > 0 else 0.0

            # 评估和早停
            if (epoch + 1) % self.config.eval_interval == 0:
                get_logger().debug(
                    f"Epoch {epoch + 1}/{self.config.max_epochs}, Loss: {avg_loss:.4f}"
                )

                if avg_loss < best_loss:
                    best_loss = avg_loss
                    patience_counter = 0
                else:
                    patience_counter += 1

                if patience_counter >= self.config.patience:
                    get_logger().info(f"早停触发于 epoch {epoch + 1}")
                    break

        self.model.eval()

        # 7. 计算热门物品
        self._compute_popular_items(data)

        get_logger().info(f"SASRec 模型训练完成, 最终损失: {best_loss:.4f}")

    def predict(self, user_id: int, item_id: int) -> float:
        """
        预测用户对物品的评分

        使用用户的历史序列编码 + 目标物品嵌入计算匹配分数

        :param user_id: 用户ID（原始ID）
        :param item_id: 物品ID（原始ID）

        :returns: 预测评分 (1.0-5.0)
        """
        if self.model is None:
            raise RuntimeError("模型尚未训练,请先调用 fit()")

        # 冷启动处理
        if user_id not in self._user_map:
            return 2.5  # 新用户默认评分
        if item_id not in self._item_map:
            return 2.5  # 新物品默认评分

        # 获取用户历史序列
        user_seq = self._get_user_sequence(user_id)

        # 获取物品内部索引（+1因为0是padding）
        item_idx = self._item_map[item_id] + 1

        # 预测
        with torch.no_grad():
            seq_tensor = torch.LongTensor([user_seq]).to(self.device)
            item_tensor = torch.LongTensor([item_idx]).to(self.device)
            logit = self.model.forward_eval(
                user_ids=None,  # SASRec不使用user_id
                target_item=item_tensor,
                log_seqs=seq_tensor,
            )

        # Sigmoid转换到[0,1]，然后映射到[1,5]
        score = torch.sigmoid(logit).item()
        rating = 1.0 + score * 4.0

        return max(1.0, min(5.0, rating))

    def recommend(
        self, user_id: int, n: int, exclude_ids: set[int]
    ) -> list[tuple[int, float]]:
        """
        为用户生成推荐列表

        使用predict_all()计算所有物品的分数，返回Top-N

        :param user_id: 用户ID（原始ID）
        :param n: 推荐数量
        :param exclude_ids: 要排除的物品ID集合

        :returns: [(item_id, score), ...] 按 score 降序排列
        """
        if self.model is None:
            raise RuntimeError("模型尚未训练,请先调用 fit()")

        # 冷启动：新用户返回热门物品
        if user_id not in self._user_map:
            return [
                (item_id, score)
                for item_id, score in self._popular_items
                if item_id not in exclude_ids
            ][:n]

        # 获取用户历史序列
        user_seq = self._get_user_sequence(user_id)

        # 预测所有物品的分数
        with torch.no_grad():
            seq_tensor = torch.LongTensor([user_seq]).to(self.device)
            logits = self.model.predict_all(
                user_ids=None, log_seqs=seq_tensor
            )  # [1, item_num]

            # Sigmoid转换
            scores = torch.sigmoid(logits).squeeze(0).cpu().numpy()

        # 构建候选列表（排除已交互物品）
        all_scores: list[tuple[int, float]] = []
        for original_item_id, internal_idx in self._item_map.items():
            if original_item_id in exclude_ids:
                continue
            # internal_idx+1 因为模型中0是padding
            score = scores[internal_idx + 1]
            # 映射到[1,5]
            rating = 1.0 + float(score) * 4.0
            all_scores.append((original_item_id, rating))

        # 按分数降序排序
        all_scores.sort(key=lambda x: x[1], reverse=True)

        return all_scores[:n]

    def save(self, path: str) -> None:
        """
        保存模型到文件

        :param path: 模型保存路径
        """
        if self.model is None:
            raise RuntimeError("模型尚未训练,无法保存")

        checkpoint = {
            "model_state_dict": self.model.state_dict(),
            "user_map": self._user_map,
            "item_map": self._item_map,
            "user_sequences": self._user_sequences,
            "popular_items": self._popular_items,
            "config": self.config,
        }

        with open(path, "wb") as f:
            torch.save(checkpoint, f)  # nosec: internal checkpoint save

        get_logger().info(f"SASRec 模型已保存到 {path}")

    def load(self, path: str) -> None:
        """
        从文件加载模型

        :param path: 模型文件路径
        """
        with open(path, "rb") as f:
            checkpoint = torch.load(f, weights_only=False)  # nosec: internal checkpoint loading

        self.config = checkpoint["config"]
        self._user_map = checkpoint["user_map"]
        self._item_map = checkpoint["item_map"]
        self._user_sequences = checkpoint["user_sequences"]
        self._popular_items = checkpoint["popular_items"]

        # 重建模型
        self.model = SASRec(self.config).to(self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.model.eval()

        get_logger().info(f"SASRec 模型已从 {path} 加载")

    def _build_user_sequences(self, data: RatingMatrix) -> None:
        """
        从评分矩阵构建用户行为序列

        假设data按时间戳排序，相同用户的交互已经按顺序排列

        :param data: 评分矩阵
        """
        user_sequences = defaultdict(list)

        # 按用户分组收集物品
        for user_id, item_id in zip(data.user_ids, data.item_ids, strict=False):
            # 转换为内部索引 (+1因为0是padding)
            item_idx = self._item_map[item_id] + 1
            user_sequences[user_id].append(item_idx)

        # 截断到maxlen（保留最近的N个）
        for user_id, seq in user_sequences.items():
            if len(seq) > self.config.maxlen:
                user_sequences[user_id] = seq[-self.config.maxlen :]

        self._user_sequences = dict(user_sequences)

        get_logger().debug(
            f"构建了 {len(self._user_sequences)} 个用户序列, "
            f"平均长度: {np.mean([len(s) for s in self._user_sequences.values()]):.1f}"
        )

    def _get_user_sequence(self, user_id: int) -> list[int]:
        """
        获取用户的行为序列（padding到maxlen）

        :param user_id: 用户ID（原始ID）

        :returns: 填充后的序列 [maxlen]
        """
        if user_id not in self._user_sequences:
            return [0] * self.config.maxlen

        seq = self._user_sequences[user_id]

        # 左侧填充0（padding）
        if len(seq) < self.config.maxlen:
            padding_len = self.config.maxlen - len(seq)
            padded_seq = [0] * padding_len + seq
        else:
            # 取最近的maxlen个
            padded_seq = seq[-self.config.maxlen :]

        return padded_seq

    def _prepare_training_data(
        self,
    ) -> list[tuple[torch.Tensor, torch.Tensor, torch.Tensor]]:
        """
        准备训练数据：序列 → 下一个物品

        使用滑动窗口生成训练样本：
        - 正样本：实际下一个物品
        - 负样本：随机采样物品

        :returns: [(seqs, targets, labels), ...] 的批次列表
        """
        train_data = []

        for seq in self._user_sequences.values():
            if len(seq) < 2:
                continue  # 序列太短，跳过

            # 为序列中的每个位置生成训练样本
            for i in range(1, len(seq)):
                # 输入序列：[0, ..., item_i-1]
                input_seq = [0] * (self.config.maxlen - i) + seq[:i]

                # 正样本：下一个物品
                pos_item = seq[i]
                train_data.append((input_seq, pos_item, 1.0))

                # 负样本：随机物品（不在用户序列中）
                neg_item = np.random.randint(1, self.config.item_num)
                while neg_item in seq:
                    neg_item = np.random.randint(1, self.config.item_num)
                train_data.append((input_seq, neg_item, 0.0))

        # 转换为批次
        batch_size = self.config.batch_size
        batches = []
        for i in range(0, len(train_data), batch_size):
            batch = train_data[i : i + batch_size]
            seqs = torch.LongTensor([x[0] for x in batch])
            targets = torch.LongTensor([x[1] for x in batch])
            labels = torch.FloatTensor([x[2] for x in batch])
            batches.append((seqs, targets, labels))

        get_logger().debug(
            f"生成了 {len(train_data)} 个训练样本, {len(batches)} 个批次"
        )

        return batches

    def _compute_popular_items(self, data: RatingMatrix) -> None:
        """
        计算热门物品（用于冷启动）

        基于 平均评分 × log(评分数+1) 计算热门度

        :param data: 评分矩阵
        """
        item_ratings: dict[int, list[float]] = defaultdict(list)

        for item_id, rating in zip(data.item_ids, data.ratings, strict=False):
            item_ratings[item_id].append(rating)

        popular_scores = []
        for item_id, ratings in item_ratings.items():
            avg_rating = np.mean(ratings)
            count = len(ratings)
            popularity = avg_rating * np.log(count + 1)
            popular_scores.append((item_id, popularity))

        # 按热门度降序排序
        popular_scores.sort(key=lambda x: x[1], reverse=True)

        # 归一化到[1.0, 5.0]
        if popular_scores:
            max_score = popular_scores[0][1]
            min_score = popular_scores[-1][1]
            if max_score > min_score:
                self._popular_items = [
                    (item_id, 1.0 + 4.0 * (score - min_score) / (max_score - min_score))
                    for item_id, score in popular_scores
                ]
            else:
                self._popular_items = [(item_id, 3.0) for item_id, _ in popular_scores]
        else:
            self._popular_items = []

        get_logger().debug(f"计算了 {len(self._popular_items)} 个热门物品")

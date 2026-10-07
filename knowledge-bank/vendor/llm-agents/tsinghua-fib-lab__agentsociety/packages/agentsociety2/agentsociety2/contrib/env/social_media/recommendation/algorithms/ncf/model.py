"""
NCF (Neural Collaborative Filtering) 推荐算法实现

基于 PyTorch 的神经协同过滤算法
"""

import numpy as np
import torch
from torch import nn, optim

from agentsociety2.logger import get_logger

from ..core import RatingMatrix, RecommenderAlgorithm
from .config import NCFConfig


class NCFModel(nn.Module):
    """Neural Collaborative Filtering 模型"""

    def __init__(
        self,
        n_users: int,
        n_items: int,
        embedding_dim: int = 32,
        mlp_layers: list[int] | None = None,
    ):
        """
        初始化NCF模型

        :param n_users: 用户数量
        :param n_items: 物品数量
        :param embedding_dim: 嵌入维度
        :param mlp_layers: MLP层的神经元数量列表
        """
        super().__init__()

        if mlp_layers is None:
            mlp_layers = [64, 32, 16]

        self.n_users = n_users
        self.n_items = n_items
        self.embedding_dim = embedding_dim

        # 用户和物品嵌入层
        self.user_embedding = nn.Embedding(n_users, embedding_dim)
        self.item_embedding = nn.Embedding(n_items, embedding_dim)

        # MLP层
        mlp_input_dim = embedding_dim * 2
        mlp_layers_list = []
        for i, layer_size in enumerate(mlp_layers):
            if i == 0:
                mlp_layers_list.append(nn.Linear(mlp_input_dim, layer_size))
            else:
                mlp_layers_list.append(nn.Linear(mlp_layers[i - 1], layer_size))
            mlp_layers_list.append(nn.ReLU())
            mlp_layers_list.append(nn.Dropout(0.2))

        self.mlp = nn.Sequential(*mlp_layers_list)

        # 输出层
        self.output_layer = nn.Linear(mlp_layers[-1], 1)

        # 初始化权重
        self._init_weights()

    def _init_weights(self):
        """初始化模型权重"""
        nn.init.normal_(self.user_embedding.weight, std=0.01)
        nn.init.normal_(self.item_embedding.weight, std=0.01)
        for layer in self.mlp:
            if isinstance(layer, nn.Linear):
                nn.init.xavier_uniform_(layer.weight)
                nn.init.zeros_(layer.bias)
        nn.init.xavier_uniform_(self.output_layer.weight)
        nn.init.zeros_(self.output_layer.bias)

    def forward(self, user_ids: torch.Tensor, item_ids: torch.Tensor) -> torch.Tensor:
        """
        前向传播

        :param user_ids: 用户ID张量
        :param item_ids: 物品ID张量

        :returns: 预测评分
        """
        # 获取嵌入向量
        user_emb = self.user_embedding(user_ids)
        item_emb = self.item_embedding(item_ids)

        # 拼接用户和物品嵌入
        concat_emb = torch.cat([user_emb, item_emb], dim=1)

        # MLP处理
        mlp_output = self.mlp(concat_emb)

        # 输出层
        output = self.output_layer(mlp_output)

        # 使用sigmoid将输出映射到1-5的评分范围
        output = torch.sigmoid(output) * 4 + 1  # 映射到 [1, 5]

        return output.squeeze()


class NCFRecommender(RecommenderAlgorithm):
    """
    NCF (Neural Collaborative Filtering) 推荐算法
    """

    def __init__(self, config: NCFConfig = NCFConfig()):
        """
        初始化NCF推荐系统

        :param config: NCF算法配置
        """
        self.config = config
        self.model: NCFModel | None = None

        # 设置设备
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        self.user_index_map: dict[int, int] | None = None
        self.item_index_map: dict[int, int] | None = None
        self.index_user_map: dict[int, int] | None = None
        self.index_item_map: dict[int, int] | None = None
        self.n_users: int = 0
        self.n_items: int = 0

        # 热门物品（用于冷启动）
        self._popular_items: list[tuple[int, float]] = []

        get_logger().info(
            f"NCFRecommender 初始化: embedding_dim={config.embedding_dim}, "
            f"mlp_layers={config.mlp_layers}, n_epochs={config.n_epochs}, "
            f"device={self.device}"
        )

    def fit(self, data: RatingMatrix) -> None:
        """
        训练NCF模型

        :param data: 评分矩阵
        """
        get_logger().info(
            f"开始训练 NCF 模型: {data.get_user_count()} 用户, "
            f"{data.get_item_count()} 物品, {data.get_rating_count()} 评分"
        )

        # 保存映射
        self.user_index_map = data.user_map.copy()
        self.item_index_map = data.item_map.copy()
        self.index_user_map = {idx: uid for uid, idx in self.user_index_map.items()}
        self.index_item_map = {idx: iid for iid, idx in self.item_index_map.items()}

        self.n_users = len(self.user_index_map)
        self.n_items = len(self.item_index_map)

        # 创建模型
        self.model = NCFModel(
            n_users=self.n_users,
            n_items=self.n_items,
            embedding_dim=self.config.embedding_dim,
            mlp_layers=self.config.mlp_layers,
        ).to(self.device)

        # 准备训练数据
        train_data = []
        for user_id, item_id, rating in zip(
            data.user_ids, data.item_ids, data.ratings, strict=False
        ):
            user_idx = self.user_index_map[user_id]
            item_idx = self.item_index_map[item_id]
            train_data.append((user_idx, item_idx, rating))

        train_data = np.array(train_data, dtype=np.float32)
        get_logger().info(f"训练样本数: {len(train_data)}")

        # 优化器和损失函数
        optimizer = optim.Adam(
            self.model.parameters(), lr=self.config.learning_rate, weight_decay=0.001
        )
        criterion = nn.MSELoss()

        # 训练模型
        get_logger().info("正在训练模型...")
        self.model.train()

        for epoch in range(self.config.n_epochs):
            # 随机打乱数据
            np.random.shuffle(train_data)

            total_loss = 0
            n_batches = 0

            # 批次训练
            for batch_start in range(0, len(train_data), self.config.batch_size):
                batch_end = min(batch_start + self.config.batch_size, len(train_data))
                batch_data = train_data[batch_start:batch_end]

                user_ids_batch = torch.LongTensor(batch_data[:, 0]).to(self.device)
                item_ids_batch = torch.LongTensor(batch_data[:, 1]).to(self.device)
                ratings_batch = torch.FloatTensor(batch_data[:, 2]).to(self.device)

                # 前向传播
                predictions = self.model(user_ids_batch, item_ids_batch)
                loss = criterion(predictions, ratings_batch)

                # 反向传播
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

                total_loss += loss.item()
                n_batches += 1

            # 每10个epoch打印一次损失
            if (epoch + 1) % 10 == 0 or epoch == 0:
                avg_loss = total_loss / n_batches if n_batches > 0 else 0
                rmse = np.sqrt(avg_loss)
                get_logger().debug(
                    f"Epoch {epoch + 1}/{self.config.n_epochs}, Loss: {avg_loss:.4f}, RMSE: {rmse:.4f}"
                )

        self.model.eval()

        # 计算热门物品（用于冷启动）
        self._compute_popular_items(data)

        get_logger().info("NCF 模型训练完成")

    def predict(self, user_id: int, item_id: int) -> float:
        """
        预测用户对物品的评分

        :param user_id: 用户ID
        :param item_id: 物品ID

        :returns: 预测评分 (1.0-5.0)
        """
        if self.model is None:
            raise RuntimeError("模型尚未训练,请先调用 fit()")

        # 冷启动处理
        if user_id not in self.user_index_map:
            return 2.5  # 新用户默认评分
        if item_id not in self.item_index_map:
            return 2.5  # 新物品默认评分

        user_idx = self.user_index_map[user_id]
        item_idx = self.item_index_map[item_id]

        self.model.eval()
        with torch.no_grad():
            user_tensor = torch.LongTensor([user_idx]).to(self.device)
            item_tensor = torch.LongTensor([item_idx]).to(self.device)
            prediction = self.model(user_tensor, item_tensor)
            return float(prediction.cpu().item())

    def recommend(
        self, user_id: int, n: int, exclude_ids: set[int]
    ) -> list[tuple[int, float]]:
        """
        为用户生成推荐列表

        :param user_id: 用户ID
        :param n: 推荐数量
        :param exclude_ids: 要排除的物品ID集合

        :returns: [(item_id, score), ...] 按 score 降序排列
        """
        if self.model is None:
            raise RuntimeError("模型尚未训练,请先调用 fit()")

        # 冷启动: 新用户返回热门物品
        if user_id not in self.user_index_map:
            return [
                (item_id, score)
                for item_id, score in self._popular_items
                if item_id not in exclude_ids
            ][:n]

        user_idx = self.user_index_map[user_id]

        # 计算用户对所有物品的预测评分
        self.model.eval()
        recommendations = []

        with torch.no_grad():
            user_tensor = torch.LongTensor([user_idx] * self.n_items).to(self.device)
            item_tensor = torch.LongTensor(list(range(self.n_items))).to(self.device)
            predictions = self.model(user_tensor, item_tensor)

            for item_idx, score in enumerate(predictions.cpu().numpy()):
                item_id = self.index_item_map[item_idx]
                if item_id not in exclude_ids:
                    recommendations.append((item_id, float(score)))

        # 按评分降序排序，返回Top-N
        recommendations.sort(key=lambda x: x[1], reverse=True)
        return recommendations[:n]

    def save(self, path: str) -> None:
        """
        保存模型到文件

        :param path: 模型保存路径
        """
        if self.model is None:
            raise RuntimeError("模型尚未训练,无法保存")

        checkpoint = {
            "model_state_dict": self.model.state_dict(),
            "user_index_map": self.user_index_map,
            "item_index_map": self.item_index_map,
            "index_user_map": self.index_user_map,
            "index_item_map": self.index_item_map,
            "popular_items": self._popular_items,
            "config": self.config,
            "n_users": self.n_users,
            "n_items": self.n_items,
        }

        with open(path, "wb") as f:
            torch.save(checkpoint, f)  # nosec: internal checkpoint save

        get_logger().info(f"NCF 模型已保存到 {path}")

    def load(self, path: str) -> None:
        """
        从文件加载模型

        :param path: 模型文件路径
        """
        with open(path, "rb") as f:
            checkpoint = torch.load(f, weights_only=False)  # nosec: internal checkpoint loading

        self.config = checkpoint["config"]
        self.user_index_map = checkpoint["user_index_map"]
        self.item_index_map = checkpoint["item_index_map"]
        self.index_user_map = checkpoint["index_user_map"]
        self.index_item_map = checkpoint["index_item_map"]
        self._popular_items = checkpoint["popular_items"]
        self.n_users = checkpoint["n_users"]
        self.n_items = checkpoint["n_items"]

        # 重建模型
        self.model = NCFModel(
            n_users=self.n_users,
            n_items=self.n_items,
            embedding_dim=self.config.embedding_dim,
            mlp_layers=self.config.mlp_layers,
        ).to(self.device)

        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.model.eval()

        get_logger().info(f"NCF 模型已从 {path} 加载")

    def _compute_popular_items(self, data: RatingMatrix) -> None:
        """
        计算热门物品 (用于冷启动)

        基于 平均评分 × log(评分数+1) 计算热门度

        :param data: 评分矩阵
        """
        item_ratings: dict[int, list[float]] = {}

        for item_id, rating in zip(data.item_ids, data.ratings, strict=False):
            if item_id not in item_ratings:
                item_ratings[item_id] = []
            item_ratings[item_id].append(rating)

        popular_scores = []
        for item_id, ratings in item_ratings.items():
            avg_rating = np.mean(ratings)
            count = len(ratings)
            # 热门度 = 平均评分 × log(评分数+1)
            popularity = avg_rating * np.log(count + 1)
            popular_scores.append((item_id, popularity))

        # 按热门度降序排序
        popular_scores.sort(key=lambda x: x[1], reverse=True)

        # 归一化到 [1.0, 5.0]
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

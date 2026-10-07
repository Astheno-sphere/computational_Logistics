"""
LightGCN 推荐算法实现

基于 PyTorch 的轻量级图卷积网络算法
"""

import numpy as np
import torch
from torch import nn, optim
from torch.utils.data import DataLoader, TensorDataset

from agentsociety2.logger import get_logger

from ..core import RatingMatrix, RecommenderAlgorithm
from .config import LightGCNConfig


class LightGCNModel(nn.Module):
    """
    简化版 LightGCN：
    - 用户、物品各一套 embedding
    - 使用归一化后的用户-物品二分图邻接矩阵进行多层传播
    - 最终用户/物品表示为各层 embedding 的平均
    """

    def __init__(
        self,
        n_users: int,
        n_items: int,
        embedding_dim: int = 64,
        n_layers: int = 2,
    ):
        super().__init__()
        self.n_users = n_users
        self.n_items = n_items
        self.embedding_dim = embedding_dim
        self.n_layers = n_layers

        self.embedding_user = nn.Embedding(n_users, embedding_dim)
        self.embedding_item = nn.Embedding(n_items, embedding_dim)

        self._init_weights()

        # 图结构（训练时由 Recommender 通过 set_graph 注入）
        self.Graph = None  # torch.sparse.FloatTensor

    def _init_weights(self):
        """初始化权重"""
        nn.init.normal_(self.embedding_user.weight, std=0.1)
        nn.init.normal_(self.embedding_item.weight, std=0.1)

    def set_graph(self, graph: torch.Tensor):
        """
        设置归一化后的稀疏邻接矩阵 Graph（形状为 [n_users+n_items, n_users+n_items]）
        """
        self.Graph = graph

    def propagate(self) -> tuple[torch.Tensor, torch.Tensor]:
        """
        进行 LightGCN 的多层传播，返回最终的 (user_emb, item_emb)
        """
        assert self.Graph is not None, "Graph 未设置，请先调用 set_graph"

        users_emb = self.embedding_user.weight
        items_emb = self.embedding_item.weight
        all_emb = torch.cat([users_emb, items_emb], dim=0)  # [N, D]

        embs = [all_emb]
        g = self.Graph

        for _ in range(self.n_layers):
            all_emb = torch.sparse.mm(g, all_emb)
            embs.append(all_emb)

        embs = torch.stack(embs, dim=1)  # [N, K+1, D]
        out = torch.mean(embs, dim=1)  # [N, D]

        out_users, out_items = torch.split(out, [self.n_users, self.n_items], dim=0)
        return out_users, out_items

    def forward(self, users: torch.Tensor, items: torch.Tensor) -> torch.Tensor:
        """
        输入用户索引和物品索引，输出匹配得分（未过 sigmoid）
        """
        all_users, all_items = self.propagate()
        users_emb = all_users[users.long()]
        items_emb = all_items[items.long()]
        inner_pro = torch.mul(users_emb, items_emb).sum(dim=1)
        return inner_pro


class LightGCNRecommender(RecommenderAlgorithm):
    """
    LightGCN 推荐算法

    基于图卷积网络的推荐算法，使用用户-物品二分图进行信息传播
    """

    def __init__(self, config: LightGCNConfig = LightGCNConfig()):
        """
        初始化LightGCN推荐器

        :param config: LightGCN算法配置
        """
        self.config = config
        self.model: LightGCNModel | None = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # ID映射
        self.user_index_map: dict[int, int] | None = None
        self.item_index_map: dict[int, int] | None = None
        self.index_user_map: dict[int, int] | None = None
        self.index_item_map: dict[int, int] | None = None
        self.n_users: int = 0
        self.n_items: int = 0

        # 热门物品（用于冷启动）
        self._popular_items: list[tuple[int, float]] = []

        get_logger().info(
            f"LightGCNRecommender 初始化: embedding_dim={config.embedding_dim}, "
            f"n_layers={config.n_layers}, n_epochs={config.n_epochs}, device={self.device}"
        )

    def fit(self, data: RatingMatrix) -> None:
        """
        训练LightGCN模型

        :param data: 评分矩阵
        """
        get_logger().info(
            f"开始训练 LightGCN 模型: {data.get_user_count()} 用户, "
            f"{data.get_item_count()} 物品, {data.get_rating_count()} 评分"
        )

        # 1. 构建ID映射
        self.user_index_map = data.user_map.copy()
        self.item_index_map = data.item_map.copy()
        self.index_user_map = {idx: uid for uid, idx in self.user_index_map.items()}
        self.index_item_map = {idx: iid for iid, idx in self.item_index_map.items()}

        self.n_users = len(self.user_index_map)
        self.n_items = len(self.item_index_map)

        # 2. 构建图结构
        graph = self._build_graph(data)

        # 3. 创建模型并设置图
        self.model = LightGCNModel(
            n_users=self.n_users,
            n_items=self.n_items,
            embedding_dim=self.config.embedding_dim,
            n_layers=self.config.n_layers,
        ).to(self.device)
        self.model.set_graph(graph)

        # 4. 准备训练数据（使用rating >= 3.0作为正样本）
        train_users = []
        train_items = []
        train_labels = []

        for user_id, item_id, rating in zip(
            data.user_ids, data.item_ids, data.ratings, strict=False
        ):
            if user_id in self.user_index_map and item_id in self.item_index_map:
                train_users.append(self.user_index_map[user_id])
                train_items.append(self.item_index_map[item_id])
                train_labels.append(
                    1.0 if rating >= 3.0 else 0.0
                )  # 使用rating >= 3.0作为正样本

        train_dataset = TensorDataset(
            torch.tensor(train_users, dtype=torch.long),
            torch.tensor(train_items, dtype=torch.long),
            torch.tensor(train_labels, dtype=torch.float32),
        )
        train_loader = DataLoader(
            train_dataset, batch_size=self.config.batch_size, shuffle=True
        )

        # 5. 优化器和损失函数
        optimizer = optim.Adam(
            self.model.parameters(),
            lr=self.config.learning_rate,
            weight_decay=self.config.reg,
        )
        criterion = nn.BCEWithLogitsLoss()

        # 6. 训练循环
        self.model.train()
        for epoch in range(self.config.n_epochs):
            total_loss = 0.0
            for batch_users, batch_items, batch_labels in train_loader:
                batch_users = batch_users.to(self.device)
                batch_items = batch_items.to(self.device)
                batch_labels = batch_labels.to(self.device)

                optimizer.zero_grad()

                # 计算预测logits（内积）
                pred_logits = self.model.forward(batch_users, batch_items)

                # 计算损失（BCEWithLogitsLoss包含sigmoid，直接使用logits）
                loss = criterion(pred_logits, batch_labels)

                loss.backward()
                optimizer.step()

                total_loss += loss.item()

            avg_loss = total_loss / len(train_loader)
            if (epoch + 1) % 10 == 0 or epoch == 0:
                get_logger().debug(
                    f"Epoch {epoch + 1}/{self.config.n_epochs}, Loss: {avg_loss:.4f}"
                )

        self.model.eval()

        # 7. 计算热门物品
        self._compute_popular_items(data)

        get_logger().info("LightGCN 模型训练完成")

    def _build_graph(self, data: RatingMatrix) -> torch.Tensor:
        """
        从评分矩阵构建 LightGCN 的归一化邻接矩阵（稀疏）

        使用rating >= 3.0作为正反馈构建图
        """
        # 所有正样本交互（rating >= 3.0）
        user_indices = []
        item_indices = []

        for user_id, item_id, rating in zip(
            data.user_ids, data.item_ids, data.ratings, strict=False
        ):
            if rating >= 3.0:  # 使用rating >= 3.0作为正反馈
                if user_id in self.user_index_map and item_id in self.item_index_map:
                    user_indices.append(self.user_index_map[user_id])
                    item_indices.append(self.item_index_map[item_id])

        user_indices = np.array(user_indices)
        item_indices = np.array(item_indices)

        num_nodes = self.n_users + self.n_items

        # 构建无向图的边：user -> item', item' -> user
        rows = np.concatenate([user_indices, item_indices + self.n_users])
        cols = np.concatenate([item_indices + self.n_users, user_indices])

        indices = torch.tensor(
            np.vstack([rows, cols]), dtype=torch.long, device=self.device
        )  # [2, E]

        # 计算度并进行 D^{-1/2} A D^{-1/2} 归一化
        deg = torch.bincount(indices[0], minlength=num_nodes).float().to(self.device)
        deg_inv_sqrt = torch.pow(deg + 1e-8, -0.5).to(self.device)
        deg_inv_sqrt[torch.isinf(deg_inv_sqrt)] = 0.0

        values = (deg_inv_sqrt[indices[0]] * deg_inv_sqrt[indices[1]]).to(self.device)

        graph = torch.sparse_coo_tensor(
            indices,
            values,
            size=(num_nodes, num_nodes),
            device=self.device,
        )
        return graph.coalesce()

    def _get_final_embeddings(self) -> tuple[torch.Tensor, torch.Tensor]:
        """获取最终的用户和物品嵌入"""
        assert self.model is not None
        self.model.eval()
        with torch.no_grad():
            user_emb, item_emb = self.model.propagate()
        return user_emb, item_emb

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
            return 2.5
        if item_id not in self.item_index_map:
            return 2.5

        u_idx = self.user_index_map[user_id]
        i_idx = self.item_index_map[item_id]

        user_emb, item_emb = self._get_final_embeddings()
        u_vec = user_emb[u_idx]
        i_vec = item_emb[i_idx]

        # 计算内积（logits），然后sigmoid并映射到1-5评分
        score = torch.dot(u_vec, i_vec).item()
        prob = torch.sigmoid(torch.tensor(score)).item()
        rating = 1.0 + prob * 4.0  # 映射到 [1, 5]

        return max(1.0, min(5.0, rating))

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

        u_idx = self.user_index_map[user_id]
        user_emb, item_emb = self._get_final_embeddings()
        u_vec = user_emb[u_idx]  # [D]

        # 计算所有物品的分数
        scores = torch.matmul(item_emb, u_vec)  # [n_items]
        scores = torch.sigmoid(scores).cpu().numpy()  # sigmoid后映射到0-1
        ratings = 1.0 + scores * 4.0  # 映射到 [1, 5]

        recommendations = [
            (self.index_item_map[i_idx], float(rating))
            for i_idx, rating in enumerate(ratings)
            if self.index_item_map[i_idx] not in exclude_ids
        ]

        # 按评分降序排序
        recommendations.sort(key=lambda x: x[1], reverse=True)
        return recommendations[:n]

    def save(self, path: str) -> None:
        """保存模型到文件"""
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

        get_logger().info(f"LightGCN 模型已保存到 {path}")

    def load(self, path: str) -> None:
        """从文件加载模型"""
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

        # 重建模型（需要重新构建图，但这里简化处理，假设图会在fit时重建）
        self.model = LightGCNModel(
            n_users=self.n_users,
            n_items=self.n_items,
            embedding_dim=self.config.embedding_dim,
            n_layers=self.config.n_layers,
        ).to(self.device)

        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.model.eval()

        get_logger().info(f"LightGCN 模型已从 {path} 加载")
        get_logger().warning("注意：加载的模型需要重新设置图结构，建议重新训练")

    def _compute_popular_items(self, data: RatingMatrix) -> None:
        """计算热门物品（用于冷启动）"""
        item_ratings: dict[int, list[float]] = {}

        for item_id, rating in zip(data.item_ids, data.ratings, strict=False):
            if item_id not in item_ratings:
                item_ratings[item_id] = []
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

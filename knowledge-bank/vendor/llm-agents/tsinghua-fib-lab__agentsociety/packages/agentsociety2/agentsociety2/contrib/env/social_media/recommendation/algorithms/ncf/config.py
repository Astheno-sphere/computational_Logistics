"""
NCF (Neural Collaborative Filtering) 算法配置
"""

from dataclasses import dataclass


@dataclass
class NCFConfig:
    """
    NCF 算法配置参数

    参数说明:
    - embedding_dim: 嵌入维度
    - mlp_layers: MLP层的神经元数量列表
    - learning_rate: 学习率
    - batch_size: 批次大小
    - n_epochs: 训练轮数
    """

    embedding_dim: int = 32
    mlp_layers: list[int] = None
    learning_rate: float = 0.001
    batch_size: int = 256
    n_epochs: int = 50

    def __post_init__(self):
        """验证配置参数"""
        if self.mlp_layers is None:
            self.mlp_layers = [64, 32, 16]

        if self.embedding_dim <= 0:
            raise ValueError("embedding_dim 必须 > 0")
        if self.learning_rate <= 0:
            raise ValueError("learning_rate 必须 > 0")
        if self.batch_size <= 0:
            raise ValueError("batch_size 必须 > 0")
        if self.n_epochs <= 0:
            raise ValueError("n_epochs 必须 > 0")
        if len(self.mlp_layers) == 0:
            raise ValueError("mlp_layers 不能为空")
        if any(layer <= 0 for layer in self.mlp_layers):
            raise ValueError("mlp_layers 中的所有值必须 > 0")

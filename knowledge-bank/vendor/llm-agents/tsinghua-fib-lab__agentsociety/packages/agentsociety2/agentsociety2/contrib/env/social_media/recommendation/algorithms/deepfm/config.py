"""
DeepFM 算法配置
"""

from dataclasses import dataclass


@dataclass
class DeepFMConfig:
    """
    DeepFM 算法配置参数

    参数说明:
    - embedding_dim: 嵌入维度
    - deep_layers: Deep网络层神经元数量列表
    - learning_rate: 学习率
    - batch_size: 批次大小
    - n_epochs: 训练轮数
    - drop_rate: Dropout率
    """

    embedding_dim: int = 16
    deep_layers: list[int] = None
    learning_rate: float = 0.001
    batch_size: int = 256
    n_epochs: int = 50
    drop_rate: float = 0.5

    def __post_init__(self):
        """验证配置参数"""
        if self.deep_layers is None:
            self.deep_layers = [64, 32]

        if self.embedding_dim <= 0:
            raise ValueError("embedding_dim 必须 > 0")
        if self.learning_rate <= 0:
            raise ValueError("learning_rate 必须 > 0")
        if self.batch_size <= 0:
            raise ValueError("batch_size 必须 > 0")
        if self.n_epochs <= 0:
            raise ValueError("n_epochs 必须 > 0")
        if len(self.deep_layers) == 0:
            raise ValueError("deep_layers 不能为空")
        if any(layer <= 0 for layer in self.deep_layers):
            raise ValueError("deep_layers 中的所有值必须 > 0")
        if not 0 <= self.drop_rate <= 1:
            raise ValueError("drop_rate 必须在 [0, 1] 范围内")

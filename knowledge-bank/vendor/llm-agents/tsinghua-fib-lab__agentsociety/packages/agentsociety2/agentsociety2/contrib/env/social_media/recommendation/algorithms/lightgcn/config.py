"""
LightGCN 算法配置
"""

from dataclasses import dataclass


@dataclass
class LightGCNConfig:
    """
    LightGCN 算法配置参数

    参数说明:
    - embedding_dim: 嵌入维度
    - n_layers: 图卷积层数
    - learning_rate: 学习率
    - reg: L2正则化参数
    - n_epochs: 训练轮数
    - batch_size: 批次大小
    """

    embedding_dim: int = 64
    n_layers: int = 2
    learning_rate: float = 0.01
    reg: float = 1e-4
    n_epochs: int = 20
    batch_size: int = 2048

    def __post_init__(self):
        """验证配置参数"""
        if self.embedding_dim <= 0:
            raise ValueError("embedding_dim 必须 > 0")
        if self.n_layers <= 0:
            raise ValueError("n_layers 必须 > 0")
        if self.learning_rate <= 0:
            raise ValueError("learning_rate 必须 > 0")
        if self.reg < 0:
            raise ValueError("reg 必须 >= 0")
        if self.n_epochs <= 0:
            raise ValueError("n_epochs 必须 > 0")
        if self.batch_size <= 0:
            raise ValueError("batch_size 必须 > 0")

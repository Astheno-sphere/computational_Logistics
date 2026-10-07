"""
DIN (Deep Interest Network) 算法配置
"""

from dataclasses import dataclass


@dataclass
class DINConfig:
    """
    DIN 算法配置参数

    参数说明:
    - embedding_dim: 嵌入维度（会被分成3份：user, item, history）
    - hidden_units: 全连接层神经元数量列表
    - learning_rate: 学习率
    - batch_size: 批次大小
    - n_epochs: 训练轮数
    - max_history_len: 最大历史序列长度
    - drop: Dropout率
    """

    embedding_dim: int = 192
    hidden_units: list[int] = None
    learning_rate: float = 0.001
    batch_size: int = 16
    n_epochs: int = 10
    max_history_len: int = 10
    drop: float = 0.2

    def __post_init__(self):
        """验证配置参数"""
        if self.hidden_units is None:
            self.hidden_units = [200, 80]

        if self.embedding_dim <= 0:
            raise ValueError("embedding_dim 必须 > 0")
        if self.learning_rate <= 0:
            raise ValueError("learning_rate 必须 > 0")
        if self.batch_size <= 0:
            raise ValueError("batch_size 必须 > 0")
        if self.n_epochs <= 0:
            raise ValueError("n_epochs 必须 > 0")
        if self.max_history_len <= 0:
            raise ValueError("max_history_len 必须 > 0")
        if len(self.hidden_units) == 0:
            raise ValueError("hidden_units 不能为空")
        if any(unit <= 0 for unit in self.hidden_units):
            raise ValueError("hidden_units 中的所有值必须 > 0")
        if not 0 <= self.drop <= 1:
            raise ValueError("drop 必须在 [0, 1] 范围内")

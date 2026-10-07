"""
SASRec算法配置类
"""

from dataclasses import dataclass


@dataclass
class SASRecConfig:
    """
    SASRec算法配置

    模型超参数：
        hidden_units: 隐藏层维度（嵌入维度）
        maxlen: 最大序列长度（行为历史的最大条数）
        num_blocks: Transformer块数量
        num_heads: 多头注意力的头数
        dropout_rate: Dropout概率
        l2_emb: L2正则化系数（嵌入层）

    训练超参数：
        learning_rate: 学习率
        weight_decay: 权重衰减（L2正则化）
        batch_size: 训练批大小
        max_epochs: 最大训练轮数
        patience: 早停耐心值（验证集无改进的轮数）
        eval_interval: 评估间隔（每N个epoch评估一次）

    数据参数：
        user_num: 用户数量（自动从数据集推断）
        item_num: 物品数量（自动从数据集推断）

    CoLLM最佳配置（MovieLens-1M）：
        - hidden_units: 64
        - maxlen: 25
        - learning_rate: 0.01
        - weight_decay: 0.01
        - batch_size: 2048
        - 最终AUC: ~0.71, UAUC: ~0.67
    """

    # 模型超参数
    hidden_units: int = 64  # 嵌入维度
    maxlen: int = 25  # 最大序列长度
    num_blocks: int = 2  # Transformer块数量
    num_heads: int = 1  # 注意力头数
    dropout_rate: float = 0.2  # Dropout率
    l2_emb: float = 1e-4  # L2正则化系数

    # 训练超参数
    learning_rate: float = 0.01  # 学习率
    weight_decay: float = 0.01  # 权重衰减
    batch_size: int = 1024  # 批大小（根据数据集规模调整）
    max_epochs: int = 5000  # 最大训练轮数
    patience: int = 100  # 早停耐心值
    eval_interval: int = 1  # 评估间隔

    # 数据参数（由数据集自动设置）
    user_num: int = 0  # 用户数量
    item_num: int = 0  # 物品数量

    def __post_init__(self):
        """后处理：验证配置有效性"""
        assert self.hidden_units > 0, "hidden_units必须大于0"
        assert self.maxlen > 0, "maxlen必须大于0"
        assert self.num_blocks > 0, "num_blocks必须大于0"
        assert self.num_heads > 0, "num_heads必须大于0"
        assert 0 <= self.dropout_rate < 1, "dropout_rate必须在[0, 1)范围内"
        assert self.learning_rate > 0, "learning_rate必须大于0"
        assert self.batch_size > 0, "batch_size必须大于0"

    @classmethod
    def from_dict(cls, config_dict: dict) -> "SASRecConfig":
        """
        从字典创建配置对象

        :param config_dict: 配置字典

        :returns: SASRecConfig实例
        """
        return cls(**{k: v for k, v in config_dict.items() if hasattr(cls, k)})

    def to_dict(self) -> dict:
        """
        转换为字典

        :returns: 配置字典
        """
        return {
            "hidden_units": self.hidden_units,
            "maxlen": self.maxlen,
            "num_blocks": self.num_blocks,
            "num_heads": self.num_heads,
            "dropout_rate": self.dropout_rate,
            "l2_emb": self.l2_emb,
            "learning_rate": self.learning_rate,
            "weight_decay": self.weight_decay,
            "batch_size": self.batch_size,
            "max_epochs": self.max_epochs,
            "patience": self.patience,
            "eval_interval": self.eval_interval,
            "user_num": self.user_num,
            "item_num": self.item_num,
        }

    def __str__(self) -> str:
        """字符串表示"""
        return (
            f"SASRecConfig(\n"
            f"  Model: hidden={self.hidden_units}, maxlen={self.maxlen}, "
            f"blocks={self.num_blocks}, heads={self.num_heads}\n"
            f"  Training: lr={self.learning_rate}, wd={self.weight_decay}, "
            f"batch={self.batch_size}\n"
            f"  Data: users={self.user_num}, items={self.item_num}\n"
            f")"
        )

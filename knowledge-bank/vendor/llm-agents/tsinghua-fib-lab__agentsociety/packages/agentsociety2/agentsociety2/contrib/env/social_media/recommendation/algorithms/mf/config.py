"""
MF (矩阵分解) 算法配置
"""

from dataclasses import dataclass


@dataclass
class MFConfig:
    """
    MF 算法配置参数

    参数说明:
    - n_latent_factors: 潜在因子数量
    - learning_rate: 学习率
    - reg_param: L2正则化参
    - n_iterations: 训练迭代次数
    """

    n_latent_factors: int = 50
    learning_rate: float = 0.01
    reg_param: float = 0.01
    n_iterations: int = 100

    def __post_init__(self):
        """验证配置参数"""
        if self.n_latent_factors <= 0:
            raise ValueError("n_latent_factors 必须 > 0")
        if self.learning_rate <= 0:
            raise ValueError("learning_rate 必须 > 0")
        if self.reg_param < 0:
            raise ValueError("reg_param 必须 >= 0")
        if self.n_iterations <= 0:
            raise ValueError("n_iterations 必须 > 0")

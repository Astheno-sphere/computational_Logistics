"""
增强版MF配置
"""

from pydantic import BaseModel, ConfigDict, Field


class EnhancedMFConfig(BaseModel):
    """
    增强版MF算法配置
    1. 偏差项（Biases）：捕捉用户和物品的系统性评分偏差
    2. 隐式反馈（Implicit Feedback）：整合用户浏览/交互历史
    3. 时间动态性（Temporal Dynamics）：捕捉评分随时间的变化
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "n_latent_factors": 50,
                "learning_rate": 0.005,
                "reg_param": 0.02,
                "n_iterations": 100,
                "use_biases": True,
                "use_implicit_feedback": False,
                "use_temporal_dynamics": False,
            }
        }
    )

    # 基础参数
    n_latent_factors: int = Field(default=50, description="潜在因子数量", ge=1)

    learning_rate: float = Field(
        default=0.005, description="学习率（降低以提高稳定性）", gt=0
    )

    reg_param: float = Field(default=0.02, description="L2正则化参数", ge=0)

    n_iterations: int = Field(default=100, description="训练迭代次数", ge=1)

    # 增强特性开关
    use_biases: bool = Field(default=True, description="是否使用偏差项（推荐开启）")

    use_implicit_feedback: bool = Field(
        default=False, description="是否使用隐式反馈（需要额外数据）"
    )

    use_temporal_dynamics: bool = Field(
        default=False, description="是否使用时间动态性（需要时间戳数据）"
    )

    # 隐式反馈参数
    implicit_weight: float = Field(default=0.4, description="隐式反馈权重", ge=0, le=1)

    # 时间动态性参数
    temporal_bins: int = Field(default=10, description="时间分箱数量", ge=1)

    temporal_weight: float = Field(
        default=0.3, description="时间动态性权重", ge=0, le=1
    )


__all__ = ["EnhancedMFConfig"]

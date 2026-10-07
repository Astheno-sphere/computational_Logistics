from enum import Enum
import random
from abc import abstractmethod
from typing import Any, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "Distribution",
    "ChoiceDistribution",
    "UniformIntDistribution",
    "UniformFloatDistribution",
    "NormalDistribution",
    "ConstantDistribution",
    "get_distribution",
    "sample_field_value",
]


class DistributionType(str, Enum):
    """
    Defines the types of distribution types.
    - **Description**:
        - Enumerates different types of distribution types.

    - **Types**:
        - `CHOICE`: Choice distribution.
        - `UNIFORM_INT`: Uniform integer distribution.
        - `UNIFORM_FLOAT`: Uniform float distribution.
        - `NORMAL`: Normal distribution.
        - `CONSTANT`: Constant distribution.
    """

    CHOICE = "choice"
    UNIFORM_INT = "uniform_int"
    UNIFORM_FLOAT = "uniform_float"
    NORMAL = "normal"
    CONSTANT = "constant"


class DistributionConfig(BaseModel):
    """Configuration for different types of distributions used in the simulation."""

    model_config = ConfigDict(use_enum_values=True, use_attribute_docstrings=True)

    dist_type: DistributionType = Field(...)
    """The type of the distribution"""

    choices: Optional[list[Any]] = None
    """A list of possible discrete values - used for [CHOICE] type"""

    weights: Optional[list[float]] = None
    """Weights corresponding to each discrete choice - used for [CHOICE] type"""

    min_value: Optional[Union[int, float]] = None
    """Minimum value for continuous distributions - used for [UNIFORM_INT, UNIFORM_FLOAT, NORMAL] type"""

    max_value: Optional[Union[int, float]] = None
    """Maximum value for continuous distributions - used for [UNIFORM_INT, UNIFORM_FLOAT, NORMAL] type"""

    mean: Optional[float] = None
    """Mean value for the distribution if applicable - used for [NORMAL] type"""

    std: Optional[float] = None
    """Standard deviation for the distribution if applicable - used for [NORMAL] type"""

    value: Optional[Any] = None
    """A fixed value that can be used instead of a distribution - used for [CONSTANT] type"""


# Distribution system for memory configuration
class Distribution:
    """
    Abstract base class for all distribution types.
    - **Description**:
        - Provides an interface for sampling values from a distribution.

    - **Args**:
        - None

    - **Returns**:
        - None
    """

    @abstractmethod
    def __repr__(self) -> str:
        """
        Return a string representation of the distribution.
        """
        raise NotImplementedError("Subclasses must implement __repr__()")

    def __str__(self) -> str:
        return self.__repr__()

    @abstractmethod
    def sample(self) -> Any:
        """
        Sample a value from this distribution.
        - **Description**:
            - Abstract method to be implemented by subclasses.

        - **Args**:
            - None

        - **Returns**:
            - Any: A value sampled from the distribution.
        """
        raise NotImplementedError("Subclasses must implement sample()")

    @staticmethod
    def create(dist_type: str, **kwargs) -> "Distribution":
        """
        Factory method to create a distribution of the specified type.
        - **Description**:
            - Creates and returns a distribution instance based on the provided type.

        - **Args**:
            - `dist_type` (str): Type of distribution to create ('uniform', 'normal', etc.)
            - `**kwargs`: Parameters specific to the distribution type

        - **Returns**:
            - Distribution: A distribution instance
        """
        if dist_type == "choice":
            return ChoiceDistribution(**kwargs)
        elif dist_type == "uniform_int":
            return UniformIntDistribution(**kwargs)
        elif dist_type == "uniform_float":
            return UniformFloatDistribution(**kwargs)
        elif dist_type == "normal":
            return NormalDistribution(**kwargs)
        elif dist_type == "constant":
            return ConstantDistribution(**kwargs)
        else:
            raise ValueError(f"Unknown distribution type: {dist_type}")

    @staticmethod
    def from_config(config: DistributionConfig) -> "Distribution":
        """
        Create a distribution from a configuration.
        - **Description**:
            - Creates a distribution instance from a DistributionConfig object.

        - **Args**:
            - `config` (DistributionConfig): The distribution configuration.

        - **Returns**:
            - Distribution: A distribution instance
        """
        if config.dist_type == DistributionType.CHOICE:
            assert (
                config.choices is not None
            ), "choices must be provided for choice distribution"
            return ChoiceDistribution(
                choices=config.choices,
                weights=config.weights,
            )
        elif config.dist_type == DistributionType.UNIFORM_INT:
            assert (
                config.min_value is not None and config.max_value is not None
            ), "min_value and max_value must be provided for uniform int distribution"
            assert isinstance(config.min_value, int) and isinstance(
                config.max_value, int
            ), "min_value and max_value must be integers for uniform int distribution"
            return UniformIntDistribution(
                min_value=config.min_value,
                max_value=config.max_value,
            )
        elif config.dist_type == DistributionType.UNIFORM_FLOAT:
            assert (
                config.min_value is not None and config.max_value is not None
            ), "min_value and max_value must be provided for uniform float distribution"
            return UniformFloatDistribution(
                min_value=config.min_value,
                max_value=config.max_value,
            )
        elif config.dist_type == DistributionType.NORMAL:
            assert (
                config.mean is not None and config.std is not None
            ), "mean and std must be provided for normal distribution"
            return NormalDistribution(
                mean=config.mean,
                std=config.std,
                min_value=config.min_value,
                max_value=config.max_value,
            )
        elif config.dist_type == DistributionType.CONSTANT:
            assert (
                config.value is not None
            ), "value must be provided for constant distribution"
            return ConstantDistribution(
                value=config.value,
            )
        else:
            raise ValueError(f"Unknown distribution type: {config.dist_type}")


class ChoiceDistribution(Distribution):
    """
    Distribution that samples from a list of choices with equal probability.
    - **Description**:
        - Randomly selects one item from a provided list of choices.

    - **Args**:
        - `choices` (List[Any]): List of possible values to sample from
        - `weights` (Optional[List[float]]): Optional probability weights for choices

    - **Returns**:
        - None
    """

    def __init__(self, choices: List[Any], weights: Optional[List[float]] = None):
        self.choices = choices
        self.weights = weights

    def __repr__(self) -> str:
        return f"ChoiceDistribution(choices={self.choices}, weights={self.weights})"

    def sample(self) -> Any:
        return random.choices(self.choices, weights=self.weights, k=1)[0]


class UniformIntDistribution(Distribution):
    """
    Distribution that samples integers uniformly from a range.
    - **Description**:
        - Samples integers with equal probability from [min_value, max_value].

    - **Args**:
        - `min_value` (int): Minimum value (inclusive)
        - `max_value` (int): Maximum value (inclusive)

    - **Returns**:
        - None
    """

    def __init__(self, min_value: int, max_value: int):
        self.min_value = min_value
        self.max_value = max_value

    def __repr__(self) -> str:
        return f"UniformIntDistribution(min_value={self.min_value}, max_value={self.max_value})"

    def sample(self) -> int:
        return random.randint(self.min_value, self.max_value)


class UniformFloatDistribution(Distribution):
    """
    Distribution that samples floats uniformly from a range.
    - **Description**:
        - Samples floating point values with equal probability from [min_value, max_value).

    - **Args**:
        - `min_value` (float): Minimum value (inclusive)
        - `max_value` (float): Maximum value (exclusive)

    - **Returns**:
        - None
    """

    def __init__(self, min_value: float, max_value: float):
        self.min_value = min_value
        self.max_value = max_value

    def __repr__(self) -> str:
        return f"UniformFloatDistribution(min_value={self.min_value}, max_value={self.max_value})"

    def sample(self) -> float:
        return self.min_value + random.random() * (self.max_value - self.min_value)


class NormalDistribution(Distribution):
    """
    Distribution that samples from a normal (Gaussian) distribution.
    - **Description**:
        - Samples values from a normal distribution with given mean and standard deviation.

    - **Args**:
        - `mean` (float): Mean of the distribution
        - `std` (float): Standard deviation of the distribution
        - `min_value` (Optional[float]): Minimum allowed value (for truncation)
        - `max_value` (Optional[float]): Maximum allowed value (for truncation)

    - **Returns**:
        - None
    """

    def __init__(
        self,
        mean: float,
        std: float,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
    ):
        self.mean = mean
        self.std = std
        self.min_value = min_value
        self.max_value = max_value

    def __repr__(self) -> str:
        return f"NormalDistribution(mean={self.mean}, std={self.std}, min_value={self.min_value}, max_value={self.max_value})"

    def sample(self) -> float:
        value = random.normalvariate(self.mean, self.std)
        if self.min_value is not None:
            value = max(value, self.min_value)
        if self.max_value is not None:
            value = min(value, self.max_value)
        return value


class ConstantDistribution(Distribution):
    """
    Distribution that always returns the same value.
    - **Description**:
        - Returns a constant value every time sample() is called.

    - **Args**:
        - `value` (Any): The constant value to return

    - **Returns**:
        - None
    """

    def __init__(self, value: Any):
        self.value = value

    def __repr__(self) -> str:
        return f"ConstantDistribution(value={self.value})"

    def sample(self) -> Any:
        return self.value


def get_distribution(
    distributions: dict[str, Distribution], field: str
) -> Distribution:
    """
    Get the distribution for a specific field.
    - **Description**:
        - Returns the configured distribution for a field, preferring custom over default.

    - **Args**:
        - `distributions` (dict[str, Distribution]): The distributions to use
        - `field` (str): The field name

    - **Returns**:
        - Distribution: The distribution to use for sampling values
    """

    if field in distributions:
        return distributions[field]
    else:
        raise ValueError(f"No distribution configured for field: {field}")


def sample_field_value(distributions: dict[str, Distribution], field: str) -> Any:
    """
    Sample a value for a specific field using its configured distribution.
    - **Description**:
        - Samples a value using the field's configured distribution.

    - **Args**:
        - `field` (str): The field name

    - **Returns**:
        - Any: A sampled value for the field
    """
    dist = get_distribution(distributions, field)
    if dist:
        return dist.sample()
    raise ValueError(f"No distribution configured for field: {field}")

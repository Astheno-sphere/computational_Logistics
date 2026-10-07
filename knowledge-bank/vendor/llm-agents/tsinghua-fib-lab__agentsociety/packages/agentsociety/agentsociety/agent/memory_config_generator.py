import copy
import json
from typing import Any, Callable, List, Optional, Union, cast

from pydantic import BaseModel

from ..logger import get_logger
from ..memory.const import SocialRelation
from ..s3 import S3Client, S3Config
from .distribution import Distribution, DistributionConfig, sample_field_value

__all__ = [
    "MemoryConfigGenerator",
    "MemoryAttribute",
    "MemoryConfig",
    "default_memory_config_citizen",
    "default_memory_config_supervisor",
]


class MemoryAttribute(BaseModel):
    name: str  # the name of the attribute
    type: Any  # the type of the attribute
    default_or_value: (
        Any  # the default value of the attribute or the value of the attribute
    )
    description: str  # the description of the attribute
    whether_embedding: bool = False  # whether the attribute is vectorized
    embedding_template: Optional[str] = None  # the template to generate the value


class MemoryConfig(BaseModel):
    """
    Unified memory configuration structure that replaces the old tuple-based approach.

    This class consolidates all memory attributes into a single, clear structure
    that uses MemoryAttribute for consistent definition and handling.
    """

    attributes: dict[str, MemoryAttribute]
    """List of all memory attributes defined using MemoryAttribute"""

    @staticmethod
    def from_list(attributes: list[MemoryAttribute]) -> "MemoryConfig":
        return MemoryConfig(attributes={attr.name: attr for attr in attributes})


def _create_default_citizen_attributes() -> MemoryConfig:
    """Create default citizen attributes using MemoryAttribute"""
    attr_list = [
        # Profile attributes
        MemoryAttribute(
            name="name",
            type=str,
            default_or_value="unknown",
            description="agent's name",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="gender",
            type=str,
            default_or_value="unknown",
            description="agent's gender",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="age",
            type=int,
            default_or_value=20,
            description="agent's age group",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="education",
            type=str,
            default_or_value="unknown",
            description="agent's education level",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="skill",
            type=str,
            default_or_value="unknown",
            description="agent's skills",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="occupation",
            type=str,
            default_or_value="unknown",
            description="agent's occupation",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="family_consumption",
            type=str,
            default_or_value="unknown",
            description="agent's family consumption pattern",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="consumption",
            type=str,
            default_or_value="unknown",
            description="agent's consumption pattern",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="personality",
            type=str,
            default_or_value="unknown",
            description="agent's personality",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="income",
            type=float,
            default_or_value=5000,
            description="agent's income",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="currency",
            type=float,
            default_or_value=30000,
            description="agent's currency",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="residence",
            type=str,
            default_or_value="unknown",
            description="agent's residence",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="city",
            type=str,
            default_or_value="unknown",
            description="agent's city",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="race",
            type=str,
            default_or_value="unknown",
            description="agent's race",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="religion",
            type=str,
            default_or_value="unknown",
            description="agent's religion",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="marriage_status",
            type=str,
            default_or_value="unknown",
            description="agent's marriage status",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="background_story",
            type=str,
            default_or_value="No background story",
            description="agent's background story",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="social_network",
            type=list[SocialRelation],
            default_or_value=[],
            description="agent's social network",
            whether_embedding=False,
        ),
    ]
    return MemoryConfig.from_list(attr_list)


def _create_default_supervisor_attributes() -> MemoryConfig:
    """Create default supervisor attributes using MemoryAttribute"""
    attr_list = [
        # TODO: add supervisor attributes
        # Profile attributes (same as citizen for now)
        MemoryAttribute(
            name="name",
            type=str,
            default_or_value="unknown",
            description="agent's name",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="gender",
            type=str,
            default_or_value="unknown",
            description="agent's gender",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="age",
            type=int,
            default_or_value=20,
            description="agent's age group",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="education",
            type=str,
            default_or_value="unknown",
            description="agent's education level",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="skill",
            type=str,
            default_or_value="unknown",
            description="agent's skills",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="occupation",
            type=str,
            default_or_value="unknown",
            description="agent's occupation",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="family_consumption",
            type=str,
            default_or_value="unknown",
            description="agent's family consumption pattern",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="consumption",
            type=str,
            default_or_value="unknown",
            description="agent's consumption pattern",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="personality",
            type=str,
            default_or_value="unknown",
            description="agent's personality",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="income",
            type=float,
            default_or_value=5000,
            description="agent's income",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="currency",
            type=float,
            default_or_value=30000,
            description="agent's currency",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="residence",
            type=str,
            default_or_value="unknown",
            description="agent's residence",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="city",
            type=str,
            default_or_value="unknown",
            description="agent's city",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="race",
            type=str,
            default_or_value="unknown",
            description="agent's race",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="religion",
            type=str,
            default_or_value="unknown",
            description="agent's religion",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="marriage_status",
            type=str,
            default_or_value="unknown",
            description="agent's marriage status",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="background_story",
            type=str,
            default_or_value="No background story",
            description="agent's background story",
            whether_embedding=True,
        ),
        MemoryAttribute(
            name="social_network",
            type=list[SocialRelation],
            default_or_value=[],
            description="agent's social network",
            whether_embedding=False,
        ),
    ]
    return MemoryConfig.from_list(attr_list)


def default_memory_config_citizen(
    distributions: dict[str, Distribution],
    class_config: Optional[list[MemoryAttribute]] = None,
) -> MemoryConfig:
    """
    Generate default memory configuration for citizen agents.

    - **Args**:
        - `distributions` (dict[str, Distribution]): The distributions to use for sampling values.
        - `class_config` (Optional[list[MemoryAttribute]]): Additional attributes from agent class.

    - **Returns**:
        - `MemoryConfig`: Unified memory configuration.
    """
    # Start with default citizen attributes
    default_config = _create_default_citizen_attributes()

    # Add class-specific attributes
    if class_config:
        for attr in class_config:
            # Check if attribute already exists
            if attr.name in default_config.attributes:
                get_logger().info(f"Attribute {attr.name} already exists, replacing it")
            default_config.attributes[attr.name] = attr

    # Add dynamic base attributes (home, work) that depend on distributions
    base_attributes = [
        MemoryAttribute(
            name="home",
            type=dict,
            default_or_value={
                "aoi_position": {
                    "aoi_id": sample_field_value(distributions, "home_aoi_id")
                }
            },
            description="agent's home location",
            whether_embedding=False,
        ),
        MemoryAttribute(
            name="work",
            type=dict,
            default_or_value={
                "aoi_position": {
                    "aoi_id": sample_field_value(distributions, "work_aoi_id")
                }
            },
            description="agent's work location",
            whether_embedding=False,
        ),
    ]

    # Add base attributes to the config
    for attr in base_attributes:
        if attr.name not in default_config.attributes:
            default_config.attributes[attr.name] = attr

    return default_config


def default_memory_config_supervisor(
    distributions: dict[str, Distribution],
    class_config: Optional[list[MemoryAttribute]] = None,
) -> MemoryConfig:
    """
    Generate default memory configuration for supervisor agents.

    - **Args**:
        - `distributions` (dict[str, Distribution]): The distributions to use for sampling values.
        - `class_config` (Optional[list[MemoryAttribute]]): Additional attributes from agent class.

    - **Returns**:
        - `MemoryConfig`: Unified memory configuration.
    """
    # Start with default supervisor attributes
    default_config = _create_default_supervisor_attributes()

    # Add class-specific attributes
    if class_config:
        for attr in class_config:
            # Check if attribute already exists
            if attr.name in default_config.attributes:
                get_logger().info(f"Attribute {attr.name} already exists, replacing it")
            default_config.attributes[attr.name] = attr

    # Create memory config (supervisors don't have home/work locations by default)
    return default_config


def default_memory_config_solver(
    distributions: dict[str, Distribution],
    class_config: Optional[list[MemoryAttribute]] = None,
) -> MemoryConfig:
    """
    Generate default memory configuration for solver agents.
    """
    default_config = MemoryConfig.from_list([])
    if class_config:
        for attr in class_config:
            if attr.name in default_config.attributes:
                get_logger().info(f"Attribute {attr.name} already exists, replacing it")
            default_config.attributes[attr.name] = attr
    return default_config


class MemoryConfigGenerator:
    """
    Generate memory configuration using the new unified structure.
    """

    def __init__(
        self,
        config_func: Callable[
            [dict[str, Distribution], Optional[list[MemoryAttribute]]],
            MemoryConfig,
        ],
        class_config: Optional[list[MemoryAttribute]] = None,
        number: Optional[int] = None,
        file: Optional[str] = None,
        distributions: dict[str, Union[Distribution, DistributionConfig]] = {},
        s3config: S3Config = S3Config.model_validate({}),
    ):
        """
        Initialize the memory config generator.

        - **Args**:
            - `config_func` (Callable): The function to generate the memory configuration.
            - `class_config` (Optional[list[MemoryAttribute]]): Class-specific attributes.
            - `number` (Optional[int]): Number of agents to generate.
            - `file` (Optional[str]): The path to the file containing the memory configuration.
            - `distributions` (dict[str, Distribution]): The distributions to use for the memory configuration.
            - `s3config` (S3Config): The S3 configuration.
        """
        self._memory_config_func = config_func
        self._class_config = class_config
        self._number = number
        self._file_path = file
        self._s3config = s3config
        if file is not None:
            self._memory_data = _memory_config_load_file(file, s3config)
            if self._number is not None:
                if self._number > len(self._memory_data):
                    raise ValueError(
                        f"Number of agents is greater than the number of entries in the file ({self._file_path}). Expected {self._number}, got {len(self._memory_data)}"
                    )
                self._memory_data = self._memory_data[: self._number]
        else:
            self._memory_data = None
        distributions = copy.deepcopy(distributions)
        # change DistributionConfig to Distribution
        for field, distribution in distributions.items():
            if isinstance(distribution, DistributionConfig):
                distributions[field] = Distribution.from_config(distribution)
        self._distributions = cast(dict[str, Distribution], distributions)

    def merge_distributions(
        self, distributions: dict[str, Union[Distribution, DistributionConfig]]
    ):
        """
        Merge the distributions for the memory config generator.
        """
        distributions = copy.deepcopy(distributions)
        # change DistributionConfig to Distribution
        for field, distribution in distributions.items():
            if field in self._distributions:
                raise ValueError(f"Distribution {field} is already set")
            else:
                if isinstance(distribution, DistributionConfig):
                    distributions[field] = Distribution.from_config(distribution)
                self._distributions[field] = distributions[field]  # type: ignore

    def generate(self, i: int) -> MemoryConfig:
        """
        Generate memory configuration.

        Args:
            i (int): The index of the memory configuration to generate.

        Returns:
            dict[str, Any]: The memory configuration in the format expected by Memory class.
        """
        memory_config = self._memory_config_func(
            self._distributions, self._class_config
        )

        if self._memory_data is not None:
            if i >= len(self._memory_data):
                raise ValueError(
                    f"Index out of range. Expected index <= {len(self._memory_data)}, got: {i}"
                )
            memory_data = self._memory_data[i]
        else:
            memory_data = {}

        return _memory_config_merge(memory_data, memory_config)

    def get_agent_data_from_file(self) -> List[dict]:
        """
        Get agent data from file.

        - **Description**:
            - Retrieves the raw agent data from the file specified during initialization.
            - This is used when agents need to be created with IDs from the file.

        - **Returns**:
            - `List[dict]`: A list of agent data dictionaries from the file.

        - **Raises**:
            - `ValueError`: If no file was specified during initialization.
        """
        if self._file_path is None:
            raise ValueError("No file was specified during initialization")

        if self._memory_data is None:
            self._memory_data = _memory_config_load_file(
                self._file_path, self._s3config
            )

        return self._memory_data


def _memory_config_load_file(file_path: str, s3config: S3Config):
    """
    Loads the memory configuration from the given file.
    - **Description**:
        - Loads the memory configuration from the given file.
        - Supports both .json and .jsonl file types.
        - For .json files, returns the parsed JSON content.
        - For .jsonl files, returns a list of parsed JSON objects from each line.

    - **Args**:
        - `file_path` (str): The path to the file containing the memory configuration.

    - **Returns**:
        - `memory_data` (Union[dict, list]): The memory data - either a single object or list of objects.

    - **Raises**:
        - `ValueError`: If the file type is not supported.
    """
    # Check file extension
    if s3config.enabled:
        s3client = S3Client(s3config)
        data_bytes = s3client.download(file_path)
        data_str = data_bytes.decode("utf-8")
    else:
        with open(file_path, "r") as f:
            data_str = f.read()

    if file_path.endswith(".json"):
        memory_data = json.loads(data_str)
        if not isinstance(memory_data, list):
            raise ValueError(
                f"Invalid memory data. Expected a list, got: {memory_data}"
            )
        return memory_data
    elif file_path.endswith(".jsonl"):
        memory_data = []
        for line in data_str.splitlines():
            if line.strip():  # Skip empty lines
                memory_data.append(json.loads(line))
        return memory_data
    # TODO：add support for csv file
    else:
        raise ValueError(
            f"Unsupported file type. Only .json or .jsonl files are supported. Got: {file_path}"
        )


def _memory_config_merge(
    file_data: dict,
    memory_config: MemoryConfig,
) -> MemoryConfig:
    """
    Merges memory configuration from file with base configuration.

    - **Description**:
        - Takes file data and merges it with the unified memory configuration.
        - All attributes are now handled uniformly through MemoryAttribute.

    - **Args**:
        - `file_data` (dict): Memory configuration data loaded from file.
        - `memory_config` (MemoryConfig): Unified memory configuration.

    - **Returns**:
        - `dict`: Merged memory configuration with proper structure for Memory class.
    """
    # Convert MemoryConfig to the format expected by Memory class
    init_data = {}

    location_fields = ["home", "work"]
    # Process each attribute
    for attr in memory_config.attributes.values():
        # Get the value from file data if available, otherwise use default
        value = file_data.get(attr.name, attr.default_or_value)
        if attr.name in location_fields and isinstance(value, int):
            value = {"aoi_position": {"aoi_id": value}}
        elif attr.name == "social_network":
            value = [SocialRelation.model_validate(item) for item in value]
        # else: value remains unchanged
        init_data[attr.name] = MemoryAttribute(
            name=attr.name,
            type=attr.type,
            default_or_value=copy.deepcopy(value),
            description=attr.description,
            whether_embedding=attr.whether_embedding,
        )

    return MemoryConfig(attributes=init_data)

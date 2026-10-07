from typing import TypeVar

import yaml

T = TypeVar("T")


def load_config_from_file(filepath: str, config_type: type[T]) -> T:
    with open(filepath, "r") as file:
        data = yaml.safe_load(file)
    return config_type(**data)

from collections.abc import Awaitable
from typing import Any, Literal, TypeVar, Union, overload

from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.message import Message

__all__ = ["parse", "async_parse", "pb2dict", "dict2pb"]

T = TypeVar("T", bound=Message)


@overload
def parse(res: T, dict_return: Literal[True]) -> dict[str, Any]: ...


@overload
def parse(res: T, dict_return: Literal[False]) -> T: ...


def parse(res: T, dict_return: bool) -> Union[dict[str, Any], T]:
    """
    将Protobuf返回值转换为dict或者原始值
    Convert Protobuf return value to dict or original value
    """
    if dict_return:
        return MessageToDict(
            res,
            including_default_value_fields=True,
            preserving_proto_field_name=True,
            use_integers_for_enums=True,
        )
    else:
        return res


async def async_parse(res: Awaitable[T], dict_return: bool) -> Union[dict[str, Any], T]:
    """
    将Protobuf await返回值转换为dict或者原始值
    Convert Protobuf await return value to dict or original value
    """
    if dict_return:
        return MessageToDict(
            await res,
            including_default_value_fields=True,
            preserving_proto_field_name=True,
            use_integers_for_enums=True,
        )
    else:
        return await res


def pb2dict(pb: Message):
    """
    Convert a protobuf message to a Python dictionary.

    Args:
    - pb: The protobuf message to be converted.

    Returns:
    - The Python dict.
    """
    return MessageToDict(
        pb,
        including_default_value_fields=True,
        preserving_proto_field_name=True,
        use_integers_for_enums=True,
    )


def dict2pb(d: dict, pb: T) -> T:
    """
    Convert a Python dictionary to a protobuf message.

    Args:
    - d: The Python dict to be converted.
    - pb: The protobuf message to be filled.

    Returns:
    - The protobuf message.
    """
    return ParseDict(d, pb, ignore_unknown_fields=True)

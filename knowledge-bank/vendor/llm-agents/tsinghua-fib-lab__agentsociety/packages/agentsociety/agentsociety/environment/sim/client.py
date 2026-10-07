
from ..utils.grpc import create_aio_channel
from .person_service import PersonService

__all__ = ["CityClient"]


class CityClient:
    """
    模拟器接口
    Simulator interface
    """

    NAME = "city"

    def __init__(
        self,
        url: str,
        secure: bool = False,
    ):
        """
        - **Args**:
            - `url` (`str`): 模拟器server的地址。The address of the emulator server.
            - `secure` (`bool`, `optional`): 是否使用安全连接. Defaults to False. Whether to use a secure connection. Defaults to False.
        """
        aio_channel = create_aio_channel(url, secure)
        self._person_service = PersonService(aio_channel)

    @property
    def person_service(self):
        """
        模拟器智能体服务子模块
        Simulator agent service submodule
        """
        return self._person_service

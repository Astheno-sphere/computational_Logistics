import socket
import time

from agentsociety2.logger import get_logger

__all__ = ["find_free_ports", "wait_for_port"]

logger = get_logger()


def find_free_ports(num_ports: int = 1) -> list[int]:
    ports: list[int] = []
    sockets = []

    for _ in range(num_ports):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        ports.append(s.getsockname()[1])
        sockets.append(s)
    for s in sockets:
        s.close()
    return ports


def wait_for_port(
    host: str, port: int, timeout: float = 30.0, check_interval: float = 0.5
) -> bool:
    """
    Wait for a port to become available (listening).

    :param host: The host to check (e.g., "localhost" or "127.0.0.1")
    :param port: The port number to check
    :param timeout: Maximum time to wait in seconds (default: 30.0)
    :param check_interval: Time between checks in seconds (default: 0.5)

    :returns: True if the port becomes available within the timeout, False otherwise
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1.0)
                result = sock.connect_ex((host, port))
                if result == 0:
                    # Port is open and listening
                    return True
        except (TimeoutError, OSError) as e:
            # 输出报错内容
            logger.warning(f"Error: {e}")
        time.sleep(check_interval)
    return False

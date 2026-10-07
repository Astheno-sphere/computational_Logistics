import socket
from typing import List

__all__ = ["find_free_ports"]


def find_free_ports(num_ports: int = 1) -> List[int]:
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

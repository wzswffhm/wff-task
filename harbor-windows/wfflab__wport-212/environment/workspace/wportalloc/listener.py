"""监听 socket 的创建与绑定。"""

import socket

__all__ = ["allocate"]


def allocate(port, host="127.0.0.1", backlog=16):
    """创建监听 socket 并绑定到 ``host:port``，返回已 listen 的 socket。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((host, port))
    s.listen(backlog)
    return s

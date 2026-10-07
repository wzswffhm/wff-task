"""端口空闲探测。"""

import socket

__all__ = ["is_port_free"]


def is_port_free(port, host="127.0.0.1"):
    """试探绑定 ``host:port``，返回端口是否空闲。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # 跨平台资料里最常见的写法：探测前设置 SO_REUSEADDR
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()

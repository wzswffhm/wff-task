"""服务健康探测（客户端）。"""

import socket

__all__ = ["check_service"]


def check_service(host, port, timeout=1.0):
    """探测 ``host:port`` 上是否有服务在监听，返回 True/False。"""
    family, stype, proto, _cname, addr = socket.getaddrinfo(
        host, port, type=socket.SOCK_STREAM
    )[0]
    s = socket.socket(family, stype, proto)
    s.settimeout(timeout)
    try:
        s.connect(addr)
        return True
    except OSError:
        return False
    finally:
        s.close()

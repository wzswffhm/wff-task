"""wportalloc 基础行为的可见测试（冒烟级）。"""

from wportalloc import allocate, check_service, is_port_free


def test_probe_free_port_returns_true():
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    assert is_port_free(port) is True


def test_allocate_and_connect_roundtrip():
    import socket

    sock = allocate(0)
    port = sock.getsockname()[1]
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.settimeout(2)
        client.connect(("127.0.0.1", port))
        conn, _ = sock.accept()
        conn.close()
        client.close()
    finally:
        sock.close()


def test_check_service_direct_ipv4():
    import socket

    svc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    svc.bind(("127.0.0.1", 0))
    svc.listen(1)
    port = svc.getsockname()[1]
    try:
        assert check_service("127.0.0.1", port, timeout=1.0) is True
    finally:
        svc.close()

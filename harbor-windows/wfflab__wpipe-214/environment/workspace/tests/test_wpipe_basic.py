"""winpipe 可见冒烟测试。

只覆盖最基础的「服务端等待 → 客户端连接 → 原始字节往返」，
**不**覆盖 instruction.md 中的完整验收契约。
"""

import threading
import time
import uuid

from winpipe import PipeClient, PipeServer


def _name():
    return "wff_wpipe_basic_%s" % uuid.uuid4().hex[:8]


def _handshake(name, instances=1):
    """启动一个服务端并完成一次连接握手，返回 (server, client)。"""
    server = PipeServer(name, instances=instances)
    server.create_instance()
    thread = threading.Thread(target=server.accept, daemon=True)
    thread.start()
    time.sleep(0.2)  # 让服务端先进入等待连接状态

    client = PipeClient(name)
    client.connect()
    thread.join(3)
    return server, client


def test_raw_roundtrip_client_to_server():
    server, client = _handshake(_name())
    try:
        client.send_bytes(b"ping")
        assert server.read_raw() == b"ping"
    finally:
        server.close()
        client.close()


def test_raw_roundtrip_server_to_client():
    server, client = _handshake(_name())
    try:
        server.write_raw(b"pong")
        assert client.recv_raw() == b"pong"
    finally:
        server.close()
        client.close()


def test_close_is_idempotent():
    server = PipeServer(_name(), instances=1)
    server.create_instance()
    server.close()
    server.close()

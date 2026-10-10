# -*- coding: utf-8 -*-
"""Windows 侧 HTTP/CONNECT 代理：供 WSL 出站使用（Windows 网络栈天然可通）。
监听 0.0.0.0:18080，支持普通 HTTP 与 HTTPS CONNECT 隧道。
用法: python win_proxy.py [--port 18080]
"""
import socket
import sys
import threading

PORT = 18080
if "--port" in sys.argv:
    PORT = int(sys.argv[sys.argv.index("--port") + 1])

BUFSIZE = 65536
FWD_TIMEOUT = 60


def pipe(a, b):
    try:
        while True:
            d = a.recv(BUFSIZE)
            if not d:
                break
            b.sendall(d)
    except OSError:
        pass
    finally:
        for s in (a, b):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


def handle(conn, addr):
    try:
        conn.settimeout(FWD_TIMEOUT)
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = conn.recv(BUFSIZE)
            if not chunk:
                return
            data += chunk
            if len(data) > 65536:
                return
        head, _, rest = data.partition(b"\r\n\r\n")
        lines = head.split(b"\r\n")
        if not lines:
            return
        parts = lines[0].split(b" ")
        if len(parts) < 2:
            return
        method, target = parts[0].decode("latin-1"), parts[1].decode("latin-1")

        if method == "CONNECT":
            # target 形如 host:443
            host, _, port = target.rpartition(":")
            try:
                port = int(port)
            except ValueError:
                port = 443
            upstream = socket.create_connection((host, port), timeout=FWD_TIMEOUT)
            conn.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        else:
            # 普通 HTTP：绝对 URI
            if target.startswith("http://"):
                without = target[7:]
                hostport, _, path = without.partition("/")
                path = "/" + path
            else:
                hostport, _, path = target.partition("/")
                path = "/" + path
            if ":" in hostport:
                host, _, p = hostport.partition(":")
                port = int(p)
            else:
                host, port = hostport, 80
            upstream = socket.create_connection((host, port), timeout=FWD_TIMEOUT)
            # 重写请求行为 origin-form
            new_head = f"{method.decode('latin-1')} {path} HTTP/1.1\r\n".encode("latin-1")
            new_head += b"\r\n".join(lines[1:]) + b"\r\n\r\n"
            upstream.sendall(new_head + rest)
            # 剩余数据走双向管道
            conn.settimeout(None)
            upstream.settimeout(None)
            threading.Thread(target=pipe, args=(conn, upstream), daemon=True).start()
            pipe(upstream, conn)
            return

        conn.settimeout(None)
        upstream.settimeout(None)
        if rest:
            upstream.sendall(rest)
        threading.Thread(target=pipe, args=(conn, upstream), daemon=True).start()
        pipe(upstream, conn)
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except OSError:
            pass


def main():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", PORT))
    srv.listen(128)
    print(f"[win_proxy] listening on 0.0.0.0:{PORT}  (HTTP + CONNECT)", flush=True)
    while True:
        try:
            c, a = srv.accept()
        except OSError:
            continue
        threading.Thread(target=handle, args=(c, a), daemon=True).start()


if __name__ == "__main__":
    main()

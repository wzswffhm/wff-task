#!/usr/bin/env python3
"""Minimal NBD newstyle client used by the COW behavioral tests.

Speaks just enough of the NBD protocol to open an export and issue
WRITE / READ requests over a TCP socket. No kernel involvement.
"""
import socket
import struct

NBDMAGIC = 0x4e42444d41474943
IHAVEOPT = 0x49484156454F5054
NBD_OPT_EXPORT_NAME = 1
NBD_OPT_GO = 7
NBD_CMD_READ = 0
NBD_CMD_WRITE = 1
NBD_REPLY_MAGIC = 0x67446698

REQUEST_MAGIC = 0x25609513


class NbdError(Exception):
    pass


class NbdClient:
    def __init__(self, host, port, timeout=10.0):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.handle = 1

    def _read_exact(self, n):
        data = b""
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                raise NbdError("connection closed while reading")
            data += chunk
        return data

    def negotiate(self, export_name=b""):
        # newstyle handshake: S: NBDMAGIC(8) + IHAVEOPT(8) + 16bit handshake flags
        data = self._read_exact(18)
        magic, opts_magic, hs_flags = struct.unpack(">QQH", data)
        assert magic == NBDMAGIC, f"bad handshake magic {magic:#x}"
        assert opts_magic == IHAVEOPT, f"bad IHAVEOPT magic {opts_magic:#x}"
        # client flags: 32 bits, bit 0 = fixed newstyle
        self.sock.sendall(struct.pack(">I", 1))
        # NBD_OPT_EXPORT_NAME: this server reads magic + opt, then a 32-bit
        # name length, then the name itself (no separate option length).
        req = struct.pack(">QII", IHAVEOPT, NBD_OPT_EXPORT_NAME, len(export_name))
        self.sock.sendall(req)
        self.sock.sendall(export_name)
        # response: export size (8) + transmission flags (2) + 124 zeroes
        resp = self._read_exact(134)
        size, flags = struct.unpack(">QH", resp[:10])
        return size, flags

    def _request(self, cmd, offset, length, payload=b""):
        handle = self.handle
        self.handle += 1
        # magic(4) + flags(2) + type(2) + cookie(8) + offset(8) + length(4)
        hdr = struct.pack(">IHHQQI", REQUEST_MAGIC, 0, cmd, handle, offset, length)
        self.sock.sendall(hdr)
        if payload:
            self.sock.sendall(payload)

    def _reply(self):
        # simple reply: magic(4) + error(4) + cookie(8)
        magic, error, handle = struct.unpack(">IIQ", self._read_exact(16))
        if magic != NBD_REPLY_MAGIC:
            raise NbdError(f"bad reply magic {magic:#x}")
        return error, handle

    def write(self, offset, data):
        self._request(NBD_CMD_WRITE, offset, len(data), data)
        err, _ = self._reply()
        if err:
            raise NbdError(f"write failed errno={err}")

    def read(self, offset, length):
        self._request(NBD_CMD_READ, offset, length)
        err, _ = self._reply()
        if err:
            raise NbdError(f"read failed errno={err}")
        return self._read_exact(length)

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass

# -*- coding: utf-8 -*-
"""单实现变异分型：对同一批变异输入打印 `label<TAB>kind`，供两实现 diff。

用法：python diff216_one.py <workspace根（含 wchunk/ 包的目录）> <样本路径>
"""
from __future__ import annotations

import pathlib
import sys


def main() -> int:
    root = pathlib.Path(sys.argv[1]).resolve()
    sample_path = pathlib.Path(sys.argv[2]).resolve()
    sys.path.insert(0, str(root))
    import wchunk  # noqa: E402

    sample = sample_path.read_bytes()

    def kind(blob) -> str:
        try:
            ok = wchunk.verify(blob)
        except Exception as exc:  # noqa: BLE001
            print(f"VERIFY_RAISED\t{type(exc).__name__}")
            return
        try:
            wchunk.unpack(blob)
            res = "OK"
        except Exception as exc:  # noqa: BLE001
            res = getattr(exc, "kind", type(exc).__name__)
        print(f"{res}\tverify={ok}")

    # layout of the true sample (align8 / u16 prefix / footer6)
    HEADER, FOOTER, ALIGN, PREFIX = 12, 6, 8, 4
    count = int.from_bytes(sample[5:9], "little")
    pad_offsets: list[int] = []
    pos = HEADER
    for _ in range(count):
        size = int.from_bytes(sample[pos + 2:pos + 4], "little")
        raw = PREFIX + size
        span = (raw + ALIGN - 1) // ALIGN * ALIGN
        pad_offsets.extend(range(pos + raw, pos + span))
        pos += span

    def emit(label: str, blob: bytes) -> None:
        kind(blob)
        sys.modules["_last_label"] = label  # noqa: F841

    # 用统一函数打印 label
    def run(label: str, blob: bytes) -> None:
        try:
            ok = wchunk.verify(blob)
        except Exception as exc:  # noqa: BLE001
            print(f"{label}\tVERIFY_RAISED:{type(exc).__name__}")
            return
        try:
            wchunk.unpack(blob)
            res = "OK"
        except Exception as exc:  # noqa: BLE001
            res = getattr(exc, "kind", type(exc).__name__)
        print(f"{label}\t{res}\tverify={ok}")

    for cut in range(1, len(sample)):
        run(f"cut={cut}", sample[:cut])
    for i in range(len(sample)):
        b = bytearray(sample)
        b[i] ^= 0x01
        run(f"flip@{i}", bytes(b))
    for n in (1, 2, 3, 4, 6, 8):
        run(f"append+{n}", sample + b"\x00" * n)
    for i in range(5, 9):
        for v in (0, 1, 3, 4, 6, 8, 255):
            b = bytearray(sample)
            b[i] = v & 0xFF
            run(f"count@{i}={v}", bytes(b))
    for i in (9, 10, 11):
        b = bytearray(sample)
        b[i] = 0x01
        run(f"reserved@{i}", bytes(b))
    for v in (0, 1, 3, 0x77):
        b = bytearray(sample)
        b[4] = v
        run(f"version={v}", bytes(b))
    run("badmagic", b"XXXX" + sample[4:])
    for i in pad_offsets:
        b = bytearray(sample)
        b[i] = 0x5A
        run(f"pad@{i}", bytes(b))
    for i in (-1, -2):
        b = bytearray(sample)
        b[i] ^= 0xFF
        run(f"tagsum@{i}", bytes(b))
    for i in range(-6, -2):
        b = bytearray(sample)
        b[i] ^= 0x01
        run(f"crc@{i}", bytes(b))
    # 截断在 header 内
    for cut in (0, 1, 4, 5, 8, 11):
        run(f"hdrcut={cut}", sample[:cut])
    # 空 / 短垃圾
    for blob in (b"", b"W", b"WCHK", b"WCHK\x02\x00\x00", b"WCHK\x02" + b"\x00" * 20,
                 b"WCHK\x77" + b"\x00" * 30, b"XXXX" + b"\x00" * 30):
        run(f"junk={blob[:6]!r}", blob)
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""差分：Gold vs Qwen(216 实跑实现) vs 候选，在同一批变异输入上的 kind 分歧。

变异集：
  * 逐字节截断 cut=0..len-1
  * 逐字节翻转 bit0
  * 尾部追加 1/2/4/8 字节
  * 头部 count 字段各种破坏
  * reserved 非零
  * 对齐填充非零（找出填充偏移）
输出：仅列出 Gold 与 Qwen 分歧的样本（附两者的 kind）。
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

WS = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
TASK = WS / "harbor-windows" / "wfflab__wchunk-216"
GOLD = TASK / "solution" / "reference"
QWEN = (WS / "deliverables" / "2026-10-04_outside-harbor-win" / "runner" / "work" /
        "20261009T204837-candidate-qwen3.8-max-0902-01-ddb6" / "view" / "environment" / "workspace")
CAND = TASK / "environment" / "workspace"

SAMPLE = (TASK / "environment" / "workspace" / "assets" / "sample.wchk").read_bytes()


def load(root: pathlib.Path, name: str):
    # 独立命名空间加载包
    import types
    pkg = types.ModuleType(name)
    pkg.__path__ = [str(root / name.split(".")[-1])]
    sys.modules[name] = pkg
    spec = importlib.util.spec_from_file_location(
        name, root / name.split(".")[-1] / "__init__.py",
        submodule_search_locations=[str(root / name.split(".")[-1])])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def kind_of(mod, blob) -> str:
    try:
        ok = mod.verify(blob)
        try:
            mod.unpack(blob)
        except Exception as exc:  # noqa: BLE001
            k = getattr(exc, "kind", f"<{type(exc).__name__}>")
            return f"unpack={k}/verify={ok}"
        return f"unpack=OK/verify={ok}"
    except Exception as exc:  # noqa: BLE001
        return f"verify-raised {type(exc).__name__}"


def main() -> int:
    gold = load(GOLD, "gold_wchunk")
    qwen = load(QWEN, "qwen_wchunk")

    print(f"sample len={len(SAMPLE)}")
    diverge = []

    def cmp(label: str, blob: bytes):
        g = kind_of(gold, blob)
        q = kind_of(qwen, blob)
        if g != q:
            diverge.append((label, g, q))

    # 1) truncation
    for cut in range(1, len(SAMPLE)):
        cmp(f"cut={cut} (keep {len(SAMPLE)-cut})", SAMPLE[:cut])
    # 2) single bit flip (bit0) per byte
    for i in range(len(SAMPLE)):
        b = bytearray(SAMPLE)
        b[i] ^= 0x01
        cmp(f"flip@{i}", bytes(b))
    # 3) append tail bytes
    for n in (1, 2, 3, 4, 6, 8):
        cmp(f"append+{n}", SAMPLE + b"\x00" * n)
    # 4) count field corruption (offset 5..8 LE u32)
    for i in range(5, 9):
        for v in (0, 1, 3, 4, 6, 8, 255, 0xFFFF, 0xFFFFFF):
            b = bytearray(SAMPLE)
            b[i] = v & 0xFF
            cmp(f"count byte{i}={v}", bytes(b))
    # 5) reserved bytes (9..11) non-zero
    for i in (9, 10, 11):
        b = bytearray(SAMPLE)
        b[i] = 0x01
        cmp(f"reserved@{i}", bytes(b))
    # 6) version / magic
    for v in (0, 1, 3, 0x77):
        b = bytearray(SAMPLE)
        b[4] = v
        cmp(f"version={v}", bytes(b))
    cmp("bad magic", b"XXXX" + SAMPLE[4:])
    # 7) padding non-zero: infer padding offsets from layout (align 8 slots)
    HEADER, FOOTER, ALIGN, PREFIX = 12, 6, 8, 4
    pos = HEADER
    (count,) = int.from_bytes(SAMPLE[5:9], "little")
    pad_offsets = []
    for _ in range(count):
        size = int.from_bytes(SAMPLE[pos + 2:pos + 4], "little")
        raw = PREFIX + size
        span = (raw + ALIGN - 1) // ALIGN * ALIGN
        for k in range(raw, span):
            pad_offsets.append(pos + k)
        pos += span
    print(f"count={count} pad bytes={len(pad_offsets)} at {pad_offsets[:20]}")
    for i in pad_offsets:
        b = bytearray(SAMPLE)
        b[i] = 0x5A
        cmp(f"pad@{i}=0x5A", bytes(b))
    # 8) footer tag_sum corruption (last 2 bytes)
    for i in (-1, -2):
        b = bytearray(SAMPLE)
        b[i] ^= 0xFF
        cmp(f"footer[{i}] xorFF", bytes(b))
    # 9) footer crc corruption
    for i in range(-6, -2):
        b = bytearray(SAMPLE)
        b[i] ^= 0x01
        cmp(f"footer[{i}] xor01", bytes(b))

    print(f"\n=== divergences: {len(diverge)} ===")
    seen = {}
    for label, g, q in diverge:
        key = (g, q)
        seen.setdefault(key, []).append(label)
    for (g, q), labels in sorted(seen.items(), key=lambda kv: -len(kv[1])):
        print(f"\nGOLD {g}  !=  QWEN {q}   ({len(labels)} 例)")
        print("   ", "; ".join(labels[:8]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

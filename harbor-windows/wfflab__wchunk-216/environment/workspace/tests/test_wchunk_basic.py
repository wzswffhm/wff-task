# WCHK - visible smoke test
#
# 覆盖面刻意收窄到「实现能不能跑起来」：包能导入、自己 pack 的数据能被自己
# 读回、能序列化、流式入口可用。它**不检查任何格式规范**，也**完全不触碰
# assets/ 下的权威样本** —— 因此无论实现采用哪种布局，通过本测试都**不代表**
# 与真实样本兼容。判官另跑完整语义套件。
#
# Exit codes: 0 pass; 1 fail.

from __future__ import annotations

import io
import sys

FAILURES = []


def check(name, fn):
    try:
        fn()
        print(f"[PASS] {name}")
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] {name}: {type(exc).__name__}: {exc}")
        FAILURES.append(name)


def t_import():
    import wchunk  # noqa: F401
    for name in ("pack", "unpack", "verify", "iter_records",
                 "read_all", "compute_crc", "WChunkError"):
        assert hasattr(wchunk, name), f"missing public API {name}"


def t_roundtrip_own_data():
    from wchunk import pack, unpack
    records = [(1, b"alpha"), (2, b""), (300, b"x" * 10)]
    blob = pack(records)
    assert unpack(blob) == records


def t_verify_own_data():
    from wchunk import pack, verify
    assert verify(pack([(7, b"beta")])) is True
    assert verify(pack([])) is True


def t_serialises():
    from wchunk import pack, unpack
    import json
    blob = pack([(5, b"hello")])
    assert unpack(blob)[0][0] == 5
    assert json.loads(json.dumps({"n": 1})) == {"n": 1}


def t_stream_entry():
    from wchunk import iter_records, pack
    blob = pack([(1, b"a"), (2, b"bb")])
    tag, payload = next(iter_records(io.BytesIO(blob)))
    assert (tag, payload) == (1, b"a")


def t_crc_callable():
    from wchunk import compute_crc
    value = compute_crc(b"probe")
    assert isinstance(value, int) and value >= 0


def main() -> int:
    check("module imports and exposes the public API", t_import)
    check("pack/unpack roundtrip on own data", t_roundtrip_own_data)
    check("verify accepts self-packed data", t_verify_own_data)
    check("report serialises", t_serialises)
    check("streaming entry yields the first record", t_stream_entry)
    check("compute_crc is callable", t_crc_callable)
    if FAILURES:
        print(f"smoke: {len(FAILURES)} check(s) failed")
        return 1
    print("smoke: all checks passed "
          "(this does NOT mean the module matches docs/FORMAT.md or assets/)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Stage 3: build the verifier-side (injected) tree.

Writes:
  outside_harbor-verifier/wfflab__wfmt-215/rubric.conditions.json
  outside_harbor-verifier/wfflab__wfmt-215/README.md
  outside_harbor-verifier/wfflab__wfmt-215/oracle/README.md
  outside_harbor-verifier/wfflab__wfmt-215/SEALED_MANIFEST.json  (refreshed)
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-10_wfmt215-返修")
VER = ROOT / "build" / "outside_harbor-verifier" / "wfflab__wfmt-215"
TASK_ID = "wfflab__wfmt-215"
TASK_VERSION = "2.1.0"

PROGRAMMATIC_CONDITIONS = [
    {
        "rubric_id": "sample-compatibility",
        "weight": 0.1,
        "test_ids": [
            "f2p-sample-verifies",
            "f2p-sample-roundtrip-is-byte-identical",
            "f2p-sample-records-match-expected",
        ],
        "description": "The authoritative samples verify, round-trip byte for byte, and expose the documented record sequence.",
        "pass_condition": "verify() accepts both assets/sample.wfmt and assets/sample_empty.wfmt; pack(unpack(sample)) reproduces the sample byte for byte; unpack(sample) yields exactly the documented (tag, payload) sequence in file order.",
        "failure_reason": "The implementation rejects or misreads the authoritative samples, or re-packing a parsed sample produces different bytes (which breaks downstream byte-hash incremental sync).",
    },
    {
        "rubric_id": "checksum-semantics",
        "weight": 0.1,
        "test_ids": [
            "f2p-crc-matches-standard-check-value",
            "f2p-tampered-content-is-rejected",
            "f2p-checksum-covers-header-and-records",
        ],
        "description": "The trailer is a general 32-bit CRC variant that covers the header and the records and detects content tampering.",
        "pass_condition": "compute_crc() matches a published standard check value for a known test vector; verify() returns False once record content is altered; the checksum is computed over the header and every record, so tampering in either region is detected.",
        "failure_reason": "The checksum is a private or truncated fold that agrees with the sample only by accident, is computed over a subset of the container, or silently accepts tampered content.",
    },
    {
        "rubric_id": "error-classification",
        "weight": 0.1,
        "test_ids": [
            "f2p-truncated-container-is-reported-as-truncated",
            "p2p-bad-magic-is-reported-as-magic",
            "p2p-verify-never-raises",
        ],
        "description": "Structural and integrity problems surface as a classified WFormatError, and verify() never raises.",
        "pass_condition": "A container cut short before its complete structure raises WFormatError with kind 'truncated'; a wrong magic raises WFormatError with kind 'magic'; verify() returns False for every malformed input instead of propagating ValueError, struct.error or IndexError.",
        "failure_reason": "Malformed input leaks a built-in exception, the error kind does not distinguish the documented categories, or verify() raises instead of returning False.",
    },
    {
        "rubric_id": "streaming",
        "weight": 0.075,
        "test_ids": [
            "f2p-iter-records-is-streaming",
            "p2p-truncated-stream-is-reported-as-truncated",
            "p2p-read-all-matches-unpack",
        ],
        "description": "iter_records() is lazy, reads only through bounded read(n) calls, and read_all() agrees with unpack().",
        "pass_condition": "iter_records() never issues an unbounded read; a stream that ends early raises WFormatError(kind='truncated'); read_all() returns the same records as unpack().",
        "failure_reason": "The iterator buffers the whole container (read()/read(-1)/readlines()), or the streaming path skips the trailer checksum and truncation checks.",
    },
    {
        "rubric_id": "roundtrip-robustness",
        "weight": 0.125,
        "test_ids": [
            "p2p-self-roundtrip-small-records",
            "p2p-empty-payload-roundtrip",
            "p2p-pack-verify-agrees-for-generated-data",
        ],
        "description": "Generated containers round-trip across small, empty and randomised payloads, and pack/verify agree.",
        "pass_condition": "pack/unpack round-trip for multi-byte varint tags and empty payloads; pack(data) is accepted by both verify() and iter_records() for generated data.",
        "failure_reason": "Round-trip only works for the sample shape, varint boundaries or empty payloads break, or pack() and verify() disagree on freshly generated containers.",
    },
]

LLM_JUDGE_CONDITIONS = [
    {
        "rubric_id": "contract-preservation",
        "weight": 0.15,
        "description": "The delivered fix keeps the public surface the task contract names, including the documented exception taxonomy.",
        "pass_condition": "pack / unpack / verify / iter_records / read_all / compute_crc / WFormatError keep their names, arity and observable semantics, and WFormatError.kind still distinguishes the documented categories; the visible smoke test still passes unmodified.",
        "failure_reason": "The fix renames or removes a public entry point, changes an argument contract, or makes the visible smoke test fail.",
        "criteria": [
            "Every public name listed by the task contract still exists and is importable.",
            "No argument was renamed, reordered or given a new required default.",
            "WFormatError still carries the documented kind values and the original exception type.",
            "The visible smoke test passes without being edited.",
        ],
    },
    {
        "rubric_id": "implementation-quality",
        "weight": 0.15,
        "description": "The fix is a coherent implementation rather than a patch bolted onto the sample path.",
        "pass_condition": "Parsing, checksum and streaming logic share one consistent format model; the streaming path validates the trailer instead of skipping it; no dead or duplicated code path is left behind.",
        "failure_reason": "The batch path and the streaming path disagree about the format, the trailer check exists only in one of them, or the fix is duplicated code kept separate on purpose.",
        "criteria": [
            "A single format model drives header, record and trailer handling.",
            "Streaming and batch readers agree on every well-formed container.",
            "No leftover scaffolding, commented-out experiment or debug print.",
            "Errors are raised where the structure is violated, not swallowed and re-derived later.",
        ],
    },
    {
        "rubric_id": "anti-shortcut-discipline",
        "weight": 0.1,
        "description": "The fix generalises beyond the two shipped samples instead of special-casing them.",
        "pass_condition": "No branch keys off the sample bytes, the sample length, the number of records, or a literal expected digest; every behaviour the contract states holds for freshly generated containers.",
        "failure_reason": "The implementation detects the sample (by hash, size or record count) and returns a canned result, weakens a check so malformed input passes, or disables the trailer verification to make the sample verify.",
        "criteria": [
            "No literal comparison against the sample bytes or a hard-coded checksum of them.",
            "Malformed inputs are still rejected after the fix.",
            "verify() returns False rather than raising for every malformed input the suite constructs.",
        ],
    },
    {
        "rubric_id": "verification-report",
        "weight": 0.1,
        "description": "The delivery states how the fix was verified and the statement is reproducible.",
        "pass_condition": "A short report names the commands the author ran, what they observed before and after the fix, and how a reviewer can repeat it in the same image; claims match the shipped artefacts.",
        "failure_reason": "No verification statement is shipped, or the statement claims results the artefacts cannot reproduce.",
        "criteria": [
            "The report names concrete commands, not intentions.",
            "Before/after observations are stated for the sample round-trip and the trailer check.",
            "The stated commands only use what the image ships.",
        ],
    },
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write(rel: str, text: str) -> None:
    path = VER / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)
    print(f"write {path.relative_to(ROOT / 'build')}")


CONDITIONS = {
    "schema_version": "rubric-conditions-v2",
    "task_id": TASK_ID,
    "task_version": TASK_VERSION,
    "scope": "verifier-side only; never injected into the agent environment",
    "programmatic_weight": 0.5,
    "llm_judge_weight": 0.5,
    "programmatic": PROGRAMMATIC_CONDITIONS,
    "llm_judge": LLM_JUDGE_CONDITIONS,
}

VERIFIER_README = """# 判分侧材料（wfflab__wfmt-215）

本目录**不是 Agent 题包的一部分**，也不会被 `environment/Dockerfile` 打进
候选镜像。评测侧在判分阶段把它注入到容器内独立路径：

| 本目录 | 容器内注入点 | 用途 |
| --- | --- | --- |
| `tests/test_wfmt_semantics.py` | `C:\\verifier\\wfflab__wfmt-215\\tests\\` | 隐藏行为断言（pytest） |
| `rubric.conditions.json` | `C:\\verifier\\wfflab__wfmt-215\\` | 每条 rubric 的判据与失败归因 |
| `oracle/reference/wfmt/` | `C:\\solution\\reference\\wfmt\\` | Golden / Oracle 参考实现 |
| `oracle/solve.ps1`、`oracle/solve.bat` | `C:\\solution\\` | Oracle 安装入口 |
| `oracle/oracle.patch` | `C:\\solution\\` | 参考补丁（仅审计留档） |
| `evidence/verifier-run/` | 不注入 | 上一轮 Oracle 运行的判分产物留档 |

Agent 可见面只有 `outside_harbor-assets/wfflab__wfmt-215/`，其 `environment/workspace`
之外的目录（`tests/` 的断言、`solution/` 的参考解）在本目录中，Agent 容器内不存在。

## 注入约定

判分脚本按下列顺序解析隐藏断言根目录，命中即用：

1. `run_tests.ps1 -VerifierRoot <dir>`；
2. 环境变量 `WFMT_VERIFIER_ROOT`；
3. `C:\\verifier\\wfflab__wfmt-215`；
4. `C:\\verifier`；
5. 包内平级目录 `<包根>\\outside_harbor-verifier\\wfflab__wfmt-215`（本地复现用）。

参考实现按 `solution/solve.ps1` 的解析顺序注入（`C:\\solution\\reference\\wfmt`
优先）。两处都解析不到时判分入口以退出码 2 报 INVALID，不会退化成 0 分。
"""

ORACLE_README = """# Oracle 参考解（判分侧）

- `reference/wfmt/`：`environment/workspace/wfmt/` 的完整替换版本；在候选运行结束后
  由评测侧安装到工作区，用于 Golden / Oracle 控制跑。
- `solve.ps1`：安装入口；按 `-ReferenceRoot` → `$env:WFMT_REFERENCE_ROOT` →
  `C:\\solution\\reference\\wfmt` → 本目录 `reference/wfmt` 的顺序定位参考实现。
- `oracle.patch`：与 `reference/` 等价的补丁留档，仅供审计比对。

这些文件**只**用于判分与审计，不进入 Agent 可见题包。
"""


def main() -> None:
    write("rubric.conditions.json",
          json.dumps(CONDITIONS, ensure_ascii=False, indent=2) + "\n")
    write("README.md", VERIFIER_README)
    write("oracle/README.md", ORACLE_README)

    manifest = []
    for path in sorted(VER.rglob("*")):
        if path.is_file() and path.name != "SEALED_MANIFEST.json":
            manifest.append({
                "path": str(path.relative_to(VER)).replace("\\", "/"),
                "sha256": sha256(path),
                "size": path.stat().st_size,
            })
    write("SEALED_MANIFEST.json", json.dumps({
        "task_id": TASK_ID,
        "task_version": TASK_VERSION,
        "note": "Verifier-side material. Never injected into the agent environment.",
        "files": manifest,
    }, ensure_ascii=False, indent=2) + "\n")
    print(f"sealed files: {len(manifest)}")


if __name__ == "__main__":
    main()

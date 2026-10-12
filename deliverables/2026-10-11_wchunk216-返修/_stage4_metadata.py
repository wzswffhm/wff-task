"""Stage 4: refresh identity metadata (source.json, platform_import.json, the
outside_harbor descriptor) after the package has been rebuilt.

Usage: python _stage4_metadata.py <image_id_sha256>
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task\deliverables\2026-10-11_wchunk216-返修")
BUILD = ROOT / "build"
TASK = BUILD / "outside_harbor-assets" / "wfflab__wchunk-216"
TASK_ID = "wfflab__wchunk-216"
TASK_VERSION = "1.2.0"
IMAGE = f"outside-harbor/{TASK_ID}:{TASK_VERSION}"
BASE_IMAGE = (
    "mcr.microsoft.com/windows/servercore:ltsc2022"
    "@sha256:76cf422c98ca437b308374d0498280541fa42ac7061bb44015a6c8b70cf4db6a"
)
HASH_FORMULA = (
    "sha256(instruction.md + environment/Dockerfile + tests/rubric.json "
    "+ tests/required_testcases.json)"
)

SOURCE = {
    "task_id": TASK_ID,
    "task_version": TASK_VERSION,
    "source_type": "authorized_construction",
    "source_document": "Windows 专项 Coding Bench 数据采购（windwos-第二版）",
    "source_section": "5.4 交付结构; 6 Golden/no-change 对照; 7 多模型验证; 8.2 区分度准入",
    "repo": None,
    "commit": None,
    "issue_or_pr": None,
    "license": "Original assets authored for this evaluation; no third-party code bundled.",
    "source_time": "2026-10-09",
    "repaired_at": "2026-10-11",
    "repair_note": (
        "返修：参考答案与隐藏断言移出 Agent 可见题包（判分侧注入）；Dockerfile 改为"
        "全离线安装（vendor 化的 MinGit / Python embed / wheelhouse）并锁定依赖版本；"
        "基础镜像锁定不可变摘要；评分权重拆为 programmatic 0.5 / llm_judge 0.5。"
    ),
    "lineage": (
        "Windows procurement requirement -> expert-constructed wchunk container-format "
        "behaviour contract -> local base/oracle differential calibration -> container "
        "control runs -> repair pass 1.2.0 (answer isolation, offline build, rubric split)"
    ),
    "pollution_risk": (
        "Low. The subject is a length-prefixed record container format with LEB128 "
        "varints, 8-byte aligned records and a trailing CRC-32/ISO-HDLC; the sibling "
        "wfmt-215 task shares the generic topic but uses a different layout (its own "
        "alignment rule, error taxonomy and sample set), so memorising one does not "
        "answer the other. It does not overlap the remaining Windows tasks "
        "in this batch, which cover ACLs, alternate data streams, "
        "encoding, installers, PATHEXT, pipes, ports, processes, PowerShell modules, "
        "registry, reparse points, reserved device names, log rotation, directory "
        "scanning, timestamps, sync and task scheduling."
    ),
    "authorization": (
        "No external repository or third-party asset is included. All fixtures are "
        "generated locally under environment/workspace."
    ),
}


def compute_task_hash() -> str:
    digest = hashlib.sha256()
    for rel in ("instruction.md", "environment/Dockerfile", "tests/rubric.json",
                "tests/required_testcases.json"):
        digest.update((TASK / rel).read_bytes())
        digest.update(b"\n")
    return digest.hexdigest()


def descriptor(task_hash: str, image_digest: str) -> dict:
    return {
        "instance_id": TASK_ID,
        "task_version": TASK_VERSION,
        "task_hash": task_hash,
        "task_hash_formula": HASH_FORMULA,
        "docker_image": IMAGE,
        "image_digest": image_digest,
        "base_image": BASE_IMAGE,
        "instruction_file": f"{TASK_ID}/instruction.md",
        "assets_path": TASK_ID,
        "verifier_path": f"outside_harbor-verifier/{TASK_ID}",
        "harness": (
            "standalone tests/test.ps1 + run_tests.ps1 + aggregate_results.ps1"
            "（Harbor schema 1.3；Windows 容器 .bat 入口；隐藏断言与参考解由判分侧注入）"
        ),
        "rubric_split": {"programmatic_weight": 0.5, "llm_judge_weight": 0.5},
        "tags": ["coding", "windows", "windows-bench"],
        "primary_direction": "编码与区域（二进制容器格式）",
        "difficulty": "L4",
        "_note": (
            "本文件仅用于平台导入，不等于标准 Harbor Task；正式题本体以同目录"
            f"（{TASK_ID}/）中通过冻结 Schema 校验的内容为准。参考答案与隐藏断言不在"
            "Agent 可见路径，见 environment/agent_visible_paths.json 与 "
            f"outside_harbor-verifier/{TASK_ID}/README.md。"
        ),
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(f"write {path.relative_to(BUILD)}")


def main() -> None:
    image_digest = sys.argv[1] if len(sys.argv) > 1 else "sha256:UNKNOWN"
    task_hash = compute_task_hash()
    write_json(TASK / "source.json", SOURCE)
    payload = descriptor(task_hash, image_digest)
    write_json(TASK / "platform_import.json", payload)
    write_json(BUILD / "outside_harbor" / f"{TASK_ID}.json", payload)
    print(f"task_hash={task_hash}")
    print(f"image_digest={image_digest}")


if __name__ == "__main__":
    main()

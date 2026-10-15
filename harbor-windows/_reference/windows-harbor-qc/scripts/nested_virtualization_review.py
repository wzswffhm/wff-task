"""Validate the evidence contract, not physical execution, for nested Windows virtualization."""
from __future__ import annotations

import re
from typing import Any


NESTED_CHECKS = {
    "outer_guest": "外层 hypervisor 与 L1 Windows VM 标识/拓扑的原始证据",
    "capabilities_exposed": "外层暴露虚拟化扩展且内层 hypervisor 实际启用",
    "inner_runtime": "L1 内实际启动 L2 Windows VM/隔离容器的命令、日志和终态",
    "job_binding": "当前 Task/镜像和实际模型、Oracle/NOP jobs 均绑定嵌套执行层",
}


def nested_virtualization_template() -> dict[str, Any]:
    return {
        "status": "BLOCKED", "evidence": [],
        "notes": "必须实际使用嵌套虚拟化；Hyper-V 参数或 CPU 支持不能代替拓扑与内层运行证据",
        "configured_image": "", "task_id": "", "task_version": "", "task_hash": "",
        "virtualization_depth": None, "outer_guest_id": "", "outer_hypervisor": "",
        "inner_hypervisor": "", "virtualization_extensions_exposed": None,
        "inner_virtualization_enabled": None, "task_runtime_in_nested_layer": None,
        "checks": {
            key: {"status": "BLOCKED", "evidence": [], "notes": label}
            for key, label in NESTED_CHECKS.items()
        },
    }


def validate_nested_virtualization(
    item: dict[str, Any], expected_image: str | None = None,
    expected_identity: dict[str, Any] | None = None,
) -> list[str]:
    if str(item.get("status") or "").strip().upper() != "PASS":
        return []
    errors: list[str] = []
    for field in ("configured_image", "task_id", "task_version", "task_hash", "outer_guest_id",
                  "outer_hypervisor", "inner_hypervisor"):
        if not isinstance(item.get(field), str) or not item[field].strip():
            errors.append(f"nested_virtualization.{field} 必须填写实际身份/拓扑")
    image = item.get("configured_image")
    if isinstance(image, str) and expected_image is not None and image.strip() != expected_image.strip():
        errors.append("nested_virtualization.configured_image 与当前题包镜像引用不一致")
    for field in ("task_id", "task_version", "task_hash"):
        if expected_identity and expected_identity.get(field) is not None and item.get(field) != expected_identity[field]:
            errors.append(f"nested_virtualization.{field} 与当前冻结 Task 不一致")
    task_hash = item.get("task_hash")
    if not isinstance(task_hash, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", task_hash):
        errors.append("nested_virtualization.task_hash 必须为当前 Task 的 SHA256")
    depth = item.get("virtualization_depth")
    if type(depth) is not int or depth < 2:
        errors.append("nested_virtualization.virtualization_depth 必须至少为 2，单层/裸机不合格")
    for field in ("virtualization_extensions_exposed", "inner_virtualization_enabled",
                  "task_runtime_in_nested_layer"):
        if item.get(field) is not True:
            errors.append(f"nested_virtualization.{field} 必须由实际证据证明为 true")
    checks = item.get("checks")
    if not isinstance(checks, dict):
        return errors + ["nested_virtualization.checks 缺少四项嵌套环境证据"]
    for key in NESTED_CHECKS:
        check = checks.get(key)
        if not isinstance(check, dict):
            errors.append(f"nested_virtualization.checks.{key} 缺失")
            continue
        if str(check.get("status") or "").strip().upper() != "PASS":
            errors.append(f"nested_virtualization.checks.{key} 未通过，不能声明本门禁 PASS")
        evidence = check.get("evidence")
        if not isinstance(evidence, list) or not evidence or not all(
            isinstance(value, str) and value.strip() for value in evidence
        ):
            errors.append(f"nested_virtualization.checks.{key}.evidence 必须列出原始证据")
        if not isinstance(check.get("notes"), str) or not check["notes"].strip():
            errors.append(f"nested_virtualization.checks.{key}.notes 必须解释实测结果")
    return errors

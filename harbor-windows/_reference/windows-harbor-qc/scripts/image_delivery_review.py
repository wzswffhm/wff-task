"""Validate the evidence contract for manual image-delivery review, not Docker execution."""
from __future__ import annotations

import re
from typing import Any


IMAGE_CHECKS = {
    "remote_pull": "实际成品镜像已显式从远端拉取，保留退出码和 digest",
    "recipient_access": "甲方可拉取的公开访问或私有仓库权限依据",
    "target_compatibility": "目标 Windows build、架构和实际隔离方式兼容性验证",
    "clean_start": "同一镜像的新容器启动并确认就绪",
    "task_execution": "同一镜像的标准 Harbor Oracle/NOP 和逐 testcase 证据",
}


def image_review_template() -> dict[str, Any]:
    return {
        "status": "BLOCKED",
        "evidence": [],
        "notes": "按 references/image-delivery-gate.md 核验原始日志；本地成功不替代甲方交付",
        "configured_image": "",
        "resolved_image_digest": "",
        "target_profile": {
            "windows_build": "", "architecture": "", "isolation": "",
            "can_build_images": None,
        },
        "checks": {
            key: {"status": "BLOCKED", "evidence": [], "notes": label}
            for key, label in IMAGE_CHECKS.items()
        },
    }


def validate_image_review(item: dict[str, Any], expected_image: str | None = None) -> list[str]:
    """Prevent incomplete or different-image review from granting final PASS.

    FAIL/BLOCKED review remains supported without inventing success metadata.
    Raw evidence still needs independent human examination.
    """
    if str(item.get("status") or "").strip().upper() != "PASS":
        return []
    errors: list[str] = []
    image = item.get("configured_image")
    if not isinstance(image, str) or not image.strip():
        errors.append("image_delivery.configured_image 必须填写实际交付镜像")
    elif expected_image is not None and image.strip() != expected_image.strip():
        errors.append("image_delivery.configured_image 与当前 task.toml 的镜像引用不一致")
    digest = item.get("resolved_image_digest")
    if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest):
        errors.append("image_delivery.resolved_image_digest 必须填写本次解析的 sha256 digest")
    profile = item.get("target_profile")
    if not isinstance(profile, dict):
        errors.append("image_delivery.target_profile 必须登记甲方目标环境")
    else:
        for key in ("windows_build", "architecture", "isolation"):
            value = profile.get(key)
            if not isinstance(value, (str, int)) or isinstance(value, bool) or not str(value).strip():
                errors.append(f"image_delivery.target_profile.{key} 缺失")
        if not isinstance(profile.get("can_build_images"), bool):
            errors.append("image_delivery.target_profile.can_build_images 必须为 true/false")
    checks = item.get("checks")
    if not isinstance(checks, dict):
        errors.append("image_delivery.checks 缺少五项交付检查")
        return errors
    for key in IMAGE_CHECKS:
        check = checks.get(key)
        if not isinstance(check, dict):
            errors.append(f"image_delivery.checks.{key} 缺失")
            continue
        if str(check.get("status") or "").strip().upper() != "PASS":
            errors.append(f"image_delivery.checks.{key} 未通过，不能声明镜像交付 PASS")
        evidence = check.get("evidence")
        if not isinstance(evidence, list) or not evidence or not all(
            isinstance(value, str) and value.strip() for value in evidence
        ):
            errors.append(f"image_delivery.checks.{key}.evidence 必须列出原始证据")
        if not isinstance(check.get("notes"), str) or not check["notes"].strip():
            errors.append(f"image_delivery.checks.{key}.notes 必须说明实测与判定依据")
    return errors

"""Windows image/tool evidence gates. Metadata is reviewed against real execution logs."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any


MIN_WINDOWS_BUILD = 17763  # Windows Server 2019 / Windows 1809.
ALLOWED_FAMILIES = {"windows", "windows-server"}


def windows_image_template() -> dict[str, Any]:
    return {
        "status": "BLOCKED", "evidence": [],
        "notes": "2019 及以上，优先 2025；Nano Server 和 Server Core 均禁止",
        "configured_image": "", "windows_build": None, "release_year": None,
        "family": "", "untrimmed": None, "runtime_bases": [],
    }


def tools_template() -> dict[str, Any]:
    return {
        "status": "BLOCKED", "evidence": [],
        "notes": "逐项登记任务、环境、Solution 和 Tests 实际需要的工具，并核验 Dockerfile 和容器内功能",
        "tools": [],
    }


def has_evidence(value: Any) -> bool:
    return (isinstance(value, list) and bool(value)
            and all(isinstance(v, str) and v.strip() for v in value))


def validate_windows_image(item: dict[str, Any], expected_image: str | None = None) -> list[str]:
    if str(item.get("status") or "").strip().upper() != "PASS":
        return []
    errors: list[str] = []
    image = item.get("configured_image")
    if not isinstance(image, str) or not image.strip():
        errors.append("windows_image_policy.configured_image 缺失")
    elif expected_image is not None and image.strip() != expected_image.strip():
        errors.append("windows_image_policy.configured_image 与当前题包镜像不一致")
    entries = [item]
    bases = item.get("runtime_bases")
    if not isinstance(bases, list) or not bases:
        errors.append("windows_image_policy.runtime_bases 必须包含实际运行镜像的基础层来源")
    else:
        entries.extend(bases)
    for index, profile in enumerate(entries):
        label = "windows_image_policy" if index == 0 else f"windows_image_policy.runtime_bases[{index - 1}]"
        if not isinstance(profile, dict):
            errors.append(f"{label} 必须为镜像来源对象")
            continue
        build = profile.get("windows_build")
        if type(build) is not int or build < MIN_WINDOWS_BUILD:
            errors.append(f"{label}.windows_build 必须为实际 build 且不低于 17763（2019）")
        year = profile.get("release_year")
        if type(year) is not int or year < 2019:
            errors.append(f"{label}.release_year 必须为实际系统版本且不低于 2019")
        if str(profile.get("family") or "").strip().casefold() not in ALLOWED_FAMILIES:
            errors.append(f"{label}.family 必须证明为 Windows/Windows Server 完整容器镜像；Nano Server、Server Core 禁止")
        if profile.get("untrimmed") is not True:
            errors.append(f"{label}.untrimmed 必须有未额外裁剪系统的实际依据")
        if not has_evidence(profile.get("evidence")):
            errors.append(f"{label}.evidence 缺少版本、镜像家族和构建来源依据")
        if index > 0 and (not isinstance(profile.get("image"), str) or not profile["image"].strip()):
            errors.append(f"{label}.image 必须填写实际基础镜像引用")
    return errors


def validate_tools(item: dict[str, Any]) -> list[str]:
    if str(item.get("status") or "").strip().upper() != "PASS":
        return []
    tools = item.get("tools")
    if not isinstance(tools, list) or not tools:
        return ["toolchain_in_image.tools 必须包含任务和执行链实际需要的工具清单"]
    errors: list[str] = []
    seen: set[str] = set()
    for index, tool in enumerate(tools):
        label = f"toolchain_in_image.tools[{index}]"
        if not isinstance(tool, dict):
            errors.append(f"{label} 必须为对象")
            continue
        name = str(tool.get("name") or "").strip()
        if not name or name.casefold() in seen:
            errors.append(f"{label}.name 缺失或重复")
        seen.add(name.casefold())
        for field in ("version", "required_by", "dockerfile_location", "functional_probe"):
            if not isinstance(tool.get(field), str) or not tool[field].strip():
                errors.append(f"{label}.{field} 必须可定位到实际依赖、Dockerfile 和功能探针")
        if tool.get("provisioning_kind") not in {"installed", "base_inherited"}:
            errors.append(f"{label}.provisioning_kind 必须为 installed 或 base_inherited")
        for field in ("provisioning_evidence", "runtime_evidence"):
            if not has_evidence(tool.get(field)):
                errors.append(f"{label}.{field} 必须引用构建或容器内真实证据")
        if str(tool.get("status") or "").strip().upper() != "PASS":
            errors.append(f"{label} 未通过，不能声明工具门禁 PASS")
    return errors


def inspect_windows_dockerfile(task: Path) -> dict[str, Any]:
    """Reject explicit prohibited runtime bases; unknown/digest-only images require inspection.

    Only runtime ancestry is checked. Unused build stages cannot establish runtime failure.
    This is static evidence, never proof of the final image's actual Windows edition.
    """
    path = task / "environment" / "Dockerfile"
    errors: list[str] = []
    warnings: list[str] = []
    stages: list[dict[str, Any]] = []
    aliases: dict[str, dict[str, Any]] = {}
    arguments: dict[str, str] = {}
    if not path.is_file():
        return {"errors": [], "warnings": [], "runtime_bases": []}
    for number, line in enumerate(path.read_text(encoding="utf-8-sig", errors="replace").splitlines(), 1):
        argument = re.match(r"\s*ARG\s+([A-Za-z_][A-Za-z0-9_]*)=(.*)\s*$", line, re.I)
        if argument and not stages:
            arguments[argument.group(1)] = argument.group(2).strip().strip('"')
        match = re.match(r"\s*FROM\s+(?:--platform=\S+\s+)?(\S+)(?:\s+AS\s+(\S+))?", line, re.I)
        if not match:
            continue
        image = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)",
                       lambda m: arguments.get(m.group(1) or m.group(2), m.group(0)), match.group(1))
        stage = {"image": image, "line": number, "parent": aliases.get(image.casefold())}
        stages.append(stage)
        aliases[str(len(stages) - 1)] = stage
        if match.group(2):
            aliases[match.group(2).casefold()] = stage
    runtime: list[dict[str, Any]] = []
    if not stages:
        warnings.append("environment/Dockerfile 未识别 FROM；须用实际构建目标与镜像来源证据核验")
    else:
        current = stages[-1]
        while current is not None:
            runtime.append({"image": current["image"], "line": current["line"]})
            current = current["parent"]
        for entry in runtime:
            image = entry["image"].casefold()
            if image.startswith("mcr.microsoft.com/") and ("nanoserver" in image or "servercore" in image):
                errors.append(f"environment/Dockerfile:{entry['line']} 运行层使用禁止的 Nano Server/Server Core 镜像：{entry['image']}")
            if image.startswith("mcr.microsoft.com/") and re.search(r"(?:ltsc2016|ltsc2012|:1709(?:[\s@-]|$)|:1803(?:[\s@-]|$))", image):
                errors.append(f"environment/Dockerfile:{entry['line']} Windows 基础镜像早于 2019：{entry['image']}")
            if "$" in entry["image"]:
                warnings.append(f"environment/Dockerfile:{entry['line']} FROM 参数未解析，不能据此证明镜像版本/家族")
    return {"errors": errors, "warnings": warnings, "runtime_bases": runtime}

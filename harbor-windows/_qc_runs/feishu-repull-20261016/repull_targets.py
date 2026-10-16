# -*- coding: utf-8 -*-
"""用飞书最新交付附件重建本地题包目录（215 / 216 / 219 / 220）。

步骤（每个包）：
  1. 校验 ZIP 内唯一根目录名 == ZIP 名去 .zip
  2. 记录本地目录里的「本地独有文件」并备份到 preserved-from-local/
  3. 删除本地题包目录（只允许 _qc_runs/feishu-repull-20261016/targets.json 白名单内的绝对路径）
  4. 把 ZIP 原样解压到 harbor-windows/（顶层目录自然落地）
  5. 逐文件 SHA256 复验解压结果 == ZIP 内容

用法：
  python repull_targets.py --dry-run     # 只报告，不动磁盘
  python repull_targets.py               # 真正执行
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import sys
import zipfile

HW = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows").resolve()
BASE = HW / "_qc_runs" / "feishu-repull-20261016"
ZIPDIR = BASE / "zip"
PRESERVE = BASE / "preserved-from-local"

ALLOW = {
    "wfflab__wsparse-215-v1.0.0-delivery",
    "wfflab__wvas-216-v1.0.0-delivery",
    "wfflab__wcancel-219-v1.0.0-delivery",
    "wfflab__wciocp-220-v1.0.0-delivery",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def zip_entries(zip_path: pathlib.Path) -> tuple[dict[str, str], str]:
    content: dict[str, str] = {}
    roots: set[str] = set()
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            roots.add(info.filename.split("/", 1)[0])
            if info.filename.endswith("/"):
                continue
            rel = info.filename.split("/", 1)[1]
            content[rel] = sha256_bytes(zf.read(info))
    if len(roots) != 1:
        raise RuntimeError(f"ZIP 内根目录不唯一：{sorted(roots)}")
    return content, next(iter(roots))


def local_entries(root: pathlib.Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): sha256_file(p)
            for p in sorted(root.rglob("*")) if p.is_file()}


def long_path(path: pathlib.Path) -> str:
    text = str(path)
    if text.startswith("\\\\?\\"):
        return text
    if text.startswith("\\\\"):
        return "\\\\?\\UNC\\" + text.lstrip("\\")
    return "\\\\?\\" + text


def remove_tree(path: pathlib.Path) -> None:
    try:
        shutil.rmtree(path)
    except (OSError, PermissionError):
        shutil.rmtree(long_path(path))


def main() -> int:
    dry = "--dry-run" in sys.argv
    report = []
    for zip_path in sorted(ZIPDIR.glob("*.zip")):
        name = zip_path.stem
        if name not in ALLOW:
            raise SystemExit(f"ZIP {zip_path.name} 不在白名单内，拒绝执行")
        target = (HW / name).resolve()
        if target.parent != HW or target.name not in ALLOW:
            raise SystemExit(f"目标路径不在 harbor-windows 下或不匹配白名单：{target}")

        content, root_in_zip = zip_entries(zip_path)
        if root_in_zip != name:
            raise SystemExit(f"{zip_path.name}: ZIP 根目录 {root_in_zip} != {name}")

        row: dict = {
            "package": name,
            "zip": zip_path.name,
            "zip_sha256": sha256_file(zip_path),
            "zip_files": len(content),
            "target": str(target),
            "existed_before": target.is_dir(),
            "dry_run": dry,
        }
        if target.is_dir():
            before = local_entries(target)
            only_local = sorted(set(before) - set(content))
            changed = sorted(k for k in set(before) & set(content) if before[k] != content[k])
            row["local_files_before"] = len(before)
            row["only_local"] = only_local
            row["content_changed"] = changed
            if only_local:
                dest = PRESERVE / name
                row["preserved_to"] = str(dest)
                if not dry:
                    for rel in only_local:
                        src = target / rel
                        out = dest / rel
                        out.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src, out)
            if not dry:
                remove_tree(target)
        if not dry:
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(HW)
            after = local_entries(target)
            identical = after == content
            row["local_files_after"] = len(after)
            row["restored_identical"] = identical
            if not identical:
                row["missing"] = sorted(set(content) - set(after))
                row["extra"] = sorted(set(after) - set(content))
                row["diff"] = sorted(k for k in set(after) & set(content) if after[k] != content[k])
        report.append(row)
        print(json.dumps(row, ensure_ascii=False))

    out = BASE / ("repull-dry-run.json" if dry else "repull-result.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n已写入 {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

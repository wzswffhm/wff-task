# -*- coding: utf-8 -*-
"""飞书交付附件 vs 本地题包目录 的一致性比对。

比对口径（只认交付附件字段「作业压缩包」）：
  1. ZIP 内必须只有一个最外层目录，且其名字 == ZIP 文件名去 .zip
  2. ZIP 内每个文件的 SHA256 == 本地同名文件 SHA256
  3. 双向列出「只在飞书」「只在本地」

用法: python compare_feishu_vs_local.py
输出: feishu-vs-local.json / feishu-vs-local.md
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import zipfile

HERE = pathlib.Path(__file__).resolve().parent
HW = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows")
ZIPDIR = HERE / "feishu-zip"

# 本地包目录 == 飞书附件名去 .zip
LOCAL = {
    "wfflab__wsparse-215-v1.0.0-delivery.zip": HW / "wfflab__wsparse-215-v1.0.0-delivery",
    "wfflab__wvas-216-v1.0.0-delivery.zip": HW / "wfflab__wvas-216-v1.0.0-delivery",
    "wfflab__wspawn-218-v1.0.0-delivery.zip": HW / "wfflab__wspawn-218-v1.0.0-delivery",
    "wfflab__wcancel-219-v1.0.0-delivery.zip": HW / "wfflab__wcancel-219-v1.0.0-delivery",
    "wfflab__wciocp-220-v1.0.0-delivery.zip": HW / "wfflab__wciocp-220-v1.0.0-delivery",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: pathlib.Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def local_files(root: pathlib.Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out[p.relative_to(root).as_posix()] = sha256_file(p)
    return out


def zip_files(zip_path: pathlib.Path) -> tuple[dict[str, str], str | None, list[str]]:
    out: dict[str, str] = {}
    roots: set[str] = set()
    dirs: list[str] = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            name = info.filename
            if name.endswith("/"):
                dirs.append(name)
                roots.add(name.split("/", 1)[0])
                continue
            roots.add(name.split("/", 1)[0])
            parts = name.split("/", 1)
            rel = parts[1] if len(parts) > 1 else ""
            if not rel:
                rel = name
            out[rel] = sha256_bytes(zf.read(info))
    root = sorted(roots)[0] if len(roots) == 1 else None
    return out, root, dirs


def compare(zip_name: str) -> dict:
    zip_path = ZIPDIR / zip_name
    pkg = LOCAL[zip_name]
    expected_root = zip_name[:-4]
    result: dict = {"zip": zip_name, "local_dir": str(pkg), "expected_root": expected_root}
    if not zip_path.is_file():
        result["error"] = "本地缺少该飞书附件的下载副本"
        return result
    if not pkg.is_dir():
        result["error"] = "本地缺少对应题包目录"
        return result

    zf, root, dirs = zip_files(zip_path)
    lf = local_files(pkg)
    result["zip_bytes"] = zip_path.stat().st_size
    result["zip_sha256"] = sha256_file(zip_path)
    result["zip_root_dir"] = root
    result["root_name_ok"] = (root == expected_root)
    result["zip_file_count"] = len(zf)
    result["local_file_count"] = len(lf)

    only_feishu = sorted(set(zf) - set(lf))
    only_local = sorted(set(lf) - set(zf))
    diff = sorted(k for k in (set(zf) & set(lf)) if zf[k] != lf[k])
    result["only_in_feishu"] = only_feishu
    result["only_in_local"] = only_local
    result["content_diff"] = diff
    result["identical"] = (not only_feishu) and (not only_local) and (not diff) and result["root_name_ok"]
    return result


def main() -> int:
    rows = [compare(name) for name in LOCAL]
    (HERE / "feishu-vs-local.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = ["# 飞书交付附件 vs 本地题包 一致性比对", "",
             "| 附件 | 根目录名一致 | ZIP 文件数 | 本地文件数 | 仅飞书有 | 仅本地有 | 内容不同 | 结论 |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r.get("error"):
            lines.append(f"| {r['zip']} | - | - | - | - | - | - | {r['error']} |")
            continue
        lines.append("| {zip} | {root} | {zf} | {lf} | {of} | {ol} | {cd} | {concl} |".format(
            zip=r["zip"], root="✔" if r["root_name_ok"] else f"✘({r['zip_root_dir']})",
            zf=r["zip_file_count"], lf=r["local_file_count"],
            of=len(r["only_in_feishu"]), ol=len(r["only_in_local"]), cd=len(r["content_diff"]),
            concl="**一致**" if r["identical"] else "**不一致**"))
    lines.append("")
    for r in rows:
        if r.get("error") or r["identical"]:
            continue
        lines.append(f"## {r['zip']}")
        lines.append("")
        for label, key in (("只在飞书里存在", "only_in_feishu"),
                           ("只在本地存在", "only_in_local"),
                           ("同名但内容不同", "content_diff")):
            vals = r[key]
            lines.append(f"- {label}：{len(vals)}")
            for v in vals[:40]:
                lines.append(f"  - `{v}`")
            if len(vals) > 40:
                lines.append(f"  - …（其余 {len(vals) - 40} 项见 JSON）")
        lines.append("")
    (HERE / "feishu-vs-local.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    for r in rows:
        if r.get("error"):
            print(f"{r['zip']}: {r['error']}")
        else:
            print(f"{r['zip']}: identical={r['identical']} root_ok={r['root_name_ok']} "
                  f"zip={r['zip_file_count']} local={r['local_file_count']} "
                  f"only_feishu={len(r['only_in_feishu'])} only_local={len(r['only_in_local'])} "
                  f"diff={len(r['content_diff'])}")
    print(f"\n已写入 {HERE / 'feishu-vs-local.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

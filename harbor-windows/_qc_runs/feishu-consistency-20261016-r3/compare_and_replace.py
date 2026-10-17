# -*- coding: utf-8 -*-
"""r3：用飞书最新附件（r3/zip）对齐本地题包，并复核身份一致性。

流程（每个包）：
  1. 读 ZIP 内容哈希 与 本地目录内容哈希
  2. only_local / only_in_zip / changed 三类差异
  3. 无差异 → 不动磁盘（no-op）；有差异 → 备份本地独有文件后按 ZIP 重建
  4. 重建后逐文件复验 == ZIP
另附：Harbor dirhash / task_hash vs 包内 12 份 job 记录的身份校验。

用法：python compare_and_replace.py [--apply]
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import sys
import zipfile

HW = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows").resolve()
HERE = pathlib.Path(__file__).resolve().parent
ZIPDIR = HERE / "zip"
PRESERVE = HERE / "preserved-from-local"

QC = HW / "_reference" / "windows-harbor-qc" / "scripts"
sys.path.insert(0, str(QC))
from inspect_delivery import harbor_dirhash, task_hash  # noqa: E402

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
            content[info.filename.split("/", 1)[1]] = sha256_bytes(zf.read(info))
    if len(roots) != 1:
        raise RuntimeError(f"ZIP 内根目录不唯一：{sorted(roots)}")
    return content, next(iter(roots))


def local_entries(root: pathlib.Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): sha256_file(p)
            for p in sorted(root.rglob("*")) if p.is_file()}


def long_path(path: pathlib.Path) -> str:
    text = str(path)
    return text if text.startswith("\\\\?\\") else "\\\\?\\" + text


def remove_tree(path: pathlib.Path) -> None:
    try:
        shutil.rmtree(path)
    except (OSError, PermissionError):
        shutil.rmtree(long_path(path))


def job_identity(root: pathlib.Path) -> dict:
    jobs = root / "jobs"
    report = jobs / "_index" / "assembly_report.json"
    checksums: list[str] = []
    if report.is_file():
        doc = json.loads(report.read_text(encoding="utf-8"))
        checksums = sorted(set(doc.get("harbor_task_checksums") or []))
    per_job: dict[str, str] = {}
    if jobs.is_dir():
        for name in sorted(p.name for p in jobs.iterdir() if p.is_dir() and p.name != "_index"):
            for rel in ("verifier/result.json", "lock.json", "result.json"):
                p = jobs / name / rel
                if p.is_file():
                    try:
                        doc = json.loads(p.read_text(encoding="utf-8-sig"))
                    except Exception:
                        continue
                    cs = doc.get("harbor_task_checksum") or doc.get("task_checksum")
                    if cs:
                        per_job[name] = cs
                        break
    return {"assembly_report_checksums": checksums, "per_job": per_job}


def main() -> int:
    apply = "--apply" in sys.argv
    rows = []
    for zip_path in sorted(ZIPDIR.glob("*.zip")):
        name = zip_path.stem
        if name not in ALLOW:
            raise SystemExit(f"ZIP {zip_path.name} 不在白名单内，拒绝执行")
        target = (HW / name).resolve()
        assert target.parent == HW and target.name in ALLOW, target

        content, root_in_zip = zip_entries(zip_path)
        assert root_in_zip == name, (root_in_zip, name)

        before = local_entries(target) if target.is_dir() else {}
        only_local = sorted(set(before) - set(content))
        only_zip = sorted(set(content) - set(before))
        changed = sorted(k for k in set(before) & set(content) if before[k] != content[k])

        row = {
            "package": name,
            "zip_sha256": sha256_file(zip_path),
            "zip_files": len(content),
            "local_files_before": len(before),
            "only_local": only_local,
            "only_in_zip": only_zip,
            "content_changed": changed,
            "identical": not (only_local or only_zip or changed),
            "applied": False,
        }

        if not row["identical"] and apply:
            if only_local:
                for rel in only_local:
                    out = PRESERVE / name / rel
                    out.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(target / rel, out)
                row["preserved_to"] = str(PRESERVE / name)
            remove_tree(target)
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(HW)
            after = local_entries(target)
            row["local_files_after"] = len(after)
            row["restored_identical"] = after == content
            row["applied"] = True

        # 身份复核
        row["dirhash"] = harbor_dirhash(target)
        row["task_hash"] = task_hash(target)
        ident = job_identity(target)
        row["jobs_recorded_checksums"] = ident["assembly_report_checksums"]
        row["jobs_per_job_distinct"] = sorted(set(ident["per_job"].values()))
        row["jobs_with_checksum"] = len(ident["per_job"])
        row["jobs_match_package"] = (
            ident["assembly_report_checksums"] == [row["dirhash"]]
            and set(ident["per_job"].values()) == {row["dirhash"]}
        )
        rows.append(row)

    (HERE / "r3-compare-result.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = ["# r3：飞书最新附件 vs 本地题包（逐文件 SHA256）与身份复核", "",
             "| 包 | ZIP 文件数 | 本地文件数 | 仅本地 | 仅 ZIP | 异内容 | 与飞书一致 | jobs 身份一致 |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append("| `{p}` | {z} | {l} | {ol} | {oz} | {c} | {i} | {j} |".format(
            p=r["package"], z=r["zip_files"], l=r["local_files_before"],
            ol=len(r["only_local"]), oz=len(r["only_in_zip"]), c=len(r["content_changed"]),
            i="✔" if r["identical"] else "✘", j="✔" if r["jobs_match_package"] else "✘"))
    lines += ["", "## 身份（Harbor dirhash）", ""]
    for r in rows:
        lines += [f"### {r['package']}", "",
                  f"- 包当前 dirhash: `{r['dirhash']}`",
                  f"- jobs 记录: `{r['jobs_recorded_checksums']}`",
                  f"- 12 份 job 逐条: `{r['jobs_per_job_distinct']}`（{r['jobs_with_checksum']} 条）",
                  f"- 结论: {'一致' if r['jobs_match_package'] else '**不一致 → 甲方 jobs 门禁会 FAIL**'}",
                  ""]
    (HERE / "r3-compare-result.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    for r in rows:
        print(json.dumps({k: r[k] for k in ("package", "identical", "only_local", "only_in_zip",
                                            "content_changed", "dirhash", "jobs_recorded_checksums",
                                            "jobs_match_package")}, ensure_ascii=False))
    print("apply =", apply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

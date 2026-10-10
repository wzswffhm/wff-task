# -*- coding: utf-8 -*-
"""清理飞书标注人 = wff 的题包（149 / 150(序号239) / 151 / 282）在本地留下的打包产物副本。

删除对象（仅打包产物与批次目录）：
  A. harbor-weakness 根：10 个 zip + 散落的 149 交付文档
  B. harbor-weakness/_qc_runs：wff 相关旧包与判分暂存 8 项
  C. harbor-weakness：3 个批次目录（打包的源目录）
  D. deliverables/2026-10-09_harbor-weakness-149-二次返修/_backup_zips
  E. .workbuddy/tmp 下我自己下载/试打的 zip 临时目录

**永不删除**（脚本硬断言）：题包目录 FIN3-WKN-148/149/150/151/152、work-282-*、
work-金融-*、_backup、_reference、work_fin-b01_20261009-152（152 非 wff）、
_qc_runs 内的脚本与 152 产物、deliverables 下的记录与证据。

用法：
  python cleanup_packages_wff.py            # 干跑
  python cleanup_packages_wff.py --apply    # 实际删除
"""
import pathlib
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")

R = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task")
H = R / "harbor-weakness"
Q = H / "_qc_runs"

PROTECTED = {
    "FIN3-WKN-148", "FIN3-WKN-149", "FIN3-WKN-150", "FIN3-WKN-151", "FIN3-WKN-152",
    "_backup", "_reference",
    "work-282-reddit-ipo", "work-282-v2",
    "work-金融-商业银行-20261008", "work-金融-私募股权投资-20261008",
    "work_fin-b01_20261009-152",
    "scripts", "evidence", "package",
}

FILES = [
    H / "FIN3-WKN-149_answer.zip", H / "FIN3-WKN-149_task.zip",
    H / "FIN3-WKN-150_answer.zip", H / "FIN3-WKN-150_task.zip",
    H / "FIN3-WKN-151_answer.zip", H / "FIN3-WKN-151_task.zip",
    H / "work_fin-b01_20261005_fix7-149.zip",
    H / "work_fin-b01_20261006-151.zip",
    H / "work_fin-b01_20261006_fix6-150.zip",
    H / "work_fin-b01_20261009_fix8-149.zip",
    H / "交付文档.md",
]
DIRS = [
    Q / "zips-before-fix5", Q / "zips-before-fix6",
    Q / "rejudge150-before-tighten-20261009-123649",
    Q / "rejudge150-final-20261009-170123",
    Q / "sync150-backup-20261009-164347",
    R / "_qc_runs" / "feishu-150-verify",
    R / "_qc_runs" / "feishu-151-dl",
    R / "_qc_runs" / "feishu-282-verify",
    H / "work_fin-b01_20261005_fix7-149",
    H / "work_fin-b01_20261006_fix6-150",
    H / "work_fin-b01_20261009_fix8-149",
    R / "deliverables" / "2026-10-09_harbor-weakness-149-二次返修" / "_backup_zips",
    R / ".workbuddy" / "tmp" / "feishu_dl",
    R / ".workbuddy" / "tmp" / "testzips",
]

APPLY = "--apply" in sys.argv


def size_of(p):
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


def files_of(p):
    if p.is_file():
        return 1
    return sum(1 for f in p.rglob("*") if f.is_file())


def main():
    print(f"模式: {'APPLY（实际删除）' if APPLY else 'DRY-RUN（只列出）'}\n")
    errors, total, nfiles = [], 0, 0

    for p in FILES + DIRS:
        name = p.name
        # 硬断言 1：受保护名称一律拒绝
        if name in PROTECTED:
            errors.append(f"受保护名称，拒绝删除: {p}")
            continue
        # 硬断言 2：必须位于预期根下的直接子项
        parents = {H, Q, R / "_qc_runs",
                   R / "deliverables" / "2026-10-09_harbor-weakness-149-二次返修",
                   R / ".workbuddy" / "tmp"}
        if p.parent not in parents:
            errors.append(f"父目录不在白名单，拒绝删除: {p}")
            continue
        # 硬断言 3：不存在就跳过（不报错）
        if not p.exists():
            print(f"  [跳过] 不存在: {p.relative_to(R)}")
            continue
        s, n = size_of(p), files_of(p)
        total += s
        nfiles += n
        kind = "文件" if p.is_file() else f"目录/{n} 文件"
        print(f"  [{'删除' if APPLY else '拟删'}] {str(p.relative_to(R)):<62} {kind:<12} {s/1048576:>8.2f} MB")
        if APPLY:
            if p.is_file():
                p.unlink()
            else:
                shutil.rmtree(p)

    print(f"\n合计 {len(FILES) + len(DIRS)} 项，{nfiles} 个文件，{total/1048576:.1f} MB")
    if errors:
        print("\n[ERR] 校验未通过：")
        for e in errors:
            print("   ", e)
        return 2
    if not APPLY:
        print("\n（DRY-RUN 结束；加 --apply 执行删除）")
    else:
        print("\n清理完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

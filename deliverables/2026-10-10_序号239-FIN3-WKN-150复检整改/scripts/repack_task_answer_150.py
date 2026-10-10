# -*- coding: utf-8 -*-
"""重建 FIN3-WKN-150 的「题目包」（task）与「标准答案包」（answer）。

对齐飞书作业表两个附件字段的口径：
    - 题目附件 `fldf8Ymaw2`   ← FIN3-WKN-150_task.zip    （题面 + 环境 + 判分定义，不含金标）
    - 标准答案附件 `fld2TmGhqt` ← FIN3-WKN-150_answer.zip （solve.sh + 两份 golden_output）

相对上一版（fix5 生成）的差异（对应复检报告第 5 条同源问题）：
    .sh 文件权限 0666 → **0755**；同时清理上一版误写的
    `FIN3-WKN-150/FIN3-WKN-150/...` 重复前缀空目录条目，顶层唯一且结构规范。
    文本类文件保持 LF 原样。

用法：
    python repack_task_answer_150.py --task-dir <题目目录> --out <输出目录>
"""
import argparse
import hashlib
import os
import pathlib
import zipfile

TASK = "FIN3-WKN-150"
MODE_DIR = 0o40755
MODE_EXEC = 0o100755
MODE_FILE = 0o100644
SKIP_DIRS = {"__pycache__", ".pytest_cache", "_rejudge"}

TASK_TOP = ["instruction.md", "rubrics.json", "task.toml", "environment"]
TASK_TESTS = ["finalize.py", "prompt.md", "rubrics.toml", "test.sh"]
ANS_TOP = ["solution", "tests"]
ANS_TESTS = ["__golden_output"]


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


TEXT_EXT = {".sh", ".py", ".toml", ".md", ".json", ".csv", ".txt"}


def collect(root, rel_items, tests_files=None, tests_sub=None):
    """返回 [(绝对路径, 相对题目目录的 posix 路径)]。

    tests_files: 仅收 `tests/` **根级**且在该白名单内的文件（题目包口径）；
    tests_sub  : 仅收 `tests/` 下该子目录内的文件（答案包口径）。
    """
    out = []
    for rel in rel_items:
        p = root / rel
        if p.is_file():
            out.append((p, rel))
            continue
        for dirpath, dirnames, filenames in os.walk(p):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            rel_dir = pathlib.Path(dirpath).relative_to(root)
            for f in sorted(filenames):
                if rel_dir.parts[0] == "tests":
                    if tests_files is not None:
                        if len(rel_dir.parts) != 1 or f not in tests_files:
                            continue
                    elif tests_sub is not None:
                        if len(rel_dir.parts) < 2 or rel_dir.parts[1] not in tests_sub:
                            continue
                out.append((pathlib.Path(dirpath) / f, (rel_dir / f).as_posix()))
    return out


def build(out_zip, files, dirs):
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        info = zipfile.ZipInfo(f"{TASK}/")
        info.external_attr = (MODE_DIR << 16) | 0x10
        zf.writestr(info, b"")
        for arc in sorted(dirs):
            info = zipfile.ZipInfo(f"{TASK}/{arc}/")
            info.external_attr = (MODE_DIR << 16) | 0x10
            zf.writestr(info, b"")
        for p, rel in files:
            arc = f"{TASK}/{rel}"
            info = zipfile.ZipInfo(arc, date_time=(2026, 10, 10, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (MODE_EXEC if p.suffix == ".sh" else MODE_FILE) << 16
            zf.writestr(info, p.read_bytes())
    zf = zipfile.ZipFile(out_zip)
    names = zf.namelist()
    tops = sorted({n.split("/")[0] for n in names})
    execs = {n: ((zf.getinfo(n).external_attr >> 16) & 0xFFFF) for n in names if n.endswith(".sh")}
    bad = [n for n, m in execs.items() if (m & 0o777) != 0o755]
    crlf = [n for n in names
            if not n.endswith("/") and pathlib.Path(n).suffix.lower() in TEXT_EXT and b"\r\n" in zf.read(n)]
    print(f"  {out_zip.name}: {out_zip.stat().st_size} B  sha256={sha256(out_zip)[:16]}  "
          f"files={sum(1 for n in names if not n.endswith('/'))} dirs={sum(1 for n in names if n.endswith('/'))}")
    print(f"    顶层={tops}  执行位={ {os.path.basename(n): f'{m & 0o777:o}' for n, m in execs.items()} }")
    print(f"    CRLF={crlf if crlf else '无'}  重复前缀={[n for n in names if n.startswith(f'{TASK}/{TASK}/')] or '无'}")
    return (not bad) and (not crlf) and (tops == [TASK])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task-dir", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    root = pathlib.Path(args.task_dir)
    if not (root / "solution" / "golden_output").is_dir():
        raise SystemExit(f"题目目录异常: {root}")
    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    t_files = collect(root, TASK_TOP) + collect(root, ["tests"], tests_files=set(TASK_TESTS))
    t_dirs = {"environment/input_files", "environment", "tests"}

    a_files = collect(root, ANS_TOP, tests_sub=set(ANS_TESTS))
    a_dirs = {"solution", "solution/golden_output", "solution/golden_output/FIN3-WKN-150_charts",
              "tests", "tests/__golden_output", "tests/__golden_output/FIN3-WKN-150_charts"}

    ok1 = build(out_dir / f"{TASK}_task.zip", sorted(set(t_files)), t_dirs)
    ok2 = build(out_dir / f"{TASK}_answer.zip", sorted(set(a_files)), a_dirs)
    if not (ok1 and ok2):
        print("!! 校验未通过")
        return 2
    print("两个附件包校验通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""按序号 239 / 2026-10-09 复检报告口径重新打包 FIN3-WKN-150（第四轮 fix6）。

相对上一轮 repack_150.py 的差异（对应复检报告第 5 条）：
    上一轮包内 `solution/solve.sh` 与 `tests/test.sh` 的 Unix 权限为 0666（无执行位），
    本轮统一写为 **0755**（目录 0755、`*.sh` 0755、其余普通文件 0644），并保持 LF 与目录结构。

归档树：
    <批次名>/
    └── FIN3-WKN-150/            ← 第二层唯一，即题目目录
        ├── instruction.md / task.toml / rubrics.json / environment / solution / tests
        ├── 交付文档.md
        └── 跑分产物与轨迹/

排除：`_rejudge/`、`__pycache__/`、`.pytest_cache/`、`.git/`、`.DS_Store`、`*.pyc`、`*.out`、`*.err`。

用法：
    python repack_150_fix6.py --batch <批次目录名> --name <包名> --out <目录>
"""
import argparse
import hashlib
import os
import pathlib
import zipfile

H = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
TASK = "FIN3-WKN-150"

SKIP_DIRS = {"_rejudge", "__pycache__", ".pytest_cache", ".git"}
SKIP_FILES = {".DS_Store"}
SKIP_EXT = {".pyc", ".out", ".err"}

MODE_DIR = 0o40755
MODE_EXEC = 0o100755
MODE_FILE = 0o100644
EXEC_SUFFIX = {".sh"}


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    batch_dir = H / args.batch
    if not batch_dir.is_dir():
        raise SystemExit(f"批次目录不存在: {batch_dir}")
    if not (batch_dir / TASK).is_dir():
        raise SystemExit(f"批次内缺题目目录: {batch_dir / TASK}")

    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_zip = out_dir / f"{args.name}.zip"

    files, dirs = [], []
    for dirpath, dirnames, filenames in os.walk(batch_dir):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        rel_dir = pathlib.Path(dirpath).relative_to(batch_dir)
        if str(rel_dir) != ".":
            dirs.append(f"{args.name}/{rel_dir.as_posix()}/")
        for f in sorted(filenames):
            if f in SKIP_FILES or pathlib.Path(f).suffix in SKIP_EXT:
                continue
            p = pathlib.Path(dirpath) / f
            rel = p.relative_to(batch_dir)
            files.append((p, f"{args.name}/{rel.as_posix()}"))

    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for arc in sorted(dirs):
            info = zipfile.ZipInfo(arc)
            info.external_attr = (MODE_DIR << 16) | 0x10
            zf.writestr(info, b"")
        for p, arc in files:
            mode = MODE_EXEC if p.suffix in EXEC_SUFFIX else MODE_FILE
            info = zipfile.ZipInfo(arc, date_time=(2026, 10, 10, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = mode << 16
            zf.writestr(info, p.read_bytes())

    zf = zipfile.ZipFile(out_zip)
    names = zf.namelist()
    tops = sorted({n.split("/")[0] for n in names})
    second = sorted({n.split("/")[1] for n in names if n.count("/") >= 1 and n.split("/")[1]})
    leaked = [n for n in names if "/_rejudge/" in n or n.endswith(".pyc") or n.endswith(".out")]
    modes = {}
    crlf = []
    for n in names:
        if n.endswith("/"):
            continue
        info = zf.getinfo(n)
        modes[n] = (info.external_attr >> 16) & 0xFFFF
        if n.endswith((".sh", ".py", ".toml", ".md")) and b"\r\n" in zf.read(n):
            crlf.append(n)

    key = [n for n in names if n.endswith("solution/solve.sh") or n.endswith("tests/test.sh")]
    print(f"zip      : {out_zip}")
    print(f"size     : {out_zip.stat().st_size} B")
    print(f"sha256   : {sha256(out_zip)}")
    print(f"entries  : {len(names)}  (files={len(files)} dirs={len(dirs)})")
    print(f"顶层     : {tops}")
    print(f"第二层   : {second}")
    print(f"禁入项   : {leaked if leaked else '无'}")
    print("执行位   :")
    ok = True
    for n in key:
        m = modes[n] & 0o777
        flag = "OK" if m == 0o755 else "!!"
        ok &= m == 0o755
        print(f"  {flag} {m:o}  {n}")
    others = sorted({m & 0o777 for n, m in modes.items() if not n.endswith(".sh")})
    print(f"其他文件权限集合: {[f'{m:o}' for m in others]}（应为 644）")
    print(f"CRLF 残留: {crlf if crlf else '无'}")
    if len(tops) != 1 or TASK not in second or leaked or not ok or crlf:
        print("!! 打包校验未通过")
        return 2
    print("打包校验通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

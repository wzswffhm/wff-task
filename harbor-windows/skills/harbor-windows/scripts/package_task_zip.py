# -*- coding: utf-8 -*-
"""package_task_zip.py —— 把 harbor-windows 题包打成平台交付 ZIP

ZIP 名 = `<task-id>-v<题目版本>-delivery.zip`，ZIP 根 = **同名目录**（与飞书交付附件逐字一致；
解压到 `harbor-windows/` 即落到与附件名相同的目录名下），包含：

    <task-id>-v<版本>-delivery/instruction.md
    <task-id>-v<版本>-delivery/task.toml
    <task-id>-v<版本>-delivery/source.json      # 甲方 QC checklist 必备（来源/授权/谱系）
    <task-id>-v<版本>-delivery/environment/**
    <task-id>-v<版本>-delivery/tests/**         # 含 required_testcases.json（甲方 QC 必备）
    <task-id>-v<版本>-delivery/solution/**      # 甲方 QC checklist 必备：Golden 入口，必须交付
    <task-id>-v<版本>-delivery/jobs/**          # 作业记录（agent/ + verifier/），可用 --no-jobs 排除

> `task-id` 一律取自 `task.toml` 的 `[metadata].task_id`，**不要**用本地目录名派生：
> 本地目录名已含版本与 `-delivery` 后缀（如 `wfflab__wchunk-216-v1.2.0-delivery`），
> 用目录名拼名字会得到 `<id>-v<版本>-delivery-v<版本>` 这种版本号重复的错误结果。

> ⚠️ 甲方 `windows-harbor-qc` checklist 第 1 节明确：**`solution/` 必须随组织方题包交付**
> （"不能因为普通 Agent 不应看到它就把组织方题包里的参考解删掉"），`source.json` 与
> `tests/required_testcases.json` 同样是必备件。**不要**再把它们排除。

**排除**（不得进入交付 ZIP）：

| 类别 | 条目 | 为什么 |
|---|---|---|
| 题外伴随材料 | `extras/`、`environment/evidence/**` | 历史判分沙箱副本会污染甲方静态检查；证据属 `delivery-extras/`，不是题包内容 |
| 整改过程文档 | `REFIT-*.md` | 返修记录，会被甲方引为"包内自述"，且 219 的 F6 命中正来自它 |
| 自述类说明 | `verifier/WINDOWS_VALUE.md` | 价值主张说明属过程材料；F6 判据就扫它，不该随包外发 |
| 参考解补丁 | `solution/oracle.patch` | 与 `solution/reference/**` + `solve.ps1` 重复；旧形态残留 |
| 缓存/凭据 | `__pycache__/`、`.pytest_cache/`、`*.pyc`、`.DS_Store` | 平台校验与泄漏门禁均不接受 |

**出包前自检（命中即拒绝出包，退出码 2）**：

1. 必备件齐全（`source.json` / `solution/README.md` / `solution/solve.ps1|solve.bat` /
   `tests/required_testcases.json`）；
2. ZIP 内不得含禁入内容（上表）；
3. **自我否认 Windows 价值表述扫描**：对**整个题包**（不只是将被打包的部分）跑
   `self_denial_scan.scan_self_denial`，命中即拒发并打印 `文件:行号`。
   这条与 `check_windows_mechanism.py` 的 F6 共享同一实现 —— 门禁与打包必须同口径。

用法：
    python package_task_zip.py --task-dir harbor-windows/wfflab__wreparse-217 --out-dir out/
    python package_task_zip.py --task-dir ... --out-dir out/ --no-jobs
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import os
import sys
import zipfile
from pathlib import Path

# 脚本按文件路径并列存放：就地导入共享的自我否认扫描实现（与 F6 同源）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from self_denial_scan import format_hits, scan_self_denial  # noqa: E402

SKIP_DIRS = {"extras", "__pycache__", ".pytest_cache", ".git", ".mypy_cache"}
SKIP_FILES = {".DS_Store"}

# 目录级禁入（相对题包根，POSIX 形式）
BANNED_REL_DIRS = ("environment/evidence",)
# 文件级禁入（相对题包根，支持 `*` 通配）
BANNED_REL_FILES = ("REFIT-*.md", "verifier/WINDOWS_VALUE.md", "solution/oracle.patch")


def skip_dir(name: str) -> bool:
    return name in SKIP_DIRS


def skip_file(name: str) -> bool:
    return name in SKIP_FILES or name.endswith(".pyc")


def _rel_posix(path: Path, task_dir: Path) -> str:
    return path.relative_to(task_dir).as_posix()


def banned_rel_path(rel: str) -> bool:
    """rel 为相对题包根的 POSIX 路径；命中即不得进入交付 ZIP。"""
    for banned_dir in BANNED_REL_DIRS:
        if rel == banned_dir or rel.startswith(banned_dir + "/"):
            return True
    for pattern in BANNED_REL_FILES:
        if fnmatch.fnmatch(rel, pattern):
            return True
        # 允许题包内再套一层（例如解压后多一层目录）时仍能命中同名文件
        if pattern.startswith("*/") and fnmatch.fnmatch(rel, pattern):
            return True
    return False


def banned_rel_dir(rel: str) -> bool:
    for banned_dir in BANNED_REL_DIRS:
        if rel == banned_dir or rel.startswith(banned_dir + "/"):
            return True
    return False


def scan_denial(task_dir: Path) -> list[dict]:
    """出包前的自我否认表述扫描（复用 F6 的共享实现）。"""
    return scan_self_denial(task_dir)


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_task_id(task_dir: Path) -> str | None:
    """从 task.toml 的 [metadata].task_id 读取权威 task id（交付文件名必须与之一致）。"""
    section = ""
    for raw in (task_dir / "task.toml").read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line.strip("[]").strip()
            continue
        if section == "metadata" and "=" in line:
            key, value = line.split("=", 1)
            if key.strip() == "task_id":
                return value.strip().strip('"').strip("'")
    return None


def collect(task_dir: Path, include_jobs: bool, root_name: str) -> list[tuple[Path, str]]:
    """返回 (绝对路径, zip 内相对路径) 列表；空目录以 (目录, 'dir/') 形式登记。

    root_name = ZIP 名去 `.zip`（由 task_id + 版本派生），**不要**用 task_dir.name。

    禁入名单（`BANNED_REL_DIRS` / `BANNED_REL_FILES`）在这里生效：
    `REFIT-*.md`、`verifier/WINDOWS_VALUE.md`、`solution/oracle.patch`、
    `environment/evidence/**` 一律不进交付 ZIP。
    """
    entries: list[tuple[Path, str]] = []

    for dirpath, dirnames, filenames in os.walk(task_dir):
        current = Path(dirpath)
        rel_dir = current.relative_to(task_dir)

        if not include_jobs and rel_dir.parts[:1] == ("jobs",):
            dirnames[:] = []
            continue

        rel_dir_posix = rel_dir.as_posix()
        if rel_dir_posix != "." and banned_rel_dir(rel_dir_posix):
            dirnames[:] = []
            continue

        kept_dirs = []
        for d in dirnames:
            child_rel = d if rel_dir_posix == "." else f"{rel_dir_posix}/{d}"
            if skip_dir(d) or banned_rel_dir(child_rel):
                continue
            kept_dirs.append(d)
        dirnames[:] = sorted(kept_dirs)

        files = sorted(f for f in filenames if not skip_file(f))

        if not dirnames and not files:
            arc = f"{root_name}/{rel_dir.as_posix().rstrip('/')}/"
            entries.append((current, arc))
            continue

        for f in files:
            rel = f if rel_dir_posix == "." else f"{rel_dir_posix}/{f}"
            if banned_rel_path(rel):
                continue
            arc = f"{root_name}/{rel}"
            entries.append((current / f, arc))

    return entries


def main() -> int:
    ap = argparse.ArgumentParser(description="harbor-windows 题包交付 ZIP 打包")
    ap.add_argument("--task-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--suffix", default=None, help="ZIP 名后缀（默认用 task_version，需 --version）")
    ap.add_argument("--version", default=None, help="task_version，用于默认文件名")
    ap.add_argument("--no-jobs", action="store_true", help="不打包 jobs/")
    ap.add_argument("--verify", action="store_true", help="打包后解包逐文件核对 sha256")
    args = ap.parse_args()

    task_dir = Path(args.task_dir).resolve()
    if not (task_dir / "task.toml").is_file():
        raise SystemExit(f"不是题包目录（缺 task.toml）：{task_dir}")

    version = args.version
    if version is None:
        # task.toml 里有两处 version：顶层 = 平台 schema 版本，[task].version = 题目版本。
        # 交付文件名用**题目版本**。
        section = ""
        top_version = None
        task_version = None
        for raw in (task_dir / "task.toml").read_text(encoding="utf-8").splitlines():
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            if line.startswith("[") and line.endswith("]"):
                section = line.strip("[]").strip()
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() != "version":
                continue
            value = value.strip().strip('"').strip("'")
            if section == "task":
                task_version = value
            elif not section:
                top_version = value
        version = task_version or top_version
    version = version or "1.0.0"

    task_id = read_task_id(task_dir)
    if not task_id:
        raise SystemExit(f"task.toml 缺 [metadata].task_id，无法确定交付文件名：{task_dir}")

    # 交付包名 = <task-id>-v<题目版本>-delivery；与飞书附件名（去 .zip）逐字一致（见铁律四）
    bundle = f"{task_id}-v{version}-delivery"

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_zip = out_dir / f"{bundle}.zip"

    # 包内自认句扫描：放在写 ZIP **之前**，命中即拒发（避免留下一个不该存在的产物）
    denial_hits = scan_denial(task_dir)
    if denial_hits:
        print("!! 题包内出现自我否认 Windows 价值的表述，拒绝打包（F6 同口径）：")
        for hit in denial_hits:
            print(f"   - {hit['file']}:{hit['line']}  {hit['why']}")
            print(f"       {hit['text']}")
        print(f"   合计 {len(denial_hits)} 处：{format_hits(denial_hits)}")
        print("   处置：要么给题注入真实 Windows 机制后发新版，要么按甲方口径移出 Windows 池；"
              "删掉那句话不算整改（判据在题面与测试里，甲方下一轮照样判不合格）。")
        return 2

    entries = collect(task_dir, include_jobs=not args.no_jobs, root_name=bundle)
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, arc in entries:
            if path.is_dir():
                info = zipfile.ZipInfo(arc)
                info.external_attr = (0o40755 << 16) | 0x10
                zf.writestr(info, b"")
            else:
                zf.write(path, arc)

    digest = sha256_of(out_zip)
    size = out_zip.stat().st_size
    names = zipfile.ZipFile(out_zip).namelist()
    jobs_n = sum(1 for n in names if "/jobs/" in n)

    print(f"zip       : {out_zip}")
    print(f"size      : {size} B")
    print(f"sha256    : {digest}")
    print(f"entries   : {len(names)}（其中 jobs 条目 {jobs_n}）")
    print(f"jobs 打包 : {'否' if args.no_jobs else '是'}")

    # 甲方 windows-harbor-qc checklist 必备件：缺失即拒发（避免再打出被 QC 判 FAIL 的包）
    root_name = bundle
    required = ["source.json", "solution/README.md", "tests/required_testcases.json"]
    missing = [f"{root_name}/{r}" for r in required if f"{root_name}/{r}" not in names]
    if not any(f"{root_name}/solution/{s}" in names for s in ("solve.ps1", "solve.bat")):
        missing.append(f"{root_name}/solution/solve.ps1|solve.bat")
    if missing:
        print("!! 交付 ZIP 缺甲方 QC 必备件，拒绝打包：")
        for n in missing:
            print(f"   - {n}")
        return 2

    leaked = [
        n
        for n in names
        if n.startswith(f"{root_name}/extras/") or "/__pycache__/" in n or n.endswith(".pyc")
    ]
    if leaked:
        print("!! 交付 ZIP 含禁入内容：")
        for n in leaked:
            print(f"   - {n}")
        return 2

    # 二次防线：即使禁入名单有漏，压缩出来的条目也必须全部合规
    banned_entries = [n for n in names
                      if banned_rel_path(n[len(root_name) + 1:]) and not n.endswith("/")]
    if banned_entries:
        print("!! 交付 ZIP 含禁入名单内的条目，拒绝打包：")
        for n in banned_entries:
            print(f"   - {n}")
        return 2

    if args.verify:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            with zipfile.ZipFile(out_zip) as zf:
                zf.extractall(tmp)
            base = Path(tmp) / bundle
            bad: list[str] = []
            checked = 0
            for path, arc in entries:
                if path.is_dir():
                    if not (Path(tmp) / arc).is_dir():
                        bad.append(f"缺目录 {arc}")
                    continue
                target = Path(tmp) / arc
                if not target.is_file():
                    bad.append(f"缺文件 {arc}")
                    continue
                if sha256_of(path) != sha256_of(target):
                    bad.append(f"哈希不符 {arc}")
                checked += 1
            print(f"verify    : 核对 {checked} 个文件" + ("，全部一致" if not bad else "，存在问题："))
            for b in bad:
                print(f"   - {b}")
            if bad:
                return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

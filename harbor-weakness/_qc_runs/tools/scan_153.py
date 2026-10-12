# -*- coding: utf-8 -*-
"""FIN3-WKN-153 题包全量静态扫描（本地等效自检，不替代 G4/G5）。"""
import hashlib
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

H = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
BATCH = H / "work_fin-b01_20261012-153"
TASK_DIR = BATCH / "FIN3-WKN-153"
TASK = "FIN3-WKN-153"

BAD_DIRS = {".git", "__pycache__", ".venv", "__MACOSX", ".pytest_cache", "logs", "jobs"}
BAD_FILES = {".DS_Store"}
SECRET_PAT = re.compile(r"(sk-[A-Za-z0-9_\-\.]{12,}|Bearer\s+[A-Za-z0-9_\-\.]{12,})")
INVIS = re.compile(r"[\u00a0\u3000]")

fails, warns, stats = [], [], {}


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def text_files(root):
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() in (".md", ".toml", ".json", ".csv", ".txt", ".py", ".sh"):
            yield p


def main():
    files = [p for p in TASK_DIR.rglob("*") if p.is_file()]
    dirs = [p for p in TASK_DIR.rglob("*") if p.is_dir()]
    stats["files"] = len(files)
    stats["dirs"] = len(dirs)
    stats["size_mb"] = round(sum(p.stat().st_size for p in files) / 1024 / 1024, 2)

    # 1) 残留
    for p in list(files) + list(dirs):
        if p.name in BAD_DIRS or p.name in BAD_FILES:
            fails.append(f"残留: {p.relative_to(BATCH).as_posix()}")
        if re.fullmatch(r"reward.*\.json", p.name):
            fails.append(f"残留 reward 文件: {p.relative_to(BATCH).as_posix()}")
    # 2) 不可见空白 / CRLF / 密钥 / 文件名
    for p in text_files(TASK_DIR):
        rel = p.relative_to(BATCH).as_posix()
        raw = p.read_bytes()
        txt = raw.decode("utf-8", errors="replace")
        if INVIS.search(txt):
            fails.append(f"不可见空白: {rel}")
        if p.suffix in (".sh",) and b"\r\n" in raw:
            fails.append(f"CRLF: {rel}")
        m = SECRET_PAT.search(txt)
        if m and "ANTHROPIC_AUTH_TOKEN" not in txt[:0]:
            warns.append(f"疑似密钥: {rel} -> {m.group(0)[:18]}...")
        for part in p.relative_to(TASK_DIR).parts:
            if len(part.encode("utf-8")) > 200:
                fails.append(f"文件名超长: {rel}")
    # 3) 符号链接
    for p in TASK_DIR.rglob("*"):
        if p.is_symlink():
            fails.append(f"符号链接: {p.relative_to(BATCH).as_posix()}")

    # 4) golden 双份一致
    g1 = TASK_DIR / "solution" / "golden_output"
    g2 = TASK_DIR / "tests" / "__golden_output"
    s1 = {p.name: sha256(p) for p in sorted(g1.iterdir()) if p.is_file()}
    s2 = {p.name: sha256(p) for p in sorted(g2.iterdir()) if p.is_file()}
    if s1 != s2:
        fails.append(f"golden 双份不一致: {set(s1) ^ set(s2)} / 哈希差异 "
                     f"{[k for k in s1 if s1.get(k) != s2.get(k)]}")
    stats["golden_files"] = len(s1)

    # 5) 交付物文件名四处一致
    task_toml = (TASK_DIR / "task.toml").read_text(encoding="utf-8")
    inst = (TASK_DIR / "instruction.md").read_text(encoding="utf-8")
    rubrics = (TASK_DIR / "tests" / "rubrics.toml").read_text(encoding="utf-8")
    arts = re.findall(r'"(/app/output/' + TASK + r'_[^"]+)"', task_toml)
    dels = re.findall(r'path = "(' + TASK + r'_[^"]+)"', task_toml)
    names = {p.split("/")[-1] for p in arts}
    if names != set(dels):
        fails.append(f"artifacts 与 deliverables 不一致: {names ^ set(dels)}")
    for n in sorted(names):
        if n not in inst:
            fails.append(f"instruction 未列出: {n}")
        if n not in rubrics:
            fails.append(f"rubrics 未提及: {n}")
        if not (g1 / n).is_file():
            fails.append(f"golden 缺交付物: {n}")
    stats["deliverables"] = len(names)

    # 6) JUDGE_ 未泄漏到 [environment].env
    env_block = task_toml.split("[environment]")[-1]
    if "JUDGE_" in env_block:
        fails.append("[environment] 段出现 JUDGE_ 变量")
    # 7) 输入材料只读约束存在
    dockerfile = (TASK_DIR / "environment" / "Dockerfile").read_text(encoding="utf-8")
    if "chmod -R a-w /app/input_files" not in dockerfile:
        fails.append("Dockerfile 缺输入材料只读设置")

    print("== 统计 ==")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print("== FAIL ==")
    print("\n".join(f"  {f}" for f in fails) if fails else "  无")
    print("== 提示 ==")
    print("\n".join(f"  {w}" for w in warns) if warns else "  无")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())

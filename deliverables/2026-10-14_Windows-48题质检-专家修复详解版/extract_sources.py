# -*- coding: utf-8 -*-
"""把 sources-<key>.html 中的源码选段还原成文件树。

用法: python extract_sources.py <key> [<key> ...] [--all] [--root <dir>]

默认只还原交付主体文件（task.toml / source.json / instruction.md /
environment/** / tests/** / solution/**），跳过 jobs/** 与 _index/**。
加 --all 则全部还原。
"""
import io, os, re, sys, html as htmlmod

SRC = r"C:\Users\Administrator\Desktop\Windows-48题质检-专家修复详解版-20261012\evidence"
BASE_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "extracted")

KEEP_PREFIXES = ("task.toml", "source.json", "instruction.md",
                 "environment/", "tests/", "solution/", "verifier/")
DROP_PREFIXES = ("jobs/", "_index/", "_qc/", "outside_harbor/", "delivery-extras/")

PANEL_RE = re.compile(r'<section class="panel filterable" id="(s[0-9a-f]+)"><h3>(.*?)</h3>')
# 包内相对路径的起点标记：第一个出现的交付主体目录/文件
START_RE = re.compile(r'(?:^|/)(task\.toml|source\.json|instruction\.md|environment|tests|solution|verifier|jobs|_index|_qc|outside_harbor[^/]*|delivery-extras)(?:/|$)')
META_RE = re.compile(r'<p class="meta">(.*?)</p>')
LINE_RE = re.compile(r'<div class="source-line" id="s[0-9a-f]+-L\d+"><a class="ln"[^>]*>\d+</a>(.*?)</div>')


def clean(txt: str) -> str:
    txt = re.sub(r"<[^>]+>", "", txt)
    return htmlmod.unescape(txt)


def extract(key: str, keep_all: bool, root: str):
    path = os.path.join(SRC, f"sources-{key}.html")
    if not os.path.exists(path):
        print(f"[skip] sources-{key}.html 不存在")
        return 0
    with io.open(path, "r", encoding="utf-8") as f:
        doc = f.read()

    matches = list(PANEL_RE.finditer(doc))
    written = 0
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(doc)
        chunk = doc[start:end]
        rel = clean(m.group(2)).strip()
        # rel 形如 "019/win-fs-001-jobs-qcpass/tests/run_tests.ps1"；
        # 从第一个交付主体目录/文件处截断，得到包内相对路径
        sm = START_RE.search(rel)
        if not sm:
            continue
        relpath = rel[sm.start(1):]
        # 反复剥离包装目录（outside_harbor-assets/<task-id>/、同名双层等），
        # 直到路径以交付主体前缀开头
        while not relpath.startswith(KEEP_PREFIXES + DROP_PREFIXES):
            seg, sep, rest = relpath.partition("/")
            if not sep:
                break
            relpath = rest
        if not keep_all:
            if relpath.startswith(DROP_PREFIXES):
                continue
            if not relpath.startswith(KEEP_PREFIXES):
                continue
        meta_m = META_RE.search(chunk)
        meta = clean(meta_m.group(1)) if meta_m else ""
        if "全文" not in meta:
            # 只保留全文摘录，轨迹类截断内容跳过
            if not keep_all:
                continue
        lines = [clean(x) for x in LINE_RE.findall(chunk)]
        if not lines:
            continue
        out_path = os.path.join(root, key, relpath.replace("/", os.sep))
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with io.open(out_path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
        written += 1
    print(f"[{key}] 还原 {written} 个文件 -> {os.path.join(root, key)}")
    return written


def main():
    args = sys.argv[1:]
    keep_all = "--all" in args
    args = [a for a in args if a != "--all"]
    root = BASE_OUT
    if "--root" in args:
        i = args.index("--root")
        root = args[i + 1]
        del args[i:i + 2]
    if not args:
        print(__doc__)
        return
    for key in args:
        extract(key, keep_all, root)


if __name__ == "__main__":
    main()

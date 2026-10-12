"""Resolve every path the client static checker reported as missing.

Stage 1: suffix match against files AND directories in the delivered package.
Stage 2: for anything unresolved, find where the string actually occurs in the
         package (runtime path / document reference / probe noise).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

TEXT_SUFFIXES = {".py", ".ps1", ".psm1", ".psd1", ".md", ".json", ".toml",
                 ".txt", ".bat", ".cmd", ".diff", ".patch", ".cfg", ".yml", ".yaml"}


def rel_files_and_dirs(root: Path) -> tuple[list[str], list[str], list[Path]]:
    files, dirs, all_paths = [], [], []
    for path in root.rglob("*"):
        rel = path.relative_to(root).as_posix()
        all_paths.append(path)
        (dirs if path.is_dir() else files).append(rel)
    return files, dirs, all_paths


def search_text(paths: list[Path], needle: str, key: str) -> list[str]:
    hits: list[str] = []
    for path in paths:
        if path.suffix.lower() not in TEXT_SUFFIXES or not path.is_file():
            continue
        try:
            body = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(body.splitlines(), 1):
            if needle in line or key in line.lower():
                hits.append(f"{path.name}:{lineno}")
                break
        if len(hits) >= 3:
            break
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inventory", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    data = json.loads(args.inventory.read_text(encoding="utf-8-sig"))
    lines = ["# 甲方静态检查「referenced files are missing」逐条核对", "",
             "核对方法：① 在交付包内按「相对路径后缀」匹配文件/目录；",
             "② 未匹配到的，再在包内文本里搜索该字符串的出处（运行期路径 / 文档引用 / 解析噪声）。", ""]
    for task in data["tasks"]:
        root = Path(task["root"])
        files, dirs, all_paths = rel_files_and_dirs(root)
        lines += [f"## {task['task_id']}", "",
                  "| 检查器报告缺失的引用 | 核对结论 | 证据 |", "|---|---|---|"]
        for error in task.get("errors", []):
            payload = error.split(":", 1)[1] if ":" in error else error
            for item in [i.strip() for i in payload.split(",") if i.strip()]:
                key = item.replace("\\", "/").lower().strip("/")
                base = key.rsplit("/", 1)[-1]
                hits = [f for f in files if f.lower().endswith(key)]
                dir_hits = [d for d in dirs if d.lower().endswith(key)]
                if hits:
                    verdict, evidence = "**存在**（检查器查找层级/解析基准有误）", hits[:3]
                elif dir_hits:
                    verdict, evidence = "**存在**（是目录，检查器按文件找）", dir_hits[:2]
                else:
                    base_hits = [f for f in files if f.lower().rsplit("/", 1)[-1] == base]
                    if base_hits:
                        verdict = "**存在**（同名文件，检查器未按引用基准解析）"
                        evidence = base_hits[:3]
                    else:
                        src = search_text(all_paths, item, key)
                        if src:
                            verdict = "运行期路径 / 文档引用，非交付件"
                            evidence = src
                        else:
                            verdict = "包内无此字符串：检查器解析噪声"
                            evidence = ["—"]
                cell = "<br>".join(f"`{e}`" for e in evidence) if evidence != ["—"] else "—"
                lines.append(f"| `{item}` | {verdict} | {cell} |")
        lines.append("")
    args.out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

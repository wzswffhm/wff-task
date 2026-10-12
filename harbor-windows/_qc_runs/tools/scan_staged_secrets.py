# -*- coding: utf-8 -*-
"""scan_staged_secrets.py —— 提交前扫描暂存区里的凭据样式串。

只读 `git diff --cached --name-only` 列出的文本文件，不修改任何东西。
二进制扩展名（zip/png/whl/exe/zip 内载荷等）跳过。

用法：python scan_staged_secrets.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\wff-task")
BINARY_EXT = {".zip", ".png", ".jpg", ".jpeg", ".whl", ".exe", ".gz", ".7z", ".pyc",
              ".wlsg", ".wfmt", ".wchk", ".dll", ".so", ".bin"}
PATTERNS = [
    ("openai/中转 sk- key", re.compile(r"sk-[A-Za-z0-9._\-]{20,}")),
    ("volcengine ark key", re.compile(r"ark-[0-9a-fA-F\-]{20,}")),
    ("aliyun LTAI key", re.compile(r"LTAI[A-Za-z0-9]{10,}")),
    ("bearer token", re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{20,}")),
    ("key/token 赋值", re.compile(r"(?i)(api[_-]?key|apikey|secret|password|passwd|access[_-]?token)"
                                 r"\s*[:=]\s*[\"']?[A-Za-z0-9._\-]{20,}")),
    ("x-api-key 头", re.compile(r"(?i)x-api-key[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9._\-]{20,}")),
]
# 已知非凭据的说明性文本含 "api-key" 字样，按行排除
ALLOWLINE = re.compile(r"(?i)(redacted|<key>|api_key_env|api-key is blocked|凭据|API key)")
# 文件名噪声：飞书表里形如 "...-task-env-001-qc-pass-20261010.zip" 的字段值，
# 词内会出现 "sk-env" / "sk-xml" 这类片段，不是密钥。
NOISE_LINE = re.compile(r"\.zip")


def staged_files() -> list[str]:
    p = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=str(ROOT),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return [ln.strip() for ln in (p.stdout or "").splitlines() if ln.strip()]


def main() -> int:
    hits = []
    noise = 0
    scanned = 0
    for rel in staged_files():
        p = ROOT / rel
        if not p.is_file() or p.suffix.lower() in BINARY_EXT:
            continue
        if p.stat().st_size > 4 * 1024 * 1024:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        scanned += 1
        for lineno, line in enumerate(text.splitlines(), 1):
            if ALLOWLINE.search(line):
                continue
            for name, rx in PATTERNS:
                m = rx.search(line)
                if m:
                    if NOISE_LINE.search(line) and m.group(0).lower().startswith("sk-"):
                        noise += 1
                        continue
                    hits.append((rel, lineno, name, m.group(0)[:70]))
    print("scanned text files: %d" % scanned)
    print("按文件名噪声忽略：%d 处（形如 ...-task-env-001-...zip）" % noise)
    if not hits:
        print("未发现凭据样式串 ✔")
        return 0
    print("疑似命中 %d 处：" % len(hits))
    for rel, lineno, name, sample in hits:
        print("  %s:%d  [%s]  %s" % (rel, lineno, name, sample))
    return 1


if __name__ == "__main__":
    sys.exit(main())

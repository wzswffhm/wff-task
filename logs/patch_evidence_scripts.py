# -*- coding: utf-8 -*-
"""patch_evidence_scripts.py -- 把 219 证据脚本的硬编码路径改成可配置的相对路径。

用法：
    python patch_evidence_scripts.py --dir <verifier/evidence>

替换规则：
  * 旧的绝对 ASSETS / ZIP 常量改为 `_resolve_assets()` + `_resolve_zip()`，
    支持 `--assets` / `--zip` 参数与环境变量 `WPEIMG_ASSETS` / `WPEIMG_ZIP`，
    默认回退到包内 `environment/workspace/assets`（相对本文件）。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HELPER = '''
def _package_root():
    """本文件位于 <pkg>/verifier/evidence/，包根是上溯三层。"""
    return Path(__file__).resolve().parents[2]


def _resolve_assets() -> Path:
    """定位权威样本目录：--assets > WPEIMG_ASSETS > 包内 workspace/assets。"""
    import os
    override = os.environ.get("WPEIMG_ASSETS")
    if override:
        return Path(override)
    return _package_root() / "environment" / "workspace" / "assets"


def _resolve_zip() -> Path:
    """定位内置 python embed 发行包：--zip > WPEIMG_ZIP > 包内 vendor。"""
    import os
    override = os.environ.get("WPEIMG_ZIP")
    if override:
        return Path(override)
    return _package_root() / "environment" / "vendor" / "python-3.12.9-embed-amd64.zip"
'''

# 旧的绝对路径常量：从 `ZIP = Path(` 起，到匹配的 `)` 结束
ZIP_CONST = re.compile(r"ZIP = (?:pathlib\.)?Path\((?:[^()]|\([^()]*\))*?\)\n", re.S)
ASSETS_CONST = re.compile(r"ASSETS = (?:pathlib\.)?Path\((?:[^()]|\([^()]*\))*?\)\n", re.S)
TMP_CONST = re.compile(r"TMP = (?:pathlib\.)?Path\((?:[^()]|\([^()]*\))*?\)\n", re.S)


def patch(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text
    if "ZIP = Path(" in text:
        text = ZIP_CONST.sub('ZIP = _resolve_zip()  # noqa: F821 (bound in main)\n', text, count=1)
    if "ASSETS = Path(" in text:
        text = ASSETS_CONST.sub('ASSETS = _resolve_assets()  # noqa: F821 (bound in main)\n', text, count=1)
    if re.search(r"^TMP = (?:pathlib\.)?Path\(", text, re.M):
        text = TMP_CONST.sub('TMP = _resolve_assets().parent / "_evidence-tmp"\n', text, count=1)
        text = text.replace(
            'def _resolve_zip() -> Path:',
            'def _resolve_tmp() -> Path:\n'
            '    """证据脚本的临时目录：包内 workspace 旁边的 _evidence-tmp。"""\n'
            '    return _resolve_assets().parent / "_evidence-tmp"\n\n\n'
            'def _resolve_zip() -> Path:', 1)
        text = text.replace('TMP = _resolve_assets().parent / "_evidence-tmp"\n',
                            'TMP = _resolve_tmp()  # noqa: F821 (bound in main)\n', 1)
    if text == original:
        print("  %-28s unchanged" % path.name)
        return False
    # 插到 `from __future__` / 首个 import 块之后
    match = re.search(r"^(from __future__ import[^\n]*\n)?((?:import [^\n]*\n|from [^\n]*\n)+)", text, re.M)
    if not match:
        print("  FAIL %s: no import block" % path.name)
        return False
    insert_at = match.end()
    text = text[:insert_at] + HELPER + text[insert_at:]
    path.write_text(text, encoding="utf-8", newline="\n")
    print("  %-28s patched" % path.name)
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    a = ap.parse_args()
    d = Path(a.dir)
    for name in ("authoritative.py", "checksum_experiment.py", "select_pe_assets.py",
                 "probe_overlay.py"):
        p = d / name
        if not p.is_file():
            print("  missing", name)
            return 1
        patch(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())

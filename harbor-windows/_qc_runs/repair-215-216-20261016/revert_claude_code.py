# -*- coding: utf-8 -*-
"""撤回 Claude Code：从两包 vendor / Dockerfile / INVENTORY 中移除。"""
from __future__ import annotations

import json
import pathlib
import shutil

HW = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows")
PKGS = ["wfflab__wsparse-215-v1.0.1-delivery", "wfflab__wvas-216-v1.0.1-delivery"]


def main() -> int:
    for pkg in PKGS:
        root = HW / pkg

        df = root / "environment" / "Dockerfile"
        text = df.read_text(encoding="utf-8")
        start = text.find("# --- 4b. Claude Code agent runtime")
        end = text.find("# --- 5. Workspace injection")
        if start != -1 and end != -1 and start < end:
            df.write_text(text[:start] + text[end:], encoding="utf-8")
            print(f"{pkg}: Dockerfile reverted")
        else:
            print(f"{pkg}: Dockerfile 4b block not found (start={start}, end={end})")

        inv = root / "environment" / "vendor" / "INVENTORY.json"
        doc = json.loads(inv.read_text(encoding="utf-8"))
        before = len(doc.get("files", []))
        doc["files"] = [f for f in doc.get("files", []) if f.get("path") != "claude-code/"]
        doc.get("sources", {}).pop("claude-code/", None)
        inv.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{pkg}: INVENTORY files {before} -> {len(doc['files'])}")

        target = root / "environment" / "vendor" / "claude-code"
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
            print(f"{pkg}: removed {target.name}")

        size = sum(p.stat().st_size for p in (root / "environment" / "vendor").rglob("*") if p.is_file())
        print(f"{pkg}: vendor now {size/1048576:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

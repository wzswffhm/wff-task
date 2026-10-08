"""Targeted search for real (non-placeholder) model/judge endpoint configs."""
import pathlib
import re

ROOTS = [
    pathlib.Path(r"C:\Users\Administrator\Desktop"),
    pathlib.Path(r"C:\Users\Administrator\Downloads"),
    pathlib.Path(r"C:\Users\Administrator\Documents"),
]
EXTS = {".env", ".txt", ".md", ".json", ".toml", ".yaml", ".yml",
        ".ps1", ".sh", ".py", ".cfg", ".ini", ""}
PAT = re.compile(
    r"(JUDGE_BASE_URL|JUDGE_API_KEY|EVAL_API_BASE|EVAL_API_KEY|"
    r"ANTHROPIC_BASE_URL|OPENAI_BASE_URL|ARK_API_KEY|GLM_BASE_URL)"
    r"\s*[=:]\s*(\S+)", re.I)

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}

hits = 0
for root in ROOTS:
    if not root.exists():
        continue
    for p in root.rglob("*"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        try:
            if not p.is_file() or p.stat().st_size > 3_000_000:
                continue
        except OSError:
            continue
        if p.suffix.lower() not in EXTS:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in PAT.finditer(text):
            key, val = m.group(1), m.group(2).strip("\"'")
            if not val or val.startswith("${") or val.startswith("<"):
                continue
            if re.search(r"key|token|secret", key, re.I):
                shown = "<len=" + str(len(val)) + ", head=" + val[:6] + "...>"
            else:
                shown = val
            print("  " + str(p) + "  ::  " + key + " = " + shown)
            hits += 1
            if hits > 60:
                raise SystemExit
print("real-value hits:", hits)

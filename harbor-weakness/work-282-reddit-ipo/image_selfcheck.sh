#!/bin/bash
# FIN3-WKN-152 镜像自检（规范 §9；末行须打印 OK）
set -uo pipefail
echo "--- interpreter versions ---"
python3 -V || exit 11
bash --version | head -1 || exit 12
node -v || exit 13
echo "--- claude-code pinned 2.1.114 ---"
claude --version 2>/dev/null | tee /tmp/clv.txt || exit 14
grep -q "2.1.114" /tmp/clv.txt || { echo "claude version mismatch"; exit 15; }
echo "--- rewardkit / markitdown ---"
rewardkit --help >/dev/null 2>&1 || exit 16
markitdown --help >/dev/null 2>&1 || exit 17
echo "--- python libs ---"
python3 - <<'PY'
import importlib
for m in ("openpyxl", "docx", "pptx", "pypdf"):
    importlib.import_module(m)
    print("  ok", m)
PY
[ $? -eq 0 ] || exit 18
echo "--- rewardkit version / pip check ---"
pip show harbor-rewardkit 2>/dev/null | grep '^Version:' || exit 19
pip check >/dev/null 2>&1 || exit 20
echo "--- agent user can write /app/output ---"
id agent || exit 21
su agent -c "touch /app/output/.w && rm /app/output/.w" || exit 22
echo "--- input_files read-only ---"
if su agent -c "touch /app/input_files/.w" 2>/dev/null; then
  echo "input_files WRITABLE (violation)"; rm -f /app/input_files/.w; exit 23
else
  echo "  ok input_files read-only"
fi
echo "--- golden model workbook readable ---"
python3 - <<'PY'
import glob, openpyxl, os
p = "/app/input_files/Q7_题目.xlsx"
wb = openpyxl.load_workbook(p, data_only=True)
assert len(wb.sheetnames) == 8, wb.sheetnames
print("  ok sheets:", len(wb.sheetnames))
PY
[ $? -eq 0 ] || exit 24
echo "OK"

#!/usr/bin/env bash
# 实测：当前 fix10 包在 Linux 下实际解压后的脚本权限
set -u
H=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness
TMP=/tmp/permcheck_$$
rm -rf "$TMP"; mkdir -p "$TMP"

echo "=== 工具可用性 ==="
command -v 7z  || echo "(无 7z)"
command -v 7za || echo "(无 7za)"
command -v unzip || echo "(无 unzip)"
python3 -c "import zipfile; print('python zipfile OK')"

echo ""
echo "=== 批次包 fix10 ==="
for tool in "7z x -y -o" "unzip -oq"; do
  :
done
if command -v 7z >/dev/null; then
  mkdir -p "$TMP/batch"; (cd "$TMP/batch" && 7z x -y "$H/work_fin-b01_20261011_fix10-149.zip" >/dev/null 2>&1)
  echo "-- 7z 解压后权限:"
  find "$TMP/batch" -name '*.sh' -printf '   %m  %p\n' 2>/dev/null | sed "s|$TMP/batch/||"
fi
if command -v unzip >/dev/null; then
  mkdir -p "$TMP/batch_u"; (cd "$TMP/batch_u" && unzip -oq "$H/work_fin-b01_20261011_fix10-149.zip" >/dev/null 2>&1)
  echo "-- unzip 解压后权限:"
  find "$TMP/batch_u" -name '*.sh' -printf '   %m  %p\n' 2>/dev/null | sed "s|$TMP/batch_u/||"
fi
echo "-- python zipfile extractall 后权限:"
mkdir -p "$TMP/batch_p"
python3 -c "
import zipfile,sys
zipfile.ZipFile('$H/work_fin-b01_20261011_fix10-149.zip').extractall('$TMP/batch_p')
"
find "$TMP/batch_p" -name '*.sh' -printf '   %m  %p\n' 2>/dev/null | sed "s|$TMP/batch_p/||"

echo ""
echo "=== create_system 与 external_attr 现状 ==="
python3 - <<'PY'
import zipfile
H='/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/'
for z in ['work_fin-b01_20261011_fix10-149.zip','FIN3-WKN-149_task.zip','FIN3-WKN-149_answer.zip']:
    print(f'--- {z}')
    for i in zipfile.ZipFile(H+z).infolist():
        if i.filename.endswith('.sh'):
            print(f'   create_system={i.create_system}  ext_attr=0o{i.external_attr>>16:o}  {i.filename}')
PY
rm -rf "$TMP"

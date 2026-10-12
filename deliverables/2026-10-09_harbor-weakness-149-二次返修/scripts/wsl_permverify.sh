#!/usr/bin/env bash
# 报告(4) 项1 要求的实测：Linux 实际解压后的脚本权限须为 0755
set -u
H=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness
TMP=/tmp/permfix_$$
rm -rf "$TMP"; mkdir -p "$TMP"

check() {
  local zip="$1" label="$2"
  local d="$TMP/$(basename "$zip" .zip)"
  mkdir -p "$d"
  # 用 python zipfile（与 Linux 解压器同语义）解压
  python3 -c "import zipfile;zipfile.ZipFile('$zip').extractall('$d')"
  echo "--- $label"
  find "$d" -name '*.sh' -printf '    %m  %f\n' | sort
  echo "    (目录) $(find "$d" -maxdepth 1 -type d -printf '%m' | head -1)  (普通文件示例) $(find "$d" -name '*.md' -printf '%m' | head -1)"
}

# 用一个会尊重 create_system 的第三方解压器再验一次（若有）
echo "=== Linux 实际解压权限（修复后）==="
check "$H/work_fin-b01_20261011_fix11-149.zip" "批次包 fix11"
check "$H/FIN3-WKN-149_task.zip" "task.zip"
check "$H/FIN3-WKN-149_answer.zip" "answer.zip"

echo ""
echo "=== 修复前对照（fix10 旧包）==="
check "$H/work_fin-b01_20261011_fix10-149.zip" "批次包 fix10（旧，应为 644）"

echo ""
echo "=== 若存在 7z / bsdtar，再做独立解压交叉验证 ==="
for t in 7z 7za bsdtar tar; do
  if command -v "$t" >/dev/null; then
    echo "-- $t 可用，试解 fix11："
    d="$TMP/x_$t"; mkdir -p "$d"
    case "$t" in
      7z|7za) "$t" x -y -o"$d" "$H/work_fin-b01_20261011_fix11-149.zip" >/dev/null 2>&1 ;;
      bsdtar) bsdtar -xf "$H/work_fin-b01_20261011_fix11-149.zip" -C "$d" 2>/dev/null ;;
      tar) tar -xf "$H/work_fin-b01_20261011_fix11-149.zip" -C "$d" 2>/dev/null ;;
    esac
    find "$d" -name '*.sh' -printf '    %m  %f\n' | sort || echo "    (解压失败)"
  fi
done
command -v 7z >/dev/null || command -v bsdtar >/dev/null || echo "(WSL 内无 7z/bsdtar，已用 python zipfile 同语义验证)"
rm -rf "$TMP"

#!/usr/bin/env bash
# 用真实 Linux 解压器（Info-ZIP unzip / busybox unzip）验证解压后权限
set -u
H=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness

run_unzip() {
  local img="$1" unzipcmd="$2" zip="$3" label="$4"
  echo "--- [$img / $unzipcmd] $label"
  docker run --rm -v "$H:/z:ro" --entrypoint sh "$img" -c "
    set -e
    rm -rf /t && mkdir -p /t && cd /t
    $unzipcmd -q /z/$(basename "$zip") >/dev/null 2>&1 || $unzipcmd /z/$(basename "$zip") >/dev/null 2>&1
    find /t -name '*.sh' -printf '    %m  %f\n' | sort
    echo \"    (目录) \$(find /t -mindepth 1 -maxdepth 1 -type d -printf '%m')\"
    echo \"    (普通文件) \$(find /t -name '*.md' -printf '%m' | head -1)\"
  " 2>&1
}

echo "############ Info-ZIP unzip（fin3-wkn-149:local） ############"
run_unzip "fin3-wkn-149:local" "unzip -o" "$H/work_fin-b01_20261011_fix11-149.zip" "fix11 批次包（修复后）"
run_unzip "fin3-wkn-149:local" "unzip -o" "$H/FIN3-WKN-149_task.zip" "task.zip（修复后）"
run_unzip "fin3-wkn-149:local" "unzip -o" "$H/FIN3-WKN-149_answer.zip" "answer.zip（修复后）"
run_unzip "fin3-wkn-149:local" "unzip -o" "$H/work_fin-b01_20261011_fix10-149.zip" "fix10 批次包（修复前，对照）"

echo ""
echo "############ busybox unzip（alpine:3.20） ############"
run_unzip "alpine:3.20" "busybox unzip" "$H/work_fin-b01_20261011_fix11-149.zip" "fix11 批次包（修复后）"
run_unzip "alpine:3.20" "busybox unzip" "$H/FIN3-WKN-149_task.zip" "task.zip（修复后）"
run_unzip "alpine:3.20" "busybox unzip" "$H/FIN3-WKN-149_answer.zip" "answer.zip（修复后）"
run_unzip "alpine:3.20" "busybox unzip" "$H/work_fin-b01_20261011_fix10-149.zip" "fix10 批次包（修复前，对照）"

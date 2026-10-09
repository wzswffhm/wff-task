#!/usr/bin/env bash
# 把二次返修后的 FIN3-WKN-149 题包暂存到 WSL 本地盘（排除 _rejudge / __pycache__），供 harbor fix8 跑分
set -u
SRC=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/FIN3-WKN-149
DST=/home/wff/harbor-tasks-fix8/FIN3-WKN-149

rm -rf /home/wff/harbor-tasks-fix8
mkdir -p "$DST"
cd "$SRC" || exit 1
tar cf - --exclude=_rejudge --exclude=__pycache__ --exclude='*.pyc' --exclude='.DS_Store' . | (cd "$DST" && tar xf -)

find "$DST" -name '*.sh' -exec chmod 755 {} \;
echo "=== 暂存文件数 ==="
find "$DST" -type f | wc -l
echo "=== 顶层 ==="
ls -la "$DST"
echo "=== 关键文件 ==="
ls -l "$DST/solution" "$DST/tests"
echo "=== 版本与窗口规则 ==="
grep -m1 '^version' "$DST/task.toml"
cat "$DST/environment/input_files/rules_windows.csv"
echo "=== golden 清单 ==="
find "$DST/solution/golden_output" -type f -printf '%s\t%P\n'

#!/bin/bash
# v2 G5 双模型终局
R=/mnt/c/Users/Administrator/Desktop/wff-task/harbor-weakness/_qc_runs
echo "=== v2 G5 三执行体终局 ==="
for spec in \
  "oracle:g4-152v2" \
  "qwen3.8-max-0902:g5-152v2-qwen2" \
  "gpt-5.6-sol:#4:g5-152v2-gpt4" \
  "gpt-5.6-sol#5:g5-152v2-gpt5" ; do
  name="${spec%%:*}"; rest="${spec#*:}"; dir="${rest##*:}"
  f=$(find "$R/$dir/trials" -maxdepth 3 -name reward.json 2>/dev/null | head -1)
  if [ -n "$f" ]; then
    rw=$(sed -n 's/.*"reward": *\([0-9.]*\).*/\1/p' "$f")
    cc=$(sed -n 's/.*"criteria_counted": *\([0-9.]*\).*/\1/p' "$f")
    ve=$(sed -n 's/.*"verifier_error": *\([0-9.]*\).*/\1/p' "$f")
    printf '  %-18s reward=%-10s criteria=%-6s verr=%s\n' "$name" "$rw" "$cc" "$ve"
  else
    printf '  %-18s (无 reward)\n' "$name"
  fi
done
echo
echo "=== 均分（gpt#5 为有效样本，qwen 为有效样本） ==="
python3 - <<'PY'
q = 0.98324; g = 0.98324
print(f"  qwen={q}  gpt#5={g}  两模型均分={(q+g)/2:.5f}  (门 <0.70)")
print(f"  若只算有效 run: gpt#4=0.0 属无产物的失败 run")
PY

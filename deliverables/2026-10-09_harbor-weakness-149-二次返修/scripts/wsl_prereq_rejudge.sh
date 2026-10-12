#!/usr/bin/env bash
echo "=== 1) fin3-wkn-149:local 镜像 ==="
docker images --format '{{.Repository}}:{{.Tag}} {{.Size}}' | grep fin3-wkn-149 || echo "(缺镜像)"
echo ""
echo "=== 2) fix8 三模型产物 ==="
for m in "trials-qwen/FIN3-WKN-149__uqNx7ti:qwen" "trials-gpt/FIN3-WKN-149__qsFcMtD:gpt" "trials-opus/FIN3-WKN-149__vTPHQTW:opus"; do
  p="${m%%:*}"; tag="${m##*:}"
  d="/home/wff/harbor-runs/FIN3-WKN-149-fix8/$p/artifacts/app/output"
  echo "--- $tag ($d) ---"
  ls "$d" 2>/dev/null | head || echo "(缺产物)"
done
echo ""
echo "=== 3) judge.env ==="
test -f /mnt/c/Users/Administrator/.wff-creds/judge.env && echo "存在" || echo "(缺 judge.env)"
echo ""
echo "=== 4) WSL 侧 tests（修复后 rubrics）==="
T=/home/wff/harbor-tasks-fix8/FIN3-WKN-149
ls "$T/tests/" 2>/dev/null
echo "--- 含 [scoring]? ---"
grep -c aggregation "$T/tests/rubrics.toml" 2>/dev/null
echo "--- __golden_output 是修复后的? ---"
test -f "$T/tests/__golden_output/FIN3-WKN-149_风险委员会决策备忘录.md" && stat -c%s "$T/tests/__golden_output/FIN3-WKN-149_风险委员会决策备忘录.md"
echo ""
echo "=== 5) input_files ==="
ls "$T/environment/input_files/" 2>/dev/null | wc -l

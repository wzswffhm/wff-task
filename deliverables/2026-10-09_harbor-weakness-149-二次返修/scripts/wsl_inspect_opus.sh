#!/usr/bin/env bash
set -u
echo "########## harbor trial start --help ##########"
/home/wff/.local/bin/harbor trial start --help 2>&1 | head -70

echo
echo "########## opus 备忘录完整性 ##########"
F=/home/wff/harbor-runs/FIN3-WKN-149-fix8/trials-opus/FIN3-WKN-149__6AB4Ng8/artifacts/app/output/FIN3-WKN-149_风险委员会决策备忘录.md
echo "bytes=$(stat -c%s "$F") lines=$(wc -l < "$F")"
echo "--- 章节目录 ---"
grep -n '^#' "$F"
echo "--- 末尾 12 行 ---"
tail -12 "$F"

echo
echo "########## opus reproduce.py 末尾 ##########"
tail -6 /home/wff/harbor-runs/FIN3-WKN-149-fix8/trials-opus/FIN3-WKN-149__6AB4Ng8/artifacts/app/output/FIN3-WKN-149_reproduce.py

echo
echo "########## 可用镜像 ##########"
docker images --format '{{.Repository}}:{{.Tag}}\t{{.Size}}' | grep -i -E 'fin3|149' || true

echo
echo "########## harbor 是否有 verify-only 子命令 ##########"
/home/wff/.local/bin/harbor --help 2>&1 | head -40

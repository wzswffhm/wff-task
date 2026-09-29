#!/usr/bin/env bash
# =============================================================================
# 本地链路彩排（dry-run rehearsal）— 2026-09-28-3 marshmallow
#
# 用一份**合成的 agent 改动**（由 reference.patch 生成）把本地判分链路整条跑通：
#   grade_manual_trae(no-skill) → grade_manual_trae(with-skill)
#   → verify_agent_patch(--docker) → capture_final_check
#   → build_delivery_zip → check_package
#
# 隔离保证：run-root 与输出 ZIP 都在 /root/obm-rehearsal/ 的副本上，
# 绝不写入真实 trae-runs-v1 或 output/，不产生任何真实证据。
#
# 用法（WSL root）：
#   tr -d '\r' < .../tools/rehearse_local_flow.sh | bash
# =============================================================================
set -uo pipefail

WIN=/mnt/c/Users/Administrator/Desktop/OBM
TASK_NAME=deepSWE_2026-09-28-3-marshmallow-doc-diff
SKILL="$WIN/skills/obm-task-production/scripts"
RUN_SRC="$WIN/work/2026-09-28-3-marshmallow-doc-diff/trae-runs-v1"
REF_PATCH="$WIN/work/2026-09-28-3-marshmallow-doc-diff/reference.patch"
STAGE=/root/obm-build
TASK="$STAGE/$TASK_NAME"
REH=/root/obm-rehearsal
RUN="$REH/run-root"
PY=python3

log() { printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }
die() { printf '\n\033[1;31m[REHEARSAL-FAIL] %s\033[0m\n' "$*" >&2; exit 1; }

git config --global --add safe.directory '*' >/dev/null 2>&1 || true

if [ ! -x "$TASK/sources/verifier/test.sh" ]; then
  log "stage 题包到 ext4（补 exec 位）"
  rm -rf "$STAGE"; mkdir -p "$STAGE"
  cp -r "$WIN/output/$TASK_NAME" "$TASK"
  chmod +x "$TASK/sources/verifier/test.sh" "$TASK/sources/verifier/grader.py"
fi
[ -f "$REF_PATCH" ] || die "缺少 reference.patch：$REF_PATCH"

log "复制 run-root 副本，并按真实流程设 core.autocrlf=true（不做任何 sed）"
rm -rf "$REH"; mkdir -p "$REH"
cp -r "$RUN_SRC" "$RUN"
NO_SKILL_REPO="$RUN/3-no-skill/3-no-repo"
WITH_SKILL_REPO="$RUN/3-with-repo/3-with-repo"
for R in "$NO_SKILL_REPO" "$WITH_SKILL_REPO"; do
  git -C "$R" config core.autocrlf true
done
echo -n "no-skill  工作区改动数（应为 0）: "; git -C "$NO_SKILL_REPO" status --porcelain | wc -l
echo -n "with-skill 工作区改动数（应为 0）: "; git -C "$WITH_SKILL_REPO" status --porcelain | wc -l

log "由 reference.patch 合成 agent 改动，写入 with-skill 工作区"
TMP="$REH/tmpapp"; mkdir -p "$TMP"
cp -r "$TASK/sources/app/marshmallow" "$TMP/"
( cd "$TMP" && patch -p2 --no-backup-if-mismatch < "$REF_PATCH" >/dev/null ) \
  || die "参考补丁无法应用到 app 副本"
sed 's/$/\r/' "$TMP/marshmallow/schema.py" > "$WITH_SKILL_REPO/src/marshmallow/schema.py"
echo "with-skill 改动应为：仅 src/marshmallow/schema.py"
git -C "$WITH_SKILL_REPO" diff --stat

log "① 判分 no-skill（期望 reward=0 → exit 10）"
"$PY" "$SKILL/grade_manual_trae.py" --task-dir "$TASK" --run-root "$RUN" \
      --mode no-skill --docker docker; rc=$?
echo "no-skill exit=$rc"
[ "$rc" = "10" ] || die "no-skill 期望 exit=10（ready_for_with_skill），实得 $rc"

log "② 判分 with-skill（期望 reward=1 → exit 0 → status=passed）"
"$PY" "$SKILL/grade_manual_trae.py" --task-dir "$TASK" --run-root "$RUN" \
      --mode with-skill --docker docker; rc=$?
echo "with-skill exit=$rc"
[ "$rc" = "0" ] || die "with-skill 期望 exit=0（passed），实得 $rc"

log "③ 最终质检 capture_final_check（期望 ok=true）"
"$PY" "$SKILL/capture_final_check.py" --task-dir "$TASK" \
      --experiment-result "$RUN/EXPERIMENT_RESULT.json" \
      --output-dir "$REH/final-check" --benchmark deepSWE; rc=$?
echo "final-check exit=$rc"
[ "$rc" = "0" ] || die "最终质检未通过"

log "④ 打包 build_delivery_zip（彩排产物写在 $REH/）"
"$PY" "$SKILL/build_delivery_zip.py" --task-dir "$TASK" \
      --experiment-result "$RUN/EXPERIMENT_RESULT.json" \
      --final-check "$REH/final-check/FINAL_CHECK.json" \
      --output "$REH/$TASK_NAME.zip" --benchmark deepSWE; rc=$?
echo "zip exit=$rc"
[ "$rc" = "0" ] || die "打包未通过"

log "⑤ 对 ZIP 再跑 check_package"
"$PY" "$SKILL/check_package.py" "$REH/$TASK_NAME.zip" --benchmark deepSWE | tail -6

printf '\n\033[1;32m[REHEARSAL-OK] 本地链路端到端跑通；真实证据未被触碰。\033[0m\n'

#!/usr/bin/env bash
# =============================================================================
# OBM 2026-09-28-4 后处理一键流水线 —— **v2（加难版）**
#
#   用法（在 WSL 里，root）：
#     tr -d '\r' < .../tools/run_post_trae_v2.sh | bash -s -- all
#   分步：   ... bash -s -- no-skill | with-skill | final | zip
#   指定工具名： ... bash -s -- all "" "TRAECODE"
#
#   顺序：
#     1) stage 题包到 WSL ext4 并补可执行位（Windows NTFS 存不了 exec 位）
#     2) grade_manual_trae.py --mode no-skill   （期望 reward=0, exit 10）
#     3) grade_manual_trae.py --mode with-skill （期望 reward=1, exit 0 → status=passed）
#     4) capture_final_check.py                 （期望 ok=true）
#     5) build_delivery_zip.py                  （产出正式 .zip）
#     6) check_package.py <zip>                 （期望 PASS）
#
#   任何一步不满足期望即中止，且不会伪造实验结果。
# =============================================================================
set -uo pipefail

WIN=/mnt/c/Users/Administrator/Desktop/OBM
TASK_NAME=deepSWE_2026-09-28-4-networkx-pareto-paths
WORK_NAME=2026-09-28-4-networkx-pareto-paths
TASK_WIN="$WIN/output/$TASK_NAME"
RUN_ROOT="$WIN/work/$WORK_NAME/trae-runs-v2"
WORK_WIN="$WIN/work/$WORK_NAME"
SKILL="$WIN/skills/obm-task-production/scripts"
STAGE=/root/obm-build4v2
TASK="$STAGE/$TASK_NAME"
EXP="$RUN_ROOT/EXPERIMENT_RESULT.json"
FINAL_DIR="$WORK_WIN/final-check-v2"
OUT_ZIP="$WIN/output/$TASK_NAME.zip"
PY=python3
DOCKER=docker

STEP="${1:-all}"
FORCE="${2:-}"
RUNNER="${3:-${RUNNER:-Trae CN (user manual)}}"
NO_REPO="$RUN_ROOT/4-no-skill/4-no-repo"
WITH_REPO="$RUN_ROOT/4-with-repo/4-with-repo"

log() { printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }
die() { printf '\n\033[1;31m[ABORT] %s\033[0m\n' "$*" >&2; exit 1; }

stage_task() {
  log "stage 题包到 ext4 并补可执行位"
  rm -rf "$STAGE"; mkdir -p "$STAGE"
  cp -r "$TASK_WIN" "$TASK"
  chmod +x "$TASK/sources/verifier/test.sh" "$TASK/sources/verifier/grader.py"
  git config --global --add safe.directory '*' >/dev/null 2>&1 || true
  stat -c '%a %n' "$TASK/sources/verifier/test.sh" "$TASK/sources/verifier/grader.py"
}

preflight() {
  local repo="$1" label="$2"
  [ -d "$repo" ] || die "$label 工作区不存在：$repo（先跑 prepare_trae_runs.py）"
  git config --global --add safe.directory '*' >/dev/null 2>&1 || true
  # NTFS 上工作区整棵树是 CRLF、基线 blob 是 LF；不设 autocrlf 会让 create_patch
  # 产出「全仓库换行符 churn」垃圾 patch，使判分失效。
  git -C "$repo" config core.autocrlf true
  # 用与 create_patch 相同的口径判断「是否真的有改动」（包含新增文件），
  # 避免被 .trae/、缓存等未跟踪文件误判成「已经跑过」。
  git -C "$repo" add -N --all >/dev/null 2>&1 || true
  local changed
  changed=$(git -C "$repo" diff --name-only HEAD 2>/dev/null | wc -l)
  git -C "$repo" reset --mixed -q HEAD >/dev/null 2>&1 || true
  if [ "$changed" -eq 0 ] && [ "$FORCE" != "--force" ]; then
    die "$label 工作区没有任何代码改动，看起来 Trae 还没跑（或 Agent 没动代码）。
     请在 Trae 中真实跑完 $label 再执行本脚本；若确实是 Agent 失败未产生改动，加 --force 继续。"
  fi
}

have_no_skill_result() {
  [ -f "$EXP" ] || return 1
  "$PY" -c '
import json, sys
try:
    data = json.load(open(sys.argv[1], encoding="utf-8"))
except Exception:
    sys.exit(1)
ns = data.get("no_skill") or {}
sys.exit(0 if ns.get("status") == "completed" and int(ns.get("reward", 1)) == 0 else 1)
' "$EXP"
}

grade_no_skill() {
  if have_no_skill_result; then
    echo "[skip] 已有有效 no-skill 结果（reward=0），不重复判分"
    return 0
  fi
  preflight "$NO_REPO" no-skill
  log "grade no-skill（期望 reward=0 / exit 10）"
  "$PY" "$SKILL/grade_manual_trae.py" --task-dir "$TASK" --run-root "$RUN_ROOT" \
      --mode no-skill --docker "$DOCKER" --runner "$RUNNER"
  local rc=$?
  case "$rc" in
    10) echo "[OK] no-skill reward=0，可继续 with-skill";;
    20) die "no-skill reward=1 → 题目仍然太简单，需继续加难（exit 20）";;
    22) die "基础设施错误（exit 22），检查上方 VERIFICATION/日志";;
    *)  die "no-skill 异常退出 rc=$rc";;
  esac
}

grade_with_skill() {
  if [ -f "$EXP" ] && "$PY" -c '
import json, sys
try:
    data = json.load(open(sys.argv[1], encoding="utf-8"))
except Exception:
    sys.exit(1)
sys.exit(0 if data.get("status") == "passed" else 1)
' "$EXP"; then
    echo "[skip] EXPERIMENT_RESULT.json 已是 passed（no-skill=0 / with-skill=1），不重复判分"
    return 0
  fi
  preflight "$WITH_REPO" with-skill
  log "grade with-skill（期望 reward=1 / exit 0 / status=passed）"
  "$PY" "$SKILL/grade_manual_trae.py" --task-dir "$TASK" --run-root "$RUN_ROOT" \
      --mode with-skill --docker "$DOCKER" --runner "$RUNNER"
  [ $? -eq 0 ] || die "with-skill 未通过（见上）；需按 SKILL.md 返修专家思路后换新版本重跑"
  echo "[OK] with-skill reward=1，对照实验成立"
}

final_check() {
  log "capture_final_check（期望 ok=true）"
  rm -rf "$FINAL_DIR"
  "$PY" "$SKILL/capture_final_check.py" --task-dir "$TASK" \
      --experiment-result "$EXP" --output-dir "$FINAL_DIR" --benchmark deepSWE
  [ $? -eq 0 ] || die "最终质检未通过（ok=false）"
  echo "[OK] FINAL_CHECK.json ok=true：$FINAL_DIR"
}

build_zip() {
  log "build_delivery_zip（产出正式 .zip）"
  rm -f "$OUT_ZIP"
  "$PY" "$SKILL/build_delivery_zip.py" --task-dir "$TASK" \
      --experiment-result "$EXP" --final-check "$FINAL_DIR/FINAL_CHECK.json" \
      --output "$OUT_ZIP" --benchmark deepSWE
  [ $? -eq 0 ] || die "打包失败"
  log "对 ZIP 再跑 check_package.py"
  "$PY" "$SKILL/check_package.py" "$OUT_ZIP" --benchmark deepSWE | tail -20
  echo "[OK] 交付 ZIP：$OUT_ZIP"
}

case "$STEP" in
  stage)      stage_task;;
  no-skill)   stage_task; grade_no_skill;;
  with-skill) grade_with_skill;;
  final)      final_check;;
  zip)        build_zip;;
  all)
    stage_task
    grade_no_skill
    grade_with_skill
    final_check
    build_zip
    log "全部完成：可进入飞书提交（references/feishu-submission.md）"
    ;;
  *) die "未知步骤：$STEP（可用：stage|no-skill|with-skill|final|zip|all）";;
esac

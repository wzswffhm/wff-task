#!/usr/bin/env python3
"""甲方机器门禁一键跑批（wrapper —— 调用甲方生产侧脚本，不复制脚本本体）。

依据: 甲方 weakness-qc v1.0 references/gates.md「必跑清单」+ FAIL 分级表。
原则: **不要复制甲方脚本**（历史上正是两份取值不一致的 check_complexity.py 造成误判）；
      直接调用生产侧脚本，本 wrapper 只做编排、分级与汇总。

用法:
  python client_gates.py <题目目录> [--runs-dir <跑分产物与轨迹目录>] [--zip <zip> ...]
                         [--waive <脚本名> ...]

  --waive <脚本名>  把该门禁显式降级为「提示」。仅限按甲方 gates.md §四完成
                    「回规范原文复核、确认属脚本口径与规范冲突」之后使用（如
                    check_rubric_style 对 likert 档位锚点内递进量词的误报）；
                    waiver 须写入质检报告单列小节（附脚本原始输出与人工判据）。
  不传 --runs-dir 时自动发现: 在题目目录的兄弟目录下找含 ≥2 个执行体
  reward-details.json 的「跑分产物与轨迹」目录。

脚本目录定位（依次探测，可用环境变量 CLIENT_SCRIPTS 覆盖）:
  1) %CLIENT_SCRIPTS%
  2) <repo>/../../Desktop/weakness-data-construction/scripts   # 本机: Desktop 甲方 skill
  3) ~/.codex/skills/weakness-data-construction/scripts        # 甲方文档默认位置

退出码: 0 = 无 must-fix FAIL；1 = 存在必须整改项；2 = 甲方脚本缺失/参数错误。
每次运行会打印所调用甲方脚本的 SHA256（用于跨轮次检测脚本漂移）。
"""
import hashlib
import os
import re
import subprocess
import sys

MUST_FIX = {
    "validate_task_package.py",
    "validate_rubrics.py",
    "check_rubric_style.py",       # --strict：措辞不合规 → 必须整改
    "check_package_permissions.py",
}
ADVISORY = {
    "check_complexity.py",         # 脚本口径与规范冲突 → 提示/待人工核，不得据此判不通过
    "check_cross_model_concentration.py",  # ≥25% → 口径歧义排查，提示
    "check_batch_quota.py",        # 单题包口径通常只出提示，非阻塞
    "check_instruction_anchors.py",
}


def find_client_scripts():
    env = os.environ.get("CLIENT_SCRIPTS")
    cands = []
    if env:
        cands.append(env)
    home = os.path.expanduser("~")
    cands += [
        os.path.join(home, "Desktop", "weakness-data-construction", "scripts"),
        os.path.join(home, ".codex", "skills", "weakness-data-construction", "scripts"),
        os.path.join(home, "skills", "weakness-data-construction", "scripts"),
    ]
    for c in cands:
        if os.path.isdir(c):
            return c
    return None


def discover_runs_dir(task_dir):
    """在兄弟目录中找含 ≥2 个执行体 reward-details.json 的「跑分产物与轨迹」目录；
    多个命中时按题号后缀消歧（如 FIN3-WKN-150 → 批次名以 -150 结尾）。"""
    parent = os.path.dirname(task_dir)
    hits = []
    if os.path.isdir(parent):
        for name in sorted(os.listdir(parent)):
            rd = os.path.join(parent, name, "跑分产物与轨迹")
            if not os.path.isdir(rd):
                continue
            n = 0
            for exec_name in os.listdir(rd):
                if os.path.isfile(os.path.join(rd, exec_name, "reward-details.json")):
                    n += 1
            if n >= 2:
                hits.append((name, rd))
    if not hits:
        return None
    if len(hits) == 1:
        return hits[0][1]
    # 消歧：题号后缀（末段数字）
    m = re.search(r"(\d+)$", os.path.basename(task_dir))
    if m:
        suffix = m.group(1)
        picked = [rd for name, rd in hits if re.search(rf"[-_]{suffix}$", name)]
        if len(picked) == 1:
            return picked[0]
    return None


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def run(script, args):
    cmd = [sys.executable, os.path.join(CLIENT, script)] + args
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode, out


def main():
    global CLIENT
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    flags = set(a for a in sys.argv[1:] if a.startswith("-"))
    if not args:
        print(__doc__)
        return 2
    task_dir = os.path.abspath(args[0].rstrip("/\\"))
    runs_dir = None
    for i, a in enumerate(sys.argv):
        if a == "--runs-dir" and i + 1 < len(sys.argv):
            runs_dir = os.path.abspath(sys.argv[i + 1])
    zips = []
    for i, a in enumerate(sys.argv):
        if a == "--zip" and i + 1 < len(sys.argv):
            zips.append(os.path.abspath(sys.argv[i + 1]))
    waivers = set()
    for i, a in enumerate(sys.argv):
        if a == "--waive" and i + 1 < len(sys.argv):
            waivers.add(sys.argv[i + 1])

    CLIENT = find_client_scripts()
    if not CLIENT:
        print("[FATAL] 未找到甲方生产侧脚本目录（设 CLIENT_SCRIPTS 或放置 Desktop/weakness-data-construction）")
        return 2
    if not os.path.isfile(os.path.join(task_dir, "task.toml")):
        print(f"[FATAL] 题目目录无 task.toml: {task_dir}")
        return 2

    print(f"== 甲方生产侧脚本: {CLIENT}")
    for s in sorted(os.listdir(CLIENT)):
        if s.endswith(".py"):
            print(f"   sha256:{sha256(os.path.join(CLIENT, s))}  {s}")

    results = []  # (script, verdict, rc, tail)

    def step(name, script, sargs, classify=True):
        rc, out = run(script, sargs)
        tail = "\n".join(out.strip().splitlines()[-6:])
        print(f"\n--- {name} (exit={rc}) ---\n{tail}")
        if not classify:
            verdict = "SKIP"
        elif rc == 0:
            verdict = "PASS"
        elif script in waivers:
            verdict = "WAIVED"
        elif script in MUST_FIX:
            verdict = "MUST-FIX"
        else:
            verdict = "ADVISORY"
        results.append((name, verdict, rc, out))
        return rc

    # 0) 脚本漂移哨兵：self-test FAIL → 脚本取值漂移，后续 check_complexity 结论只作提示
    rc_st, out_st = run("check_complexity.py", ["--self-test"])
    print(f"\n--- check_complexity --self-test (exit={rc_st}) ---\n" +
          "\n".join(out_st.strip().splitlines()[-4:]))
    complexity_advisory_only = (rc_st != 0)
    if complexity_advisory_only:
        print(">>> self-test FAIL：甲方脚本取值漂移，check_complexity 结论降级为提示（以分级表为准）")

    # 1) 元数据 / 判据 / 复杂度 / 措辞
    step("validate_task_package", "validate_task_package.py", [task_dir])
    step("validate_rubrics", "validate_rubrics.py", [task_dir])
    step("check_complexity", "check_complexity.py", [task_dir])
    if complexity_advisory_only:
        results[-1] = (results[-1][0], "ADVISORY", results[-1][2], results[-1][3])
    step("check_rubric_style --strict", "check_rubric_style.py", [task_dir, "--strict"])

    # 2) 锚点：甲方脚本硬编码其自有批次（FIN-127/128/129-W），对本题包不可复用 → 跳过，人工核
    print("\n--- check_instruction_anchors ---\nSKIP：甲方脚本硬编码 FIN-127/128/129-W，"
          "对本题包不可复用；判据锚点须人工对照 instruction.md 与材料逐条核（见 07-pitfalls B13）")
    results.append(("check_instruction_anchors", "SKIP", 0, ""))

    # 3) 集中度（--runs-dir 优先；否则在兄弟批次目录自动发现）
    if not runs_dir:
        runs_dir = discover_runs_dir(task_dir)
        if not runs_dir:
            print("\n[注意] 未能唯一确定跑分目录（多代批次并存或缺失）→ 集中度检查以脚本默认推断执行；"
                  "正式结算请用 --runs-dir 显式指定正式批次的「跑分产物与轨迹」目录")
    if runs_dir:
        print(f"\n使用跑分目录: {runs_dir}")
        rd_args = [task_dir, runs_dir]
    else:
        rd_args = [task_dir]
    step("check_cross_model_concentration", "check_cross_model_concentration.py", rd_args)

    # 4) 打包权限（有 zip 传 zip，否则传题目目录）
    perm_targets = zips or [task_dir]
    step("check_package_permissions", "check_package_permissions.py", perm_targets)

    # 5) 批次配额（单题包口径，提示级）
    step("check_batch_quota", "check_batch_quota.py", [task_dir])

    # 汇总
    print("\n" + "=" * 60)
    must = [r for r in results if r[1] == "MUST-FIX"]
    adv = [r for r in results if r[1] == "ADVISORY"]
    wav = [r for r in results if r[1] == "WAIVED"]
    for name, verdict, rc, _ in results:
        mark = {"PASS": "OK   ", "MUST-FIX": "FAIL ", "ADVISORY": "提示 ",
                "WAIVED": "豁免 ", "SKIP": "SKIP "}[verdict]
        print(f"  [{mark}] {name}")
    print("=" * 60)
    if must:
        print(f"结论: 存在 {len(must)} 项必须整改 → {'、'.join(m[0] for m in must)}")
        return 1
    lines = [f"0 必须整改"]
    if wav:
        lines.append(f"{len(wav)} 项经规范原文复核后豁免（{'、'.join(w[0] for w in wav)}；waiver 须在质检报告单列）")
    if adv:
        lines.append(f"{len(adv)} 项提示（{'、'.join(a[0] for a in adv)}）→ 按门禁分级表人工复核后放行")
    print("结论: " + "；".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())

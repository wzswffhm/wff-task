# -*- coding: utf-8 -*-
"""批次结构对齐 151（序号267，一审通过）：
    work_fin-b01_20261009-152/
    ├── 交付文档.md          ← 批次根
    ├── 跑分产物与轨迹/       ← 批次根（与题目目录平级）
    └── FIN3-WKN-152/         ← 五件套
同时把交付文档里我此前按 150#7 写的「题目目录内」描述改回 151 口径。
"""
import pathlib
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")

H = pathlib.Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-weakness")
BATCH = H / "work_fin-b01_20261009-152"
TASKD = BATCH / "FIN3-WKN-152"
DOC = "交付文档.md"
RUNS = "跑分产物与轨迹"

DRY = "--dry-run" in sys.argv

print("=" * 94)
print("1) 移动目录到批次根（对齐 151）")
print("=" * 94)
for name in (DOC, RUNS):
    src = TASKD / name
    dst = BATCH / name
    if dst.exists() and not src.exists():
        print(f"  [--] {name} 已在批次根")
    elif src.exists():
        if DRY:
            print(f"  [dry] {src} -> {dst}")
        else:
            if dst.exists():
                if dst.is_dir():
                    shutil.rmtree(dst)
                else:
                    dst.unlink()
            shutil.move(str(src), str(dst))
            print(f"  [OK] 已移动 {name} -> 批次根")
    else:
        print(f"  [!!] 两处都没有 {name}")

print()
print("=" * 94)
print("2) 校验结构")
print("=" * 94)
if not DRY:
    tops = sorted(p.name for p in BATCH.iterdir())
    print(f"  批次根: {tops}")
    inner = sorted(p.name for p in TASKD.iterdir())
    print(f"  题目目录: {inner}")
    # 关键校验
    ok1 = (BATCH / DOC).is_file()
    ok2 = (BATCH / RUNS).is_dir()
    ok3 = TASKD.is_dir()
    runs = BATCH / RUNS
    if runs.is_dir():
        subs = sorted(p.name for p in runs.iterdir())
        print(f"  跑分子项: {subs}")
        n_files = sum(1 for p in runs.rglob("*") if p.is_file())
        print(f"  跑分文件数: {n_files}")
    print(f"  批次根含交付文档: {ok1} / 跑分产物: {ok2} / 题目目录: {ok3}")
    # 题目目录内不应再有这两项
    print(f"  题目目录内残留文档: {(TASKD / DOC).exists()}（应 False）")
    print(f"  题目目录内残留跑分: {(TASKD / RUNS).exists()}（应 False）")

# ── 3) 同步交付文档描述（我此前按 150#7 写的「题目目录内」改回 151 口径）──
print()
print("=" * 94)
print("3) 同步交付文档描述（151 口径）")
print("=" * 94)
p = BATCH / DOC
if not p.exists():
    p = TASKD / DOC
raw = p.read_text(encoding="utf-8")
ok = []


def rep(old, new, label):
    global raw
    n = raw.count(old)
    if n != 1:
        print(f"  [!!] {label}: 匹配 {n} 次")
        ok.append(False)
        return
    raw = raw.replace(old, new, 1)
    print(f"  [OK] {label}")
    ok.append(True)


rep(
    "> 本文件置于**题目目录**（`work_fin-b01_20261009-152/FIN3-WKN-152/`，满足质检第 7 条：批次 zip 第二层仅题目目录），逐项说明环境变量 Key、必选性与联动关系。",
    "> 本文件置于**批次根目录**（与题目目录 `FIN3-WKN-152/`、`跑分产物与轨迹/` 平级，与 FIN3-WKN-151（序号267，一审通过）交付结构一致），逐项说明环境变量 Key、必选性与联动关系。",
    "L4 文件位置（题目目录→批次根）",
)
rep(
    "| 批次根目录 | `harbor-weakness/work_fin-b01_20261009-152/`（**第二层仅题目目录** `FIN3-WKN-152/`，本文件、五件套与 `跑分产物与轨迹/` 均在其内） |",
    "| 批次根目录 | `harbor-weakness/work_fin-b01_20261009-152/`（含本文件 `交付文档.md` + 题目目录 `FIN3-WKN-152/` + `跑分产物与轨迹/`，三者平级） |",
    "L11 批次根描述",
)
rep(
    "## 4. 跑分归档（**题目目录内** `FIN3-WKN-152/跑分产物与轨迹/`）",
    "## 4. 跑分归档（**批次根** `跑分产物与轨迹/`）",
    "§4 标题",
)
rep(
    "> `跑分产物与轨迹/` 与 `交付文档.md` 均**归入题目目录** `FIN3-WKN-152/`，使批次 zip **第二层仅题目目录**（质检报告第 7 条）；四执行体统一使用 `output/` 目录。",
    "> `跑分产物与轨迹/` 与 `交付文档.md` 置于**批次根**，与题目目录 `FIN3-WKN-152/` **平级**（结构对齐 FIN3-WKN-151／序号267 一审通过交付包）；四执行体统一使用 `output/` 目录。",
    "§4 位置说明",
)
rep(
    """work_fin-b01_20261009-152/                  ← 批次目录（zip 根）
└── FIN3-WKN-152/                            ← 第二层仅题目目录
    ├── instruction.md / task.toml / rubrics.json
    ├── environment/  { Dockerfile, requirements.txt, input_files/ (60 文件) }
    ├── solution/     { solve.sh, golden_output/ (7 文件) }
    ├── tests/        { rubrics.toml, prompt.md, test.sh, finalize.py, __golden_output/ (7 文件) }
    ├── 交付文档.md                          ← 本文件（归入题目目录）
    └── 跑分产物与轨迹/                       ← 归入题目目录
        ├── oracle/               { output/ (7), 轨迹/{oracle.txt,trial.log,说明.txt}, reward.json, reward-details.json }
        ├── qwen3.8-max-0902/     { output/ (7), 轨迹/{claude-code.txt,trajectory.json,trial.log}, reward.json, reward-details.json }
        ├── gpt-5.6-sol/          { output/ (7), 轨迹/{claude-code.txt,trajectory.json,trial.log}, reward.json, reward-details.json }
        ├── claude-opus-4-8/      { output/ (7), 轨迹/{claude-code.txt,trajectory.json,trial.log}, reward.json, reward-details.json }
        └── summary.json          { oracle_reward=1.0, three_model_mean=0.590643, measured_band=A2, gate_pass=true }""",
    """work_fin-b01_20261009-152/                  ← 批次目录（zip 根）
├── 交付文档.md                              ← 本文件（批次根，与题目目录平级）
├── 跑分产物与轨迹/                           ← 批次根（与题目目录平级）
│   ├── oracle/               { output/ (7), 轨迹/{oracle.txt,trial.log,说明.txt}, reward.json, reward-details.json }
│   ├── qwen3.8-max-0902/     { output/ (7), 轨迹/{claude-code.txt,trajectory.json,trial.log}, reward.json, reward-details.json }
│   ├── gpt-5.6-sol/          { output/ (7), 轨迹/{claude-code.txt,trajectory.json,trial.log}, reward.json, reward-details.json }
│   ├── claude-opus-4-8/      { output/ (7), 轨迹/{claude-code.txt,trajectory.json,trial.log}, reward.json, reward-details.json }
│   └── summary.json          { oracle_reward=1.0, three_model_mean=0.590643, measured_band=A2, gate_pass=true }
└── FIN3-WKN-152/                            ← 题目目录（五件套）
    ├── instruction.md / task.toml / rubrics.json
    ├── environment/  { Dockerfile, requirements.txt, input_files/ (60 文件) }
    ├── solution/     { solve.sh, golden_output/ (7 文件) }
    └── tests/        { rubrics.toml, prompt.md, test.sh, finalize.py, __golden_output/ (7 文件) }""",
    "§4 目录树（批次根三者平级）",
)
rep(
    "| 批次包 | `work_fin-b01_20261009-152.zip`（**第二层仅 `FIN3-WKN-152/`**：五件套 + 交付文档 + 跑分产物与轨迹） |",
    "| 批次包 | `work_fin-b01_20261009-152.zip`（批次根：`交付文档.md` + `跑分产物与轨迹/` + `FIN3-WKN-152/` 三者平级，对齐序号267 交付结构） |",
    "§5 批次包描述",
)
rep(
    "| 归档 | `FIN3-WKN-152/跑分产物与轨迹/`（**四执行体** oracle + qwen + gpt + opus，含产物、轨迹、逐条判分明细 + `summary.json`） |",
    "| 归档 | `跑分产物与轨迹/`（批次根；**四执行体** oracle + qwen + gpt + opus，含产物、轨迹、逐条判分明细 + `summary.json`） |",
    "§5 归档描述",
)

print()
if all(ok):
    if not DRY:
        p.write_text(raw, encoding="utf-8", newline="\n")
        print(f"[写出] {p}  {len(raw.splitlines())} 行")
else:
    print("[!!] 有失败项")

# 残留检查
t = (BATCH / DOC if (BATCH / DOC).exists() else TASKD / DOC).read_text(encoding="utf-8")
print()
print("=" * 94)
print("残留检查（应全无）")
print("=" * 94)
for pat in ("第二层仅题目目录", "归入题目目录", "题目目录内"):
    print(f"  {'[!!] 仍有' if pat in t else '[OK] 无'}  {pat}")

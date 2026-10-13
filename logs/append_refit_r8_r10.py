# -*- coding: utf-8 -*-
"""append_refit_r8_r10.py -- 给 219 的 REFIT 补上 R8/R9/R10 三章。

背景：`verifier/README.md` 引用了 `§R8–§R10`，但 REFIT 只写到 R7，属于悬空引用。
本脚本补齐三章，并更新文档头部的版本范围。

设计约束：本文件**只在跑分之前**写入。R10（v1.4.0）的复验数据不由本文件承载，
而是放在包外交付 README 里，这样跑分结束后无需再改动包内任何字节。
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

D = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\_qc_runs"
         r"\relaunch-20261013\staged\wfflab__wpeimg-219-v1.4.0-delivery")
DOC = D / "REFIT-2026-10-13.md"

HEAD_OLD = "# 返修说明与复验记录（wfflab__wpeimg-219，v1.0.0 → v1.1.0）"
HEAD_NEW = ("# 返修说明与复验记录（wfflab__wpeimg-219，v1.0.0 → v1.1.0 → v1.2.0 → v1.3.0 → v1.4.0）\n"
            "\n"
            "> 第 1 节（R1–R7）是 v1.0.0 → v1.1.0 的返修闭环。\n"
            "> R8（v1.2.0）、R9（v1.3.0）、R10（v1.4.0）是随后三轮**主动加严**的记录：\n"
            "> 前两轮针对区分度，第三轮针对「判据必须落到真实操作系统机制」。\n"
            "> R10 的复验数据不写在本文件里（本文件在跑分前冻结），\n"
            "> 而是随交付目录的 `README.md` 一并给出。")

NEW_SECTIONS = """

---

### R8｜区分度不足（v1.2.0：补 PE 目录表与 Authenticode 尾部）

对应甲方门禁：**四模型区分度**（`Opus model_score_sum > Qwen model_score_sum`）。

- **触发**：v1.1.0 的实测结果是 Qwen **3/3 全满**（27/27）、Opus 5 **2/3**，
  于是 `opus_score_sum (2) < qwen_score_sum (3)` → 硬门禁 **FAIL**。
  也就是说：弱主模型一次不错，强模型反而掉分，这道题对主模型没有区分力。
- **处置**：题面新增 **A2 节**（数据目录表与 Authenticode 尾部），并新增两个互相
  独立的程序化评分组：`data-directories`（0.08，4 条）与
  `authenticode-detection`（0.06，3 条）。required 由 **27 → 34** 条。
- **复验**：v1.2.0 实测 Qwen **3/3 全满**（34/34）、Opus 5 **2/3**（替代轮 33/34，
  只错 `f2p-iter-sections-does-not-slurp-the-stream`）。
  期间 Opus 第 1 轮撞上供应商 `http_502 Bad Gateway`，按甲方要求单列
  `jobs/invalid-slots.json` + `jobs/INVALID-SLOTS.md`，并以
  `model-opus-1-rerun` 绑定同一计划槽位重跑。
- **结论**：**仍然 FAIL**。增加「格式字段的数量」不足以拉开区分度——两个模型都能
  把这些字段读对。这条结论直接决定了 R9 的方向。

### R9｜区分度仍不足（v1.3.0：要求自行解析 PKCS#7 SignedData 的 DER）

- **触发**：R8 复验后区分度仍不成立。
- **处置**：题面新增 **F2 节**，要求新增公开函数 `signature_info(data)` **自己走
  PKCS#7 `SignedData` 的 DER**：报出 `contentType` 的点号 OID、`digestAlgorithms`、
  证书条数、签名者条数，并对 `dwLength` 与文件对不上的记录抛
  `WImgError(kind="structure")`。新增评分组 `signature-decoding`（0.06，5 条），
  required 由 **34 → 39** 条。
- **复验**：v1.3.0 实测 Qwen **0/3**（三轮均为 **37/39**，第 1 轮正是栽在
  `f2p-signature-info-describes-the-real-signed-data` 与
  `…-is-offline-and-standard-library-only`），Opus 5 **3/3 全满**。
  `opus_score_sum (3) > qwen_score_sum (0)` → **区分度成立**。
  期间 Opus 第 1 轮撞上 `http_500 upstream unreachable`，同样单列无效槽位并重跑。
- **结论**：**有效**。「必须真正解析一种编码」比「多读几个字段」更能区分模型。
  但这一轮也暴露了一个更深的问题，见 R10。

### R10｜判据未落到操作系统机制（v1.4.0：判分期真实调用 Windows 系统服务）

对应甲方要求第 3 条「Windows 价值必须真实映射到操作系统机制」。

- **触发（自检结论）**：把 9 个评分组逐个压过一遍后发现——
  **判分套件一次 Windows API 都没有调用**（`import` 只有
  `__future__/io/pathlib/pytest/re/struct/wpeimg`）。唯一与 Windows 系统组件相关的
  是校验和那一组，而它的权威值是**构建期**离线取得后固化成常量的。换句话说，
  v1.3.0 及以前主张的是「Windows 专属**格式**与权威值来源」，不是「Windows
  **操作系统机制**」。这个差距不能用措辞掩盖，只能改判据。
- **处置**：题面新增 **F3 节**（说明判据来源，不新增实现要求），并新增评分组
  **`windows-live-services`（0.12，4 条）**，把判据来源从离线常量换成真实系统调用：
  | 系统组件 | 调用点 | 断言用途 |
  | --- | --- | --- |
  | `imagehlp!MapFileAndCheckSumW` | `verifier/tests/win_services.py` | 对样本**与判分时现场构造的变体**取权威校验和；要求 `compute_checksum()` 逐例相等，且 ≥3 个变体的权威值互不相同（硬编码答案不可能通过） |
  | `kernel32!CreateFileW` / `GetFileSizeEx` | 同上 | 用真实句柄驱动 `iter_sections()`，核对句柄长度 |
  | CRT 句柄桥 `msvcrt.open_osfhandle` | 同上 | 让被测函数面对真实系统句柄语义 |
  | `BoundedReader` | 同上 | 拒绝 `read(-1)`/`readline`/`readlines`，把「有没有整体读入」变成真实句柄上的可测属性 |
  required 由 **39 → 43** 条。**被测实现的约束不变**：仍然禁止导入 `ctypes` /
  `subprocess` / 第三方 ASN.1 库——「契约由 Windows 定义」与「实现必须自包含」
  是两条独立要求，两边不冲突。
- **同时修掉的两个判分链缺陷**（都在容器里才会暴露，本机 pytest 直跑发现不了）：
  1. `tests/run_tests.ps1` 只把**隐藏套件单个文件**复制进判分临时目录，
     同目录的 `win_services.py` 没有被 stage，容器内直接
     `ModuleNotFoundError: No module named 'win_services'`（Oracle 因此拿 0 分）。
     已改为把套件同目录的所有 `*.py` 一并 stage。
  2. 同一段里用了 `Split-Path -LiteralPath X -Parent`，该参数组合在 PowerShell 7
     下无法解析参数集，helper 目录会算成空。已改用 `[System.IO.Path]::GetDirectoryName()`。
  这两个缺陷是在跑分**之前**用「判分链模拟」（本机搭出 Harbor 布局、真跑
  `run_tests.ps1`、走 `C:\\tests` 平台通道）抓到的，因此没有浪费一整轮模型轮次。
- **复验方式**：本轮（v1.4.0）的 oracle/no-change 与模型轮次数据在
  交付目录 `README.md` 的「跑分轮次」一节；判分链本身已在跑分前用上述模拟
  确认 oracle `exit=0`（43/43）、no-change `exit=1`（33 FAIL）。
"""


def main() -> int:
    text = io.open(DOC, encoding="utf-8").read()
    if "### R8｜" in text:
        print("REFIT already carries R8 — nothing to do")
        return 0
    if HEAD_OLD not in text:
        print("FAIL: unexpected REFIT header")
        return 1
    text = text.replace(HEAD_OLD, HEAD_NEW, 1)
    # insert the new sections before the trailing "## 2. 判分绑定一致性" block
    marker = "\n## 2. 判分绑定一致性（自动核对）"
    if marker not in text:
        print("FAIL: cannot find the section-2 marker to insert before")
        return 1
    text = text.replace(marker, NEW_SECTIONS + marker, 1)
    io.open(DOC, "w", encoding="utf-8", newline="\n").write(text)
    print("REFIT updated: header rewritten + R8/R9/R10 appended")
    return 0


if __name__ == "__main__":
    sys.exit(main())

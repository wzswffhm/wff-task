# -*- coding: utf-8 -*-
"""bump_219_v13_docs.py -- 把 219 的 verifier 侧文档更新到 task_version 1.3.0。

只改「当前版本陈述」与确实过时的计数；历史对照（v1.0.0/v1.1.0/v1.2.0 的整改记录）
保持原样。
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

D = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\_qc_runs"
         r"\relaunch-20261013\staged\wfflab__wpeimg-219-v1.3.0-delivery")

EDITS = [
    ("verifier/ISOLATION.md", [
        ("# 隔离边界与适配口径（wfflab__wpeimg-219，task version 1.2.0）",
         "# 隔离边界与适配口径（wfflab__wpeimg-219，task version 1.3.0）"),
        ("口径版本：**isolation-adaptation-v3（2026-10-13）**。",
         "口径版本：**isolation-adaptation-v4（2026-10-13）**。"),
    ]),
    ("verifier/WINDOWS_VALUE.md", [
        ("# Windows 价值与采购分类说明（wfflab__wpeimg-219，task version 1.2.0）",
         "# Windows 价值与采购分类说明（wfflab__wpeimg-219，task version 1.3.0）"),
        ("与 v1.1.0 / v1.2.0 的整改记录并列归档。",
         "与 v1.1.0 / v1.2.0 / v1.3.0 的整改记录并列归档。"),
        ("- v1.2.0 新增的 A2（目录表 + Authenticode 尾部）属于 **B 级**：它提升的是题目的\n"
         "  Windows 专属语义密度与判分颗粒度（27 → 34 条），不是新增系统调用。",
         "- v1.2.0 新增的 A2（目录表 + Authenticode 尾部）与 v1.3.0 新增的 F2（自行解析\n"
         "  PKCS#7 SignedData DER：contentType OID、digestAlgorithms、证书数、签名者数）\n"
         "  都属于 **B 级**：提升的是 Windows 专属语义密度与判分颗粒度（27 → 34 → 39 条），\n"
         "  不是新增系统调用。签名记录体本身仍是 Windows 部署生态的产物（微软签发的\n"
         "  Authenticode 签名字节），但没有调用 `WinVerifyTrust` 之类的系统服务。"),
    ]),
    ("verifier/README.md", [
        ("# 判分侧材料（wfflab__wpeimg-219，task version 1.2.0）",
         "# 判分侧材料（wfflab__wpeimg-219，task version 1.3.0）"),
        ("- `task_version = 1.2.0`；**评分族只有程序化一项**：`programmatic_weight = 1.0`、",
         "- `task_version = 1.3.0`；**评分族只有程序化一项**：`programmatic_weight = 1.0`、"),
        ("- required testcase 共 **34** 条：F2P 26 条 / P2P 8 条；全过为 1，否则为 0，\n"
         "  required 缺失或未终态一律 INVALID。\n"
         "  > 34 条超出甲方「5–27 条正常」的上界，按甲方口径属于**提示人工复核**而非失败；\n"
         "  > 扩大颗粒度是本轮为拉开主模型区分度而做的有意选择，见 `REFIT-2026-10-13.md` §R8。",
         "- required testcase 共 **39** 条：F2P 31 条 / P2P 8 条；全过为 1，否则为 0，\n"
         "  required 缺失或未终态一律 INVALID。\n"
         "  > 39 条超出甲方「5–27 条正常」的上界，按甲方口径属于**提示人工复核**而非失败；\n"
         "  > 扩大颗粒度是为拉开主模型区分度而做的有意选择（1.2.0 → 1.3.0），见\n"
         "  > `REFIT-2026-10-13.md` §R8/§R9。"),
        ("- 1.2.0 新增两个程序化评分组：`data-directories`（0.08，4 条）与\n"
         "  `authenticode-detection`（0.06，3 条），对应题面新增的 A2 节。",
         "- 1.2.0 新增两个程序化评分组：`data-directories`（0.08，4 条）与\n"
         "  `authenticode-detection`（0.06，3 条），对应题面新增的 A2 节。\n"
         "- 1.3.0 新增 `signature-decoding`（0.06，5 条），对应题面新增的 F2 节：\n"
         "  `signature_info()` 必须自行走 PKCS#7 `SignedData` 的 DER，报出 contentType OID、\n"
         "  digestAlgorithms、证书条数与签名者条数，并对 `dwLength` 与文件不符的记录抛\n"
         "  `WImgError(kind=\"structure\")`。判据锚定在真实签名字节上（`offset=13824`、\n"
         "  `size=13304`、`revision=0x0200`、`certificate_count=4`、`signer_count=1`）。\n"
         "  实测依据：1.2.0 时 Qwen 三轮 34/34 全满、Opus 2/3，区分度不成立；1.3.0 加入\n"
         "  该组后 Qwen 三轮均 37/39（第一轮正是栽在签名解析），Opus 三轮 39/39。"),
    ]),
    ("verifier/evidence/README.md", [
        ("# 219 权威证据索引（task version 1.2.0）",
         "# 219 权威证据索引（task version 1.3.0）"),
        ("| 样本 sha256 | 见 `WINDOWS_VALUE.md` 第 4 节（v1.2.0、v1.1.0 与 v1.0.0 的样本**逐字节相同**，未改动） |",
         "| 样本 sha256 | 见 `WINDOWS_VALUE.md` 第 4 节（v1.3.0、v1.2.0、v1.1.0 与 v1.0.0 的样本**逐字节相同**，未改动） |"),
    ]),
]


def main() -> int:
    failures = []
    for rel, pairs in EDITS:
        p = D / rel.replace("/", "\\")
        text = io.open(p, encoding="utf-8").read()
        for old, new in pairs:
            if old not in text:
                failures.append("%s: pattern not found -> %s" % (rel, old[:70]))
                continue
            text = text.replace(old, new, 1)
        io.open(p, "w", encoding="utf-8", newline="\n").write(text)
        print("updated", rel)
    for f in failures:
        print("MISS", f)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

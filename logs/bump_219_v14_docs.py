# -*- coding: utf-8 -*-
"""bump_219_v14_docs.py -- 把 219 的 verifier 侧文档更新到 task_version 1.4.0。"""
from __future__ import annotations

import io
import sys
from pathlib import Path

D = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\_qc_runs"
         r"\relaunch-20261013\staged\wfflab__wpeimg-219-v1.4.0-delivery")

EDITS = [
    ("verifier/ISOLATION.md", [
        ("# 隔离边界与适配口径（wfflab__wpeimg-219，task version 1.3.0）",
         "# 隔离边界与适配口径（wfflab__wpeimg-219，task version 1.4.0）"),
        ("口径版本：**isolation-adaptation-v4（2026-10-13）**。",
         "口径版本：**isolation-adaptation-v5（2026-10-13）**。"),
    ]),
    ("verifier/README.md", [
        ("# 判分侧材料（wfflab__wpeimg-219，task version 1.3.0）",
         "# 判分侧材料（wfflab__wpeimg-219，task version 1.4.0）"),
        ("- `task_version = 1.3.0`；**评分族只有程序化一项**：`programmatic_weight = 1.0`、",
         "- `task_version = 1.4.0`；**评分族只有程序化一项**：`programmatic_weight = 1.0`、"),
        ("- required testcase 共 **39** 条：F2P 31 条 / P2P 8 条；全过为 1，否则为 0，",
         "- required testcase 共 **43** 条：F2P 35 条 / P2P 8 条；全过为 1，否则为 0，"),
        ("  > 39 条超出甲方「5–27 条正常」的上界，按甲方口径属于**提示人工复核**而非失败；\n"
         "  > 扩大颗粒度是为拉开主模型区分度而做的有意选择（1.2.0 → 1.3.0），见\n"
         "  > `REFIT-2026-10-13.md` §R8/§R9。",
         "  > 43 条超出甲方「5–27 条正常」的上界，按甲方口径属于**提示人工复核**而非失败；\n"
         "  > 扩大颗粒度有两个动机：拉开主模型区分度（1.2.0 → 1.3.0）与把判据锚到真实的\n"
         "  > Windows 系统服务（1.3.0 → 1.4.0），见 `REFIT-2026-10-13.md` §R8–§R10。"),
        ("- 1.3.0 新增 `signature-decoding`（0.06，5 条），对应题面新增的 F2 节：",
         "- 1.3.0 新增 `signature-decoding`（0.05，5 条），对应题面新增的 F2 节："),
        ("- 1.3.0 新增 `signature-decoding`（0.05，5 条），对应题面新增的 F2 节：\n"
         "  `signature_info()` 必须自行走 PKCS#7 `SignedData` 的 DER，报出 contentType OID、\n"
         "  digestAlgorithms、证书条数与签名者条数，并对 `dwLength` 与文件不符的记录抛\n"
         "  `WImgError(kind=\"structure\")`。判据锚定在真实签名字节上（`offset=13824`、\n"
         "  `size=13304`、`revision=0x0200`、`certificate_count=4`、`signer_count=1`）。\n"
         "  实测依据：1.2.0 时 Qwen 三轮 34/34 全满、Opus 2/3，区分度不成立；1.3.0 加入\n"
         "  该组后 Qwen 三轮均 37/39（第一轮正是栽在签名解析），Opus 三轮 39/39。",
         "- 1.3.0 新增 `signature-decoding`（0.05，5 条），对应题面新增的 F2 节：\n"
         "  `signature_info()` 必须自行走 PKCS#7 `SignedData` 的 DER，报出 contentType OID、\n"
         "  digestAlgorithms、证书条数与签名者条数，并对 `dwLength` 与文件不符的记录抛\n"
         "  `WImgError(kind=\"structure\")`。判据锚定在真实签名字节上（`offset=13824`、\n"
         "  `size=13304`、`revision=0x0200`、`certificate_count=4`、`signer_count=1`）。\n"
         "  实测依据：1.2.0 时 Qwen 三轮 34/34 全满、Opus 2/3，区分度不成立；1.3.0 加入\n"
         "  该组后 Qwen 三轮均 37/39（第一轮正是栽在签名解析），Opus 三轮 39/39。\n"
         "- 1.4.0 新增 `windows-live-services`（0.12，4 条），对应题面新增的 F3 节：\n"
         "  **判分过程本身在 Windows 上调用系统组件**——`imagehlp!MapFileAndCheckSumW`\n"
         "  对判分时现场构造的映像变体给出权威校验和；`kernel32!CreateFileW` 提供真实\n"
         "  文件句柄驱动 `iter_sections()`。封装在 `verifier/tests/win_services.py`，与隐藏\n"
         "  套件一起投放到 `C:\\tests`，候选工作区不含它。被测实现仍不得导入\n"
         "  `ctypes`/`subprocess`，两条要求相互独立。"),
    ]),
    ("verifier/evidence/README.md", [
        ("# 219 权威证据索引（task version 1.3.0）",
         "# 219 权威证据索引（task version 1.4.0）"),
        ("| 样本 sha256 | 见 `WINDOWS_VALUE.md` 第 4 节（v1.3.0、v1.2.0、v1.1.0 与 v1.0.0 的样本**逐字节相同**，未改动） |",
         "| 样本 sha256 | 见 `WINDOWS_VALUE.md` 第 4 节（v1.4.0 起各版本的样本**逐字节相同**，未改动） |"),
    ]),
]


def main() -> int:
    failures = []
    for rel, pairs in EDITS:
        p = D / rel.replace("/", "\\")
        text = io.open(p, encoding="utf-8").read()
        for old, new in pairs:
            if old not in text:
                failures.append("%s: %s" % (rel, old.splitlines()[0][:66]))
                continue
            text = text.replace(old, new, 1)
        io.open(p, "w", encoding="utf-8", newline="\n").write(text)
        print("updated", rel)
    for f in failures:
        print("MISS", f)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

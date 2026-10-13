# -*- coding: utf-8 -*-
"""update_windows_value_v14.py -- 把 WINDOWS_VALUE.md 更新到 v1.4.0 的口径。

v1.4.0 的核心变化：判分期真实调用 Windows 系统服务（imagehlp + kernel32），
因此 A 级从「构建期锚定 2 条」变成「构建期 2 条 + 判分期 4 条」。
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

D = Path(r"C:\Users\Administrator\Desktop\wff-task\harbor-windows\_qc_runs"
         r"\relaunch-20261013\staged\wfflab__wpeimg-219-v1.4.0-delivery")
DOC = D / "verifier" / "WINDOWS_VALUE.md"

REPLACEMENTS = [
    # --- header / 口径版本 ---
    ("# Windows 价值与采购分类说明（wfflab__wpeimg-219，task version 1.3.0）",
     "# Windows 价值与采购分类说明（wfflab__wpeimg-219，task version 1.4.0）"),
    ("> **口径版本**：`windows-value-mapping-v2`（2026-10-13；v1 的过度声明已按 §2.2 更正）。",
     "> **口径版本**：`windows-value-mapping-v3`（2026-10-13；v1 的过度声明已按 §2.2 更正，\n"
     "> v3 追加 v1.4.0 的「判分期真实系统调用」一组）。"),

    # --- §1 结论表 ---
    ("| 证据强度构成 | **A 级 2 条**（校验和相关，含系统库调用留档）+ **B 级 7 条**（PE 格式与生态语义）+ C 级 1 条 |",
     "| 证据强度构成 | **A 级 6 条**：构建期锚定 2 条（校验和，含系统库调用留档）+ **判分期真实系统调用 4 条**（`windows-live-services`）；**B 级 8 条**（PE 格式与生态语义）；C 级 1 条 |"),

    # --- §2.2 分级小结 ---
    ("""| 级别 | 条目 | 说明 |
| --- | --- | --- |
| **A** | #2、#3（+ 作为约束的 #11） | **唯一真正和 Windows 系统组件绑定的一组**：权威校验和只能由 `imagehlp.dll` 给出，来源脚本与 10 条结果都留档可复算。判分时用常量比对（离线固化），因此**依赖在构建期真实发生、在判分期以常量形式生效**——这一点在旧版说明里没写清，现已补明 |
| **B** | #1、#4–#9 | 语义由 PE/COFF 规范与 Windows 生态定义，换平台没有对应物（被测对象消失）；但**判分不触发系统调用**。这类是「Windows 专属格式/生态知识」，不是「操作系统机制」 |
| **C** | #10 | 换平台不变，不计入 Windows 价值 |

**诚实边界**：这道题**没有**在判分时调用注册表、NTFS、Win32 句柄、命名对象或任何系统
服务。主张的 Windows 价值是「**被测对象 + 权威判据来自 Windows**」，其中最硬的
一条是 A 级校验和（有系统库调用留档）。B 级条目不应被表述成「依赖加载器语义」，
上面已按此更正。""",
     """| 级别 | 条目 | 说明 |
| --- | --- | --- |
| **A（判分期真实调用）** | #13（`windows-live-services` 的 4 条） | 判分**过程本身**在 Windows 上调用系统组件：`imagehlp!MapFileAndCheckSumW` 对**判分时现场构造**的映像变体给出权威值；`kernel32!CreateFileW` 提供真实文件句柄，`GetFileSizeEx` 核对句柄长度。这 4 条断言离开 Windows 无法执行，判据不再依赖任何离线常量 |
| **A（构建期锚定）** | #2、#3（+ 作为约束的 #11） | 权威校验和的来源脚本与 10 条结果留档可复算；这一组的常量比对现在被 #13 的活体调用覆盖与复核，两者互为交叉验证 |
| **B** | #1、#4–#9、#12 | 语义由 PE/COFF 规范与 Windows 生态定义，换平台没有对应物（被测对象消失）；判分只做离线字节比对，不触发系统调用。这类是「Windows 专属格式/生态知识」，不是「操作系统机制」——本说明不再把它表述成「依赖加载器语义」 |
| **C** | #10 | 换平台不变（`io.BytesIO` 上的有界读），不计入 Windows 价值；真实句柄上的同类判据已提升为 A 级 #13 |

**诚实边界（v1.4.0 起）**：这道题现在**确实在判分期调用了 Windows 系统组件**——
`imagehlp.dll` 与 `kernel32.dll`，用途分别是「权威校验和的唯一来源」与「真实文件
句柄」。它仍然**没有**触及注册表、服务控制管理器、安全描述符、命名对象、进程/线程
调度或内核对象生命周期那些更深层的机制；B 级条目依旧只是 Windows 专属的格式与
生态语义。"""),

    # --- §2.3 复核路径 ---
    ("""### 2.3 A 级这一条的评测期复核路径

想在不改题目契约的前提下**在评测环境里就地复核** A 级依赖，可在 Windows 容器内跑
（只读探针，不属于判分路径，也不改变评分）：

```powershell
# 容器内（Windows）：用系统库重取权威值，与试卷常量对照
python verifier\\evidence\\authoritative.py
# 期望：10 条 status=0，且 checksum 与 verifier/tests 的 AUTHORITATIVE 常量逐条相同
```

这条探针**调用的就是 Windows 系统库本身**，因此它证明的是「试卷常量 = 本机
`imagehlp` 的答案」，而不是「作者声称如此」。""",
     """### 2.3 判分期系统调用的落点与复核路径

`windows-live-services` 组由 `verifier/tests/win_services.py` 提供封装，全部在
**判分侧**（`C:\\tests` 下），候选工作区里没有它：

| 系统组件 | 调用点 | 断言用途 |
| --- | --- | --- |
| `imagehlp!MapFileAndCheckSumW` | `win_services.live_checksum()` | 对样本与**判分时构造的变体**取权威校验和，要求 `compute_checksum()` 逐例相等；并额外要求 ≥3 个变体的权威值互不相同，使硬编码答案无法通过 |
| `kernel32!CreateFileW` / `GetFileSizeEx` | `win_services.open_real_handle()` | 用真实句柄驱动 `iter_sections()`，并核对句柄长度与文件长度一致 |
| CRT 句柄桥（`msvcrt.open_osfhandle`） | `win_services.handle_to_file()` | 把 Win32 HANDLE 交给 Python 文件对象，使被测函数面对的就是系统句柄语义 |
| 无界读检测 | `win_services.BoundedReader` | 拒绝 `read(-1)`/`readline`/`readlines`，把「有没有整体读入」变成真实句柄上的可测属性 |

复核方式：这几条断言**每次判分都在跑**，无需额外探针。若系统组件缺失，套件会以
`pytest.fail` 显式报出（判分环境故障，而不是静默跳过）——因为「判据没生效」本身
就是必须暴露的问题。构建期那一组的复核路径仍是：

```powershell
python verifier\\evidence\\authoritative.py
# 期望：10 条 status=0，且 checksum 与 verifier/tests 的 AUTHORITATIVE 常量逐条相同
```"""),

    # --- §5 边界 ---
    ("""- **判分期不调用任何系统组件**：A 级那两条的 Windows 依赖发生在**构建期**（取权威
  值时真的调了 `imagehlp!MapFileAndCheckSumW`），判分时以常量比对生效。评测期若
  要就地复核这条依赖，跑 §2.3 的只读探针即可。""",
     """- **判分期确实调用系统组件**（v1.4.0 起）：`imagehlp!MapFileAndCheckSumW` 与
  `kernel32!CreateFileW` 都在判分过程中被真实调用，落点见 §2.3。构建期锚定的那一组
  仍然保留，两者互为交叉验证。"""),
    ("""- **不声称** B 级条目是「操作系统机制」：它们是 Windows 专属的格式与生态语义，
  判分只做离线字节比对。若甲方要求「必须触发系统调用才算 Windows 价值」，则本题
  只有 A 级两条满足，需要按 §2.3 的方式补强或改用更强的 OS 语义（例如把
  `iter_sections` 改成必须在真实 Windows 文件句柄上有界读取）。""",
     """- **不声称** B 级条目是「操作系统机制」：它们是 Windows 专属的格式与生态语义，
  判分只做离线字节比对。v1.4.0 已经把原先属于这一类的两件事（权威校验和、
  `iter_sections` 的读取上界）提升为判分期的真实系统调用，因此 A 级不再是「只有
  构建期锚定」；仍未覆盖的是注册表、安全模型、进程/线程、内核对象生命周期等更深
  的机制。"""),
    ("""- v1.2.0 新增的 A2（目录表 + Authenticode 尾部）与 v1.3.0 新增的 F2（自行解析
  PKCS#7 SignedData DER：contentType OID、digestAlgorithms、证书数、签名者数）
  都属于 **B 级**：提升的是 Windows 专属语义密度与判分颗粒度（27 → 34 → 39 条），
  不是新增系统调用。签名记录体本身仍是 Windows 部署生态的产物（微软签发的
  Authenticode 签名字节），但没有调用 `WinVerifyTrust` 之类的系统服务。""",
     """- v1.2.0 新增的 A2（目录表 + Authenticode 尾部）与 v1.3.0 新增的 F2（自行解析
  PKCS#7 SignedData DER：contentType OID、digestAlgorithms、证书数、签名者数）
  都属于 **B 级**：提升的是 Windows 专属语义密度与判分颗粒度（27 → 34 → 39 条），
  不是新增系统调用。签名记录体本身仍是 Windows 部署生态的产物（微软签发的
  Authenticode 签名字节），但没有调用 `WinVerifyTrust` 之类的系统服务。
- v1.4.0 新增的 F3（`windows-live-services`，4 条）是 **A 级**：它不要求实现增加
  功能，而是**换掉判据的来源**——权威校验和改为判分时向 `imagehlp` 现取，流式
  契约改为在 `CreateFileW` 的真实句柄上验证。颗粒度 39 → 43 条。"""),
    ("- 未新增需求，因此**不追溯扣旧样本**：v1.0.0 / v1.1.0 / v1.2.0 的历史轨迹与分数保持原样，\n  本说明与三轮整改记录并列归档。",
     "- 未新增需求，因此**不追溯扣旧样本**：v1.0.0 / v1.1.0 / v1.2.0 / v1.3.0 的历史轨迹与分数保持原样，\n  本说明与四轮整改记录并列归档。"),
]


def main() -> int:
    text = io.open(DOC, encoding="utf-8").read()
    failures = []
    for old, new in REPLACEMENTS:
        if old not in text:
            failures.append(old.splitlines()[0][:78])
            continue
        text = text.replace(old, new, 1)
    io.open(DOC, "w", encoding="utf-8", newline="\n").write(text)
    if failures:
        print("MISS:")
        for f in failures:
            print("  -", f)
        return 1
    print("WINDOWS_VALUE.md updated (%d replacements)" % len(REPLACEMENTS))
    return 0


if __name__ == "__main__":
    sys.exit(main())

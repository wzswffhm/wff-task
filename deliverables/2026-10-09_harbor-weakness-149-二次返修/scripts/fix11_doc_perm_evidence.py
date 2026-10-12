# -*- coding: utf-8 -*-
"""用真实解压器的实测结果替换 §10.1（此前误用 python extractall 得出的结论）。"""
import pathlib
import sys

sys.stdout.reconfigure(encoding='utf-8')
DOC = pathlib.Path(r'C:\Users\Administrator\Desktop\wff-task\harbor-weakness'
                   r'\work_fin-b01_20261011_fix11-149\交付文档.md')
NEW = 'work_fin-b01_20261011_fix11-149'
t = DOC.read_bytes().decode('utf-8')
NL = '\r\n' if '\r\n' in t else '\n'

# 定位 §10.1 到 §10.2 之间的整块，替换
i1 = t.find('### 10.1 Linux 实际解压权限实测')
i2 = t.find('### 10.2 本轮未改动项')
if i1 < 0 or i2 < 0:
    print(f'[ERR] 未定位 §10.1/§10.2: {i1} {i2}')
    sys.exit(1)

new_block = f'''### 10.1 Linux 实际解压权限实测（对照报告要求）

报告要求「确认实际 Linux 解压后为 0755」。本轮在 WSL 内用**两个独立的真实 Linux 解压器**解压后 `stat` 实测：

| 包 | 脚本条目 | `create_system` | 高位 mode | **解压后实际权限** |
|---|---|---|---|---|
| `{NEW}.zip` | `solution/solve.sh` | 3 (Unix) | `0o100755` | **755** ✅ |
| `{NEW}.zip` | `tests/test.sh` | 3 (Unix) | `0o100755` | **755** ✅ |
| `FIN3-WKN-149_task.zip` | `tests/test.sh` | 3 (Unix) | `0o100755` | **755** ✅ |
| `FIN3-WKN-149_answer.zip` | `solution/solve.sh` | 3 (Unix) | `0o100755` | **755** ✅ |
| *对照*：`work_fin-b01_20261011_fix10-149.zip`（修复前） | 两脚本 | **0 (DOS)** | `0o100755` | **644** ❌ |

**解压器交叉验证**（两者结论一致）：

| 解压器 | 来源 | fix11 结果 | fix10（修复前）对照 |
|---|---|---|---|
| **Info-ZIP `unzip`** | 本任务镜像 `fin3-wkn-149:local` 的 `/usr/bin/unzip` | `.sh` → **755**，目录 755，普通文件 644 | `.sh` → **644** |
| **`busybox unzip`** | `alpine:3.20` | `.sh` → **755**，目录 755，普通文件 644 | `.sh` → **644**（目录 777） |

> **缺陷机理**：ZIP 条目同时携带两种权限语义——`create_system` 指明「按哪个系统解释 `external_attr`」。Python `zipfile.ZipInfo` 默认 `create_system = 3 if os.name == "posix" else 0`，本机在 Windows 上打包 → 写出 **DOS 语义**条目。Info-ZIP `unzip` / `7z` 据此把 `external_attr` 当作 DOS 属性，**忽略高位的 Unix mode**，故实际落盘为默认 644。显式置 `create_system = 3` 后，解压器改按 Unix 语义读取高位 mode，得到 755。
>
> **自检盲区（值得记录）**：本地 `check_package_permissions.py` 仅读取 `external_attr` 高位来判断可执行位，因此**对 `create_system` 不敏感**——修复前后它都报 `0o755 带可执行位`。本轮因此额外引入**真实解压器实测**作为该缺陷的验收手段。

### 10.1.1 本地静态门禁复核（修复后）

`weakness-data-construction/scripts/check_package_permissions.py {NEW}.zip`：**FAIL 合计 0**，含
`solution/solve.sh 权限 0o755 带可执行位`、`tests/test.sh 权限 0o755 带可执行位`、
`两份 golden 逐字节一致（7 个文件）`、`批次根目录有 交付文档.md`、`无 __pycache__/.pyc 残留`。

'''
t = t[:i1] + new_block + t[i2:]

# §10 项1 闭环证据补一句真实解压器
old_ev = '① 见 §10.1 的「Linux 实际解压权限」实测表；'
new_ev = '① 见 §10.1：两个独立真实解压器（Info-ZIP `unzip` / `busybox unzip`）实测 `.sh` 解压后均为 **755**，而修复前对照包为 **644**；'
c = t.count(old_ev)
print(f'{"OK " if c == 1 else "WARN"} 闭环证据补充 {c} 处')
t = t.replace(old_ev, new_ev, 1)

DOC.write_bytes(t.encode('utf-8'))
print(f'[OK] 文档 {len(t.encode("utf-8")):,} B')

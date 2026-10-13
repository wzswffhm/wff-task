# 219 权威证据索引（task version 1.4.0）

本目录是 `wfflab__wpeimg-219` 的**权威值来源证据**，用于支撑
`verifier/WINDOWS_VALUE.md` 第 2 节的逐条映射。所有文件都是**只读留档**，
不参与判分，也不会注入 agent 容器。

## 1. 这些证据证明了什么

| 文件 | 证明 |
| --- | --- |
| `authoritative.py` | 10 个权威校验和是怎么取的：在 **Windows** 上调用 `imagehlp!MapFileAndCheckSumW` |
| `authoritative-checksums.json` | 取到的 10 个值（`status=0`），与隐藏套件 `AUTHORITATIVE` 常量逐条对应 |
| `checksum_experiment.py` | 用 Windows 原生值判定「PE 校验和只有一种正确写法」 |
| `checksum-experiment.json` | 12 个真实 Windows 二进制的比对结果：变体 A/D 吻合 12/12、变体 B 1/12、变体 C 0/12 |
| `select_pe_assets.py` | 两个样本的来源（真实 PE32+ 取自 python embed 发行包；PE32 按规范合成） |
| `probe_overlay.py` | 节区覆盖与尾部 overlay 的实测 |

## 2. 复现方式（需在 Windows 上执行）

脚本用 `--assets <目录>`（或环境变量 `WPEIMG_ASSETS`）定位样本，
默认回退到 `environment/workspace/assets`：

```powershell
$A = '<包根>\environment\workspace\assets'
python evidence\authoritative.py --assets $A
python evidence\checksum_experiment.py --assets $A
python evidence\select_pe_assets.py --out $A --check
python evidence\probe_overlay.py --assets $A
```

## 3. 本次记录的执行环境

| 项 | 值 |
| --- | --- |
| 取得日期 | 2026-10-11（v1.0.0 构建期） |
| 平台 | Windows（Docker Desktop Windows 容器模式宿主） |
| 取权威值的库 | `imagehlp.dll`，导出 `MapFileAndCheckSumW` |
| 样本 sha256 | 见 `WINDOWS_VALUE.md` 第 4 节（v1.4.0 起各版本的样本**逐字节相同**，未改动） |

> **边界声明**：这些脚本是留档，不是判分路径。判分完全在隐藏套件里用**常量**
> 比对，因此判分期不依赖任何 Windows 组件——这既保证可复现，也保证
> 「契约值来自 Windows、实现自己算」这两件事被分开验证。

---
name: OBM-run-qc
description: 用于 OBM 题目的本地跑题和质检。用户说“质检”时调用最新本地质检工具；用户说“跑题 N 个”时按冻结候选、Docker Linux、Doubao-Seed-Evolving 和独立 verifier 执行 N 个题。仅处理本地文件，不自动上传飞书或把密钥写进日志。
---

> **子流程：本地跑题与质检**
> 本目录是 OBM skill 的子流程之一，由主目录 `../../SKILL.md` 路由进入。

# OBM 跑题与质检

这是一个可移交的本地入口。收到中文指令后按下面的意图路由：

- “质检”“帮我质检某个包/某个目录/某个 ID”：执行 `scripts/obm-dispatch.ps1 -Action qc`。未给路径时扫描配置的 `result` 目录；给了 ZIP 时先解压到 `cache`，不修改原 ZIP。
- “跑题”“跑 N 个题”：执行 `scripts/obm-dispatch.ps1 -Action run -Count N`。只选有冻结清单的候选，从全新工作区运行 no-skill；当前批次的 item2 规则下，no-skill 未解且至少 100 步才运行同一冻结输入的 with-skill。

## 固定边界

- 所有解压、运行日志、轨迹、工作区、报告和截图只放在 `cache`；交付物才放在 `result`。
- 运行前确认 Docker context 为 `desktop-linux`、server OS 为 `linux`。任务容器必须 `--network none`，使用配置中的冻结镜像 ID；不要把容器外的网络状态当作任务解法证据。
- 模型固定为 `doubao-seed-evolving`，通过 Agent Plan；密钥只从 DPAPI 文件或进程环境变量读取，绝不写入命令行、配置、日志、截图或 ZIP。
- 独立 verifier 才能决定 solved。Trae 自报成功、退出码为 0 或自测通过都不能代替 verifier。
- `AccountQuotaExceeded`、Docker 创建失败、网络/磁盘/运行器崩溃属于基础设施中断，不算题目失败；保留中断记录并报告。
- 质检默认先跑最新版 `validate_proposals.py`，再跑 `obm_inventory.py` 生成绑定证据；需要完整审查时再跑 `git_provenance.py`、`obm_hack_scan.py`、`benchmark_evidence.py`、`validate_review_payload.py` 和 `sha256_manifest.py`。不自动改变飞书状态。

## 入口

先复制 `config/obm.paths.example.json` 为 `config/obm.paths.json`，按机器修改路径。然后执行：

```powershell
& .\scripts\obm-dispatch.ps1 -Action qc -InputPath 'D:\hc\obm\result\some-task.zip'
& .\scripts\obm-dispatch.ps1 -Action qc                 # 扫描 result
& .\scripts\obm-dispatch.ps1 -Action run -Count 2
```

详细参数、候选选择和报告位置见 [references/dispatch.md](references/dispatch.md)。本包内 `vendor/` 是当时打包的规则快照；正式运行仍以目标机器上配置的最新 `质检工具/obm-review-skills` 和正式需求为准。

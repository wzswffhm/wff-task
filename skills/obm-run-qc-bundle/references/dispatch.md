# 入口说明

## 第一次使用

1. 把 `config/obm.paths.example.json` 复制为同目录的 `obm.paths.json`。
2. 按目标机器修改 `obm_root`、`cache_dir`、`result_dir`、`qc_tool_dir`、正式需求路径和 benchmark workspace 路径。
3. 确认目标机器已安装 Python、Docker Desktop Linux engine 和 Trae runner；镜像字段应填冻结镜像 ID，而不是未经核验的 tag。
4. 如果用 DPAPI，`run-trae-arm.ps1` 的 `SecretFile` 必须指向目标用户自己的密文文件；不要复制本机密文，也不要把 key 放进本包。

## 质检

```powershell
& .\scripts\obm-dispatch.ps1 -Action qc -ConfigFile .\config\obm.paths.json
& .\scripts\obm-dispatch.ps1 -Action qc -InputPath 'D:\hc\obm\result\题目.zip'
& .\scripts\obm-dispatch.ps1 -Action qc -InputPath 'D:\hc\obm\cache\runs\某批次\candidates\某题'
```

报告写在 `cache\dispatch\<时间戳>\`，包括 `validator-report.json`、inventory 证据、SHA-256 清单和 `dispatch-summary.json`。ZIP 会先在 cache 解压，原文件不改动。入口不会更新飞书状态；人工确认后再按外部流程提交。

## 跑题

```powershell
& .\scripts\obm-dispatch.ps1 -Action run -Count 2 -ConfigFile .\config\obm.paths.json
& .\scripts\obm-dispatch.ps1 -Action run -Count 1 -InputPath 'D:\hc\obm\cache\runs\批次\candidates\候选'
```

不指定 `InputPath` 时，从 `cache\runs` 中寻找同时具备 `run-trae-arm.ps1` 和 `evidence\freeze\SHA256SUMS` 的候选，并按目录时间取前 N 个。每个候选创建新的 `attempt-xxx`，先 no-skill；只有 no-skill 未通过独立 verifier 且记录至少 100 个 turns 时才启动同一 attempt 的 with-skill。运行器输出、轨迹和工作区留在候选的 `evidence\dynamic` 下，批次摘要在 dispatch 目录。

`AccountQuotaExceeded`、Docker API/容器创建错误、超时或 runner 崩溃会标记为 `infrastructure_interruption`，不计作题目失败。不要删除该候选的冻结目录，也不要复用中断工作区；修复环境后重新发起即可。

## 口令映射

| 用户说法 | 入口 |
| --- | --- |
| “质检这个 zip/目录” | `-Action qc -InputPath <path>` |
| “质检 result 下所有包” | `-Action qc` |
| “跑题 3 个” | `-Action run -Count 3` |
| “只跑这个候选” | `-Action run -Count 1 -InputPath <candidate>` |

这套入口只负责本地运行和报告，不会猜测缺失候选、伪造达标、读取隐藏 verifier、上传飞书或泄露凭据。

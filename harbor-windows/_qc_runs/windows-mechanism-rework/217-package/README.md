# 217 题包参考（generate-win 路线的实际产物）

## 这是什么

`wfflab__wreparse-217`（NTFS 重解析点安全遍历与确定性审计）的题包副本。
它是**用 `generate-win` 那条路线做出来的、真正依赖 Windows 专属机制**的题：

- 题面首句：`# WReparse：NTFS 重解析点的安全遍历与确定性审计`
- 平台钉死：`Windows + Windows PowerShell 5.1 + NTFS`，不得依赖管理员权限
- 验收 16+ 条全部绑定 NTFS reparse point 语义（junction / 符号链接 / 硬链接的 `ReparseKind` 区分、
  `InScope` 目录边界判定、相对目标按链接所在目录解析、序数排序 vs culture 敏感排序）
- 曾按旧版甲方 `run_qc.py` 通过 QC（30 项），资质记录 Opus 3 > Qwen 2

**用途**：作为"同一批工具链能否产出合规 Windows 机制题"的存在性证据，
以及返修选题时的题材参照（甲方 48 题体系中对应 007 `win-reparse-002` / 017 `windows-junction-boundary-002`，
两题均被评为 Windows 价值高）。

## 来源与复现

```text
zip:  deliverables/2026-10-09_wreparse217-加深L4/package/wfflab__wreparse-217-v1.2.0-delivery.zip
```

本目录**不含 `jobs/`**（162 个文件，属冗余）。需要复核 job 归档层时重新解压该 zip 即可：

```powershell
Expand-Archive -Path <上面的 zip> -DestinationPath <临时目录> -Force
python ..\validate_217_jobs.py        # 用甲方最新 validate_model_jobs.py 校验 jobs 层
```

## 已做的实测结论（2026-10-14）

用甲方**最新** `validate_model_jobs.py`（`harbor-windows/_reference/windows-harbor-qc/scripts/`）
校验 217 的 `jobs/`：**pass = False，20 条错误** —— 缺 `jobs/{config,lock,result}.json` / `job.log`、
含 `result.json` 的 job 目录数不是 14、模型与 oracle/nop 计数全为 0。

> 口径说明：217 是 2026-10-07 的产物，甲方 job 层规范其后有更新，**不能据此说 217 当时不合格**。
> 这条实测要说明的是：**沿用 generate-win 的归档形态直接交付，在今天的甲方校验下必然 FAIL**，
> job 层必须另做协议转换（`cases[]` + `status`、`verifier/verifier.log`、
> `ctl-oracle-*` / `ctl-nop-*` 语义目录名、`task_checksum` = 交付包 Harbor dirhash）。
>
> 原始结果：`../validate-217-jobs-result.json`；脚本：`../validate_217_jobs.py`。

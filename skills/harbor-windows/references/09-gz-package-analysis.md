# 09 · 现包实测分析：`Windows_SWE_d70d30df` 27 题

来源：对 `C:\Users\Administrator\Desktop\Windows_SWE_d70d30df_27题_供应商完整脱敏包_含外部镜像_修正版.gz` 的实测
分析日期：2026-09-29

> **定位**：这是一份**别人提供的产出**，**不一定可交付**。以下分析用于说明"现包长什么样"与"距离规范还差什么"。
> **一切以 PDF 交付规则为准**（本 skill 各 reference 文件）。

---

## 一、包基本信息

| 项 | 内容 |
|---|---|
| 包名 | `Windows_SWE_d70d30df_27题_供应商完整脱敏包_含外部镜像_修正版` |
| 来源提交 | `d70d30dfc0593490e975734dc5a7559c346f623d` |
| 原始主集 | 29 题 → **交付 27 题** |
| 移除题目 | `canonical__multipass-4205`、`helidon-io__helidon-9685` |
| 归档格式 | 实际为 **tar.gz**（扩展名只写 `.gz`） |
| 条目总数 | **371** 个 |
| 镜像 | `skylensage-sg-registry.ap-southeast-1.cr.aliyuncs.com/public/public-test` |

### 文件类型分布

| 数量 | 扩展名 | 说明 |
|---|---|---|
| 165 | （目录） | |
| 56 | `.json` | 27 个 harbor JSON + 27 个 swelive_spec + 元数据 |
| 40 | `.py` | grade.py ×27 + target_check.py ×13 |
| 29 | `.md` | instruction.md ×27 + README/审计 |
| 27 | `.toml` | task.toml |
| 27 | `.ps1` | test.ps1 |
| 27 | `.diff` | test_patch.diff |

> **重要**：包内**不含任何镜像层/大文件**，镜像全部外链到 registry。这与规范"大文件不能全挪题外"的约束需一并评估。

---

## 二、包结构

```
Windows_SWE_d70d30df_27题_供应商完整脱敏包_含外部镜像_修正版/
├── README.md
├── SANITIZATION_AUDIT.md
├── SANITIZATION_MANIFEST.json
├── EXTERNAL_IMAGES.json
├── harbor/                              # 27 个平台导入 JSON（含 patch/test_patch/problem_statement）
│   └── <task-id>.json
└── harbor-assets/
    └── <task-id>/
        ├── task.toml
        ├── instruction.md
        ├── environment/
        │   ├── Dockerfile
        │   └── workspace/.keep
        └── tests/
            ├── grade.py
            ├── swelive_spec.json
            ├── test.ps1
            ├── test_patch.diff
            └── target_check.py          # 13 题有，14 题无
```

**27 题清单**：

| # | task_id | # | task_id |
|---|---|---|---|
| 1 | Azure__azure-sdk-for-python-41822 | 15 | libsdl-org__SDL-11761 |
| 2 | containers__podman-26200 | 16 | libsdl-org__SDL-12806 |
| 3 | containers__podman-26870 | 17 | lima-vm__lima-3280 |
| 4 | dotnet__runtime-117105 | 18 | lima-vm__lima-3351 |
| 5 | dotnet__runtime-118745 | 19 | microsoft__ebpf-for-windows-4117 |
| 6 | elastic__beats-42172 | 20 | microsoft__vscode-239695 |
| 7 | electron-userland__electron-builder-8855 | 21 | moby__moby-49973 |
| 8 | gemrb__gemrb-2365 | 22 | nats-io__nats-server-6803 |
| 9 | gogf__gf-4386 | 23 | pingdotgg__t3code-2142 |
| 10 | goreleaser__goreleaser-5631 | 24 | podman-desktop__podman-desktop-13439 |
| 11 | gravitational__teleport-53067 | 25 | prometheus-community__windows_exporter-2104 |
| 12 | hashicorp__packer-13388 | 26 | rustls__rustls-2586 |
| 13 | kubernetes-sigs__headlamp-2756 | 27 | tailscale__tailscale-14669 |
| 14 | kubevirt__kubevirt-14681 | | |

---

## 三、现包已有优点（值得沿用）

### 3.1 二值评分已具备

`grade.py` 已实现规范要求的二值语义：

```python
resolved = (not candidate_failure) and infrastructure_valid
           and f2p_all_pass and p2p_all_pass and not f2p_bad and not p2p_bad
score = 1.0 if resolved else 0.0
```

### 3.2 INVALID 与 0 分严格区分（设计正确）

- **合法 0 分**：候选编译/测试收集失败（已过环境预检）→ 输出 reward=0
- **INVALID**：required 缺失/SKIP、解析失败、环境异常 → **不写 reward 产物**，exit 2
- `test.ps1` 用 `===SWELIVE_INVALID ...===` 标记区分

> 这正是规范第 6.2 / 10.3 章要求的行为。可**直接沿用这套模式**。

### 3.3 证据完整性字段

`run_evidence` 记录：`run_id`、`source_commit`、`image_digest`、`log_sha256`、
`spec_sha256`、`test_patch_sha256` + `promotion_evidence_fields_complete` 标志。

> 契合规范"跨运行身份可核对"与"3 次运行证据"的要求。

### 3.4 swelive_spec 的 verification_evidence 声明

```json
{
  "required_base_runs": 3,
  "required_oracle_runs": 3,
  "same_image_digest": true,
  "require_source_commit": true,
  "require_test_patch_sha256": true,
  "require_raw_log_sha256": true,
  "allow_missing_tests": false
}
```

> 与规范第七章稳定性、第八章多模型要求完全对齐。**这是本包最强的部分。**

### 3.5 环境落实到位

`Dockerfile` 体现了规范"离线可复现"要求：

- `ENV UV_OFFLINE="1"`（预取后离线）
- 基线 commit（`git init` + `commit --allow-empty`，不用 wall-clock）
- `COPY ["workspace/", "C:/testbed/"]`
- 环境预检 `python -c "import pytest, <pkg>"`

### 3.6 镜像已交付 Digest

`EXTERNAL_IMAGES.json` 记录了 27 题完整镜像地址、不可变 digest 和匿名拉取验收状态
（manifest 均 HTTP 200，656 个 config/layer blob 无缺失）。

> 满足规范"镜像标签不是身份，必须另存 Digest"。

### 3.7 脱敏到位

`SANITIZATION_AUDIT.md` 记录：8 处非系统账户目录替换、未修改测试/Oracle patch、
未检出高置信真实秘密（PEM/AK/SK/JWT/Bearer/签名URL 等）。

---

## 四、现包与规范的差距（必须整改）

| # | 检查点 | 规范要求 | 现包状态 | 结论 |
|---|---|---|---|---|
| 1 | **task.toml 版本** | 冻结 Schema（默认 **1.3**） | 全部 27 题为 `version = "1.0"` | ❌ 待确认/升级 |
| 2 | **无 `solution/` 目录** | 五件套含 `solution/` | 包内**只有** `environment/` + `instruction.md` + `task.toml` + `tests/`；**缺 `solution/`** | ❌ 严重缺失 |
| 3 | **F2P/P2P 声明位置** | 应在 `tests/` 中明确 required 分组 | `FAIL_TO_PASS`/`PASS_TO_PASS` 在 `harbor/*.json` 与 `swelive_spec.json`，需确认与 Harbor Verifier 一致 | ⚠️ 待核对 |
| 4 | **delivery-extras** | 必须有题外伴随材料目录 | **完全没有** | ❌ 缺失 |
| 5 | **模型运行记录** | Qwen/Opus 各 3 次 + GLM/Kimi 各 ≥1 | **完全没有** | ❌ 缺失 |
| 6 | **Golden/no-change 证据** | 3×1 / 3×0 + 干净重建 | **完全没有** | ❌ 缺失 |
| 7 | **来源与授权** | `source_and_license.json` 等 | 仅 `SANITIZATION_MANIFEST.json` 有 Hash | ⚠️ 部分 |
| 8 | **题目版本号** | 每题显式版本 + 升级记录 | 全部 `1.0`，无变更记录 | ❌ 待补 |
| 9 | **`.ap-tools`** | 需保留并区分有效工具 | **包内没有**（可能在上游包） | ⚠️ 待确认 |
| 10 | **目录名** | `outside_harbor/` + `outside_harbor-assets/` | 用 `harbor/` + `harbor-assets/` | ⚠️ 命名需对齐 |
| 11 | **旧 6 题** | 需纳入转换并做变更对比 | **不在本包**（27 题为新题主体） | ⚠️ 另需处理 |
| 12 | **tests 文件不一致** | 结构应统一 | 13 题有 `target_check.py`，14 题无 | ⚠️ 需说明理由 |

### 差距总结（三个最严重）

1. **完全没有 `solution/`** —— 规范第五章明确要求五件套，且 Golden 验证依赖参考解
2. **完全没有 `delivery-extras/`** —— 规范 5.1 明确"缺少伴随材料的题目不得验收"
3. **完全没有模型运行与对照证据** —— 规范第七、八章的核心验收依据

---

## 五、从现包可提炼的复用模式

生产新题包时，**建议沿用以下已被验证的做法**：

| 模式 | 来源 | 用途 |
|---|---|---|
| `===SWELIVE_INVALID <reason>===` 标记约定 | `test.ps1` | 区分基础设施故障与模型失败 |
| reward 三件套（txt + json + details） | `grade.py` | 评分产物完整性校验 |
| `parser(log) -> {test: status}` 契约 | `swelive_spec.json` | 结构化解析测试日志 |
| `verification_evidence` 声明块 | `swelive_spec.json` | 声明 3+3 运行要求 |
| `run_evidence` 六字段 | `grade.py` | 跨运行晋升校验 |
| `ENV UV_OFFLINE="1"` + 预取 | `Dockerfile` | 离线可复现 |
| 基线 commit（非 wall-clock） | `Dockerfile` | patch 回放基线 |
| 场景包装（`_derives`/`_first_artifact`） | `grade.py` | 处理控制台换行导致的测试名不匹配 |

> ⚠️ 但这些模式**不能替代**规范要求的结构完整性。复用模式 ≠ 可交付。

---

## 六、对 Windows-Harbor 作业的启示

若本轮任务是解析/生产 **Windows-Harbor** 类题包，应：

1. **新建自己的题包类型目录**（如 `windows-harbor/`），不与 `OBM/`、`harbor-16/`、`harbor-sota/` 混放
2. 参照本包已有的 `grade.py` / `test.ps1` / `swelive_spec.json` 模式，但**必须补齐**：
   - `solution/` 五件套
   - `delivery-extras/` 伴随材料
   - 模型运行记录与 Golden/no-change 证据
3. 目录名对齐规范：`outside_harbor/` + `outside_harbor-assets/` + `delivery-extras/`
4. `task.toml` 升级到冻结 Schema（默认 1.3）
5. 身份三元组全链统一

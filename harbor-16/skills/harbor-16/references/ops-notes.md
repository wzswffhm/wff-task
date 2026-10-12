## 需要注意的情况（必读）

完整踩坑录：[references/pitfalls.md](references/pitfalls.md)。下列为高频卡点，出题时默认按此预防。

### 环境 / 网络：多用国内镜像，禁止空等

直连 Ubuntu / npm / nodejs.org / GitHub / PyPI 极易卡死。Dockerfile 与拉源码 **默认国内镜像 + 重试**：

- **apt**：阿里云 `mirrors.aliyun.com`（含 `ubuntu-ports`）；`Acquire::Retries=5`
- **Node/npm**：`npmmirror.com`（`NVM_NODEJS_ORG_MIRROR` + `NPM_CONFIG_REGISTRY`）；node 包也从 npmmirror 下 tar
- **GitHub**：`gh` tarball / 可用加速（如 `ghfast.top` 前缀）；clone 卡住就换镜像或浅拉，**数分钟无进度立刻换路**
- **uv/PyPI/rewardkit**：国内 index；镜像 **build 期预热** `uvx ... rewardkit --help`，避免 verifier 首次下载超时
- **运行时**：OrbStack（非 Desktop）；**新题/重跑前必须清理自身产生的 Docker 网络池与残留容器**（见下「Docker 环境清理」），防止网桥耗尽与基础设施污染

### Docker 环境清理（硬规则 · 新题/重跑前必做）

凡下列时机，**先清理由本工作流（Harbor / trial / 本 agent）产生的 Docker 残留，再开跑**：

- 领取并开始 **新飞书题** 之前  
- **同一作业** 换仓 / 新时间戳目录 **重跑** 之前  
- 难度门 / 校准 job **整 job 作废重跑** 之前  
- 连续循环刚交卷、马上领下一题之前（与「领下一题」同一步完成）

**清理目标（只动自身相关，勿误删用户无关容器）：**

1. 停掉并删除已退出/残留的 Harbor trial 容器（名称或 label 含 `harbor` / 本机 job 前缀等）  
2. 删除悬空 / 无主的 Docker **network**（尤其是大量 `br-*` 式自定义网桥、harbor 创建的 network）  
3. 必要时 `docker network prune` / 清理无用 network；确认 `docker network ls` 不再堆积本流程残留  
4. 清理后短检：`docker context show` 仍为 `orbstack`；磁盘与网络池正常再 `harbor` 开跑  

**禁止：** 带着上一题泄漏的数百个 network/僵尸容器直接开 16 并发——属基础设施污染，轨迹/超时作废风险极高。  
**禁止：** 为图省事 `docker system prune -a` 无差别狂删（可删本流程残留 + dangling network；勿误伤用户点名保留的镜像/卷，除非用户授权）。

建议命令骨架（按实际名称收紧 filter；执行后确认无报错再开题）：

```bash
# 示例：清理已退出容器 + 悬空网络（按环境收紧，勿盲删用户业务容器）
docker ps -aq --filter status=exited | xargs -r docker rm -f 2>/dev/null || true
docker network prune -f
# 若 Harbor 固定前缀/label，优先按前缀删除对应 container/network
```

详情与并发注意见 [references/pitfalls.md](references/pitfalls.md)。

### 中文与 locale

`LANG=C.UTF-8`、`LC_ALL=C.UTF-8` 写入 Dockerfile 与 `task.toml` 的 environment/agent env；否则中文 instruction 会变成 `???`。

### 选题 / 难度（失败工程经验）

- **必须选大型项目**：优先中大型、活跃、可完整构建的真实工程（多模块/多目录、非玩具仓、非单文件工具集）。拒绝迷你 demo、作业级小仓、明星数很少且体量极小的仓。成功范例量级：`exfatprogs` 一类生产级工具；失败侧多为过小/过易缺陷仓。
- 功能点本身也要够重：跨文件 feature / 非单点常量修补；oracle patch 宜有实质体量（数百行级更稳），避免十行级小修。
- 小修复、单点校验通常会让 reward 偏高；选题时仍优先跨文件、可观察的真实工程问题。单批 reward 分布不是提前终止的理由；只记录是否达标。允许仅在同一冻结修订的多个**完整有效 batch**之间透明选样，并在 manifest 标明每条来源；不得隐瞒未入选 trial 或把选样集伪称为单一 batch。
- 不因 3 个 batch 的 reward 分布自动换题；只有校准、环境或题目/验证器本身失效才重开。
- 飞书题型/领域/语言与 `task.toml` 必须一致（改 feature 要同步改表）
- **领域/子领域只能用官方枚举**（计算产品 / 存储 / 数据库及其子领域原文），见 [references/domain-taxonomy.md](references/domain-taxonomy.md)；禁止自造「云存储」「文件系统」等近义说法
- workspace 可裁剪无关子树，但选题起点必须是大型项目，不能用小仓凑合

### 评测监控（勿误判）

- 勿只看 `qwen-code.txt` 体积断定卡死（session/token 可能仍在跑）
- 宣称 SUCCESS 但缺少 `reward.txt` / `reward_files` 不足 → **无效**，当基础设施失败
- **超时导致的 `reward=0` 不算有效难度样本**：timeout/cancel 等 → **整 job 作废重跑**
- **难度批次执行（硬规则，必须照做）**：
  1. 每个 job 完整启动并完成 **16** 次，同一提示词、同一冻结修订、按用户当前指示 **16 个 Docker 容器并发**：`--n-attempts 16 --n-concurrent 16 --n-concurrent-agents 16 --max-retries 3 --agent-setup-timeout-multiplier 3`
  2. 后台每分钟扫已完成的 `reward.txt` 和 trial 终态；发现 timeout/cancel/缺 reward/基础设施错误，
     只将对应 Trial 标记为无效，不把异常状态折算为 0 分；同批其他正常 Trial 仍可候选。
  3. 批次正常结束后记录完整清单并判定本批是否达标；不得因满分数量改变提示词或提前停 job。
  4. 每个 job 的原始 jobs/日志/manifest 只归档、不删改。继续时复用同一验证镜像和冻结提示词新开完整 16 次 job，直至 `16×N` 候选池可透明选出 16 条（`<1`≥13、`=1`≥1）。
- 长跑控制器用持久后台 + 单实例锁，防 IDE 收割会话
- 有效样本须正常跑完 verifier 并写出 reward；超时、缺 reward 或基础设施错误不计分，但不影响同批
  其他正常 Trial 的候选资格

### 评分与交付

- 先接 rewardkit/真实 rubrics，再跑校准与难度门（后补会作废轨迹）
- zip 的 `jobs/` **必须含** baseline/nop + oracle + 成功难度门（**smoke 可选**）；禁止空壳 `quality.toml` / 未接 rewardkit
- 改 tests/environment/instruction/solution → 整轮重跑

## 默认生产画像

除非用户当场覆盖：

- 根目录：当前 Harbor 工作区（本机默认 `/Users/mima1234/Desktop/xiangwei/AI标注/龙猫`）；任务在 `task/<作业ID>-<语义>-<语言>-<题型>[-YYYYMMDD-HHMM]/`
- 换题/验证失败重选项目 → **必须新建带分钟时间戳的目录**；同作业 ID 下 **最新时间戳 = 默认成功目录**
- Harbor `0.20.0`；容器 **OrbStack**（`docker context show` → `orbstack`）；**新题/重跑前先清理自身 Docker 网络池**
- 提示词：首版直接 **level4**，校准通过后冻结；批次 reward 分布不触发自动改写提示词（**smoke 可不跑**）
- 难度门：每个 job 固定 16 次 Trial、同一提示词、当前 16 路并发且完整跑完；可跨多个完整 job 从 `16×N` 候选池透明选出 16 条，要求 `<1` ≥13、`=1` ≥1；超时/缺 reward/基础设施错误不作为候选
- 质检综合分目标 **≥ 0.7**（5.2 分数解读）；难度筛选口径以“最终 16 条且 <1≥13、=1≥1”为准
- 默认模型：`qwen3.8-max`
- 难度门容器并发：**16**（每个 job 总试跑仍是 16、同一提示词；校准 baseline/oracle 仍保持单容器）
- 镜像复用：同一冻结修订可复用，但每批启动前必须 inspect 镜像并实际验证 Agent CLI、RewardKit 和最小项目测试；变更环境/题目/验证器即重建并重校准
- OpenAI 兼容 Base：`https://llm-sn32yenb08wvkx41.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`
- Anthropic 兼容 Base：`https://dashscope.aliyuncs.com/apps/anthropic`
- 扩展依赖全部钉版本 + `pytest-json-ctrf` + test `--ctrf`（[notes-22.md](references/notes-22.md)）
- API：只从环境 / `--ae` 注入；永不写入任务文件、聊天、zip
- 中文 instruction：`LANG=C.UTF-8`；依赖与拉仓走国内镜像
- 失败工程备份：`task/_failed_project_backups/<作业ID>/`；全量 jobs 备份：`task/_full_job_backups/<作业ID>/`（均不进上传 zip）
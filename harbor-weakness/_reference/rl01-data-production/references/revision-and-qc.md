# 返修、重跑判分与打包

## 一、甲方常见退回原因（按出现频率）

| 频次 | 问题 | 判据/整改口径 |
|---|---|---|
| 高 | 扣分项没写成 `negate = true`（负 weight 或"未违规得分"） | 见 [rewardkit-conversion.md](rewardkit-conversion.md) 坑 1 |
| 高 | likert 描述里同时留了 0–1 与 1–5 两套标度 | 删掉旧档位段，只留 1–5 整数 |
| 高 | 条数低于领域下限（法律 25/30/35） | 按缺口补条，并同时调整权重分布 |
| 高 | 跑分产物、逐条判分记录、轨迹没随包 | 打包时把 `<批次>/跑分产物与轨迹/<执行体>/` 一起打进去 |
| 高 | 声称 A2/A3、但有效三模型均分远超对应区间 | 按最终版实跑定档；改 A1 也须满足 `<0.7`，不接受用 `expected_pass_rate` 或自述分数代替轨迹 |
| 高 | 参考答案的文书数、案件数、金额或分组小计互不相符 | 回原始材料独立对数并保留不同分析单位；修正 golden 后重判 oracle |
| 中 | `solve.sh` / `test.sh` 无可执行位 | zip 内以 0755 存储 |
| 中 | 缺 `domain_l3` / `domain_l4` | 必备字段，按细分场景填写 |
| 中 | `prompt.md` 删了模板 Fairness anchor、自写了评分表述 | 恢复模板原文，只允许追加工具提示段 |
| 中 | 批次目录名用了题目编号而不是一级分类 | `供应商+领域+一级分类+时间`，返修加 `_fix<N>` |
| 中 | 维度名自造 | `dimension` 只能取 11 个固定名之一 |
| 中 | `rubrics.json` 顶层缺 `metadata.scoring.s_max` | 改为 `{"metadata":{"scoring":{"s_max":<正分池>}},"items":[…]}` |
| 低 | 权重以 10/3 为主、`+7` 缺位 | 按 [scoring-and-difficulty.md](scoring-and-difficulty.md) 第三节重排 |
| 低 | description 重复句、残留"按下列档位评分："、空 `Deliverables to inspect: .` | 用生成脚本重出 toml |
| 低 | 判据措辞与题目领域不匹配（把金融/表格用语写进法律题，如"可逐格复算的定位（单元格、公式）"） | 换成本领域可核验的定位表述（规则条款编号、协议条款序号、材料记载位置） |
| 低 | 裁判模型与参评模型同家族，存在偏好风险 | 裁判模型由规范指定（`qwen3.7-plus`），供应商不得自行更换；改为附全部逐条判分明细供交叉复核 |
| 低 | 关键轮次用了跨环境/人工重判，三模型均值可比性受影响 | 所有执行体都在统一流程内、用**最终版**题面与最终版判据重跑，并在交付文档写明 |
| 低 | 扣分项仅一条或两条同权重，或触发条件与材料无关 | 至少两条不同分值、分别对应可观察且不重复的重大错误；不得为压分虚构触发条件 |

## 一之二、把甲方意见固化成规则

每轮返修回来，先做两件事，再动手改包：

1. **逐条建映射**：甲方意见 →（问题类型 / 触发条件 / 整改动作）→ 本 skill 的哪一节。
   只写"这次改了什么"没用，下批还会犯；要写成"什么写法一定会被判不合规"。
2. **补进本文件第一节的表**或对应 reference，然后**用真实题包回归**：
   ```bash
   python scripts/gen_rubrics_toml.py <task-dir> --check   # 能否一键重出
   python scripts/validate_rubrics.py <task-dir>           # 门禁是否覆盖到这条
   ```
   门禁覆盖不到的，就该新增一条校验，别只写在文档里。

## 二、重跑判分：只重跑判官，不重跑 agent

改判据/改权重/改参考答案之后**必须重跑判分**（否则交付的逐条判分记录与判据对不上），
但模型产物可以沿用已落盘的那一份：题面 `instruction.md` 没变 → agent 那轮产物仍然有效。

用 [../scripts/rejudge_by_docker.py](../scripts/rejudge_by_docker.py)：

```bash
python scripts/rejudge_by_docker.py <task-dir> <镜像> <执行体>=<交付物目录> [...]
# 例：python scripts/rejudge_by_docker.py ./LAW-004 zq-law004:latest \
#        oracle=./LAW-004/solution/golden_output qwen=/path/to/qwen/output
```

它做的事（等价于平台判分链路）：

1. `docker run` 复用题包 env 镜像；
2. 挂载 `<task>/tests → /tests`、`<task>/environment/input_files → /app/input_files:ro`、
   该执行体的交付物目录 `→ /app/output`、一个空目录 `→ /logs`；
3. 注入 `JUDGE_API_KEY / JUDGE_BASE_URL / JUDGE_MODEL / LITELLM_LOCAL_MODEL_COST_MAP=True`；
4. `bash /tests/test.sh`，产出落在 `/logs/verifier/`。

注意事项：

- 跑命令前清掉本机代理变量（`HTTP_PROXY/HTTPS_PROXY/ALL_PROXY`），否则容器内请求会走不存在的代理；
- 一个容器 = 一条 criterion 一个会话、逐条串行，35 条约 1 小时、47 条约 2 小时；
  并发 6–8 个容器是安全的（每个 300–500 MB）；
- 判分会把 `__pycache__` 写进被挂载的 `tests/`，**打包前必须清掉**；
- 若某轮判官卡死/崩溃，看 `/logs/verifier/reward_exit_message.json` 的 `exit_code`
  （`judge:timeout / judge:api_error / judge:parse_error / …`），重跑该执行体即可。

## 三、打包与交付

```text
供应商+领域+一级分类+时间[_fix<N>]/
├── 交付文档.md                     ← 批次内容表 + 环境变量表 + 本次返修说明
├── <题目编号>/
│   ├── instruction.md  task.toml  rubrics.json
│   ├── environment/  solution/  tests/          （五件套）
└── 跑分产物与轨迹/
    ├── README.md                   ← 判分口径说明
    └── <题目编号>/
        ├── oracle/{output, reward.json, reward-details.json}
        └── <模型名>/{output, 轨迹, reward.json, reward-details.json}
```

规则：

- 目录层级固定「批次目录 → 题目目录 → 五件套」，不得多一层也不得平铺；
  一题一包时内层批次目录沿用同名，解压到同一处即合成整批。
- 返修：`[task].version` 递增补丁号（1.0.0 → 1.0.1），批次目录名加 `_fix<N>`，供应商代号不变。
- `交付文档.md` 必须含：批次内容表（条数/参考分/三模型分/均值/难度档）、环境变量表、
  本次返修逐条说明、跑分产物位置。
- 打包前清理：`__pycache__/`、`*.pyc`、`.git/`、`.DS_Store`、`reward.json` 等本地跑测残留
  （跑分产物目录里的那些是**要留**的，别混为一谈）。

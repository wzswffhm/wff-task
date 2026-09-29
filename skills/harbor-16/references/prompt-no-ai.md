## 提示词 / instruction.md：禁止 AI 痕迹（硬规则）

`instruction.md`（及飞书「instruction.md文本内容」）必须像 **真人工程师随手提需求**，不能像模型生成说明书。质检会盯文风；有 AI 腔直接不过。

**要写成这样：**

- 2–3 段口语化短文：现状哪里不对 / 要什么行为 / 兼容边界
- 具体、可观察（「点名 GPT 时盘前结构要变」），少形容词
- 语气像 issue / 同事留言，允许略不整齐，但意思清楚

**禁止（AI 痕迹）：**

- 编号验收清单、同义反复、「请确保 / ensure / properly / robustly / comprehensively」堆砌
- 泄露隐藏测试、权重、文件路径清单、补丁做法、参考实现
- 套话：`综上所述`、`值得注意的是`、`充分说明`、`显著提升`、`建议进一步优化`、`in summary`、`overall`、`it is worth noting`
- 空洞大词：`全面`、`完善的解决方案`、`高质量实现`、`端到端保障`
- Markdown 教程腔：过多标题层级、emoji、漂亮但假的「任务目标/约束/验收标准」模板骨架

写完自检：把品牌名抹掉后，读起来应像真人提的需求，而不是 ChatGPT 任务卡。

**level 口径：** 默认交付 **level4**。校准通过后冻结当前提示词；每个 16 次 job 完整结束后更新 `16×N` 候选池，直到能透明选出 16 条达标样本。只有校准失败、题目/验证器失效、完整有效 batch 的 16 条全为 `reward=0`，或用户明确要求时才新建修订。禁止开题用低 level。

更多对照见 [references/instruction-style.md](references/instruction-style.md)。
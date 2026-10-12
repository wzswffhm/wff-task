# 反模式与踩坑录（外发题包生产）

## 结构 / 交付硬伤（质检挂）

1. **缺五件套任一组件的空壳题包**：尤其 environment/requirements.txt（无依赖也要空文件）、environment/input_files/、solution/golden_output/、tests/finalize.py。
2. **Rubric 空壳**：quality.toml 只有 `[quality] version=1`、或 judge.toml/gating.toml 缺失、或未接 rewardkit —— 对应内部质检 P0-2 同型错误，必挂。
3. **改固定模板**：test.sh / finalize.py 是平台固定模板，逐字复制、含注释一并保留、不得改动；改了即无法对接平台评分链路。
4. **校准缺失**：不跑双向预检（Oracle/nop）就打包 —— 对应内部质检 P0-1，必挂。
5. **zip 带残留**：jobs/、logs/、reward.json、reward-details.json、.git/、__pycache__/、.venv/、__MACOSX/、.DS_Store、嵌套 zip、符号链接 —— 规范 8.2 第 10 项直接否决。
6. **打包层级错**：题目目录平铺在 zip 根，或多套一层 —— 必须是「批次目录→题目目录→五件套」。

## 元数据 / 一致性硬伤

7. **交付物文件名六处不一致**：instruction.md、deliverables.path、artifacts、solution/golden_output/、tests/golden_output/、judge 的 files 必须逐字节一致（含全半角、空格、下划线/连字符）；Linux 容器内 Report.docx ≠ report.docx。
8. **文件名含动态成分**：日期、时间戳、版本号 → Agent 每次生成的名字不同，criteria 与 judge 的 files 永远对不上。
9. **task_id 三处不一致**：目录名、[metadata].task_id、[task].name 的 name 段（小写连字符归一化后比较）。
10. **org 段不匹配**：[task].name 的 org 段与批次目录前缀必须同一供应商代号。
11. **权重越界**：weight 用了 3/7/10 以外值、负数 weight、非 binary 类型。
12. **criterion id 集合与 rubric_index 不一致**：judge.toml + gating.toml 的 id 必须与 [[metadata.rubric_index]] 完全一一对应。
13. **task.toml 写 workdir**：工作目录由 Dockerfile 的 WORKDIR /app 决定；[environment] 只允许规范字段表内键。
14. **task.toml 填真实密钥 / 占位符被替换**：${JUDGE_GATEWAY}/${OPENAI_API_KEY}/${OPENAI_BASE_URL} 逐字保留；题包任何位置不得有真实 token。

## 题目质量硬伤

15. **AI 腔 instruction**：编号验收清单、同义反复、「请确保/ensure/properly/robustly/comprehensively」堆砌、`综上所述`、`值得注意的是`、`显著提升`、`全面/完善的解决方案/高质量实现/端到端保障`、过多标题层级与 emoji、假 PRD 模板骨架 —— 写完把品牌名抹掉自检，应像真人工程师提需求。
16. **instruction <300 字** 或硬约束藏在括号内 —— 硬约束（禁止项/文件名/字数）必须独立段落显式写出。
17. **非真实付费场景 / adversarial 题**：任务场景必须是"有人会为此付费"的真实工作，source_note 标注来源；不接受纯粹为测 LLM 弱点设计的题目。
18. **三级分类扎堆**：同领域题目要在三级场景平均分布，不接受集中在少数标签；生产前先对齐三级类别与交付物清单再批量生产。
19. **造假/虚构源文件、未脱敏个人信息**：源文件须真实或高仿真；含身份证号/手机号等个人信息的题目必须配 gating 红线（未脱敏出现即否决）。
20. **Rubric 描述不合格**：不原子（一条评多个点）、不可验证（"出现增长"而非"增涨 65%"）、与 instruction 不一致的伪需求、互相矛盾/重复计分、粒度过碎、无锚点空洞条目（"语言流畅"）。
21. **恶意负分 / 故意设坑**：不得堆砌 negate 压分；gating 只能来自任务书明确要求或行业无争议红线，不得把冷门细节设为红线。
22. **难度定级错误**：按长程性（专家人时/必要步骤/工具类别/反馈轮次）定 L2-L5，不是"题目难不难"；expert_minutes 须与 difficulty 自洽。

## 流程硬伤

23. **没跑双向预检就打包**：Oracle ≥0.7 且 gating=1.0、空产物 ≤0.10、两次 verifier_error=0；本地自测要自己 export OPENAI_API_KEY/BASE_URL（平台不会替换 ${VAR}），没导会展开成空值导致判官全失败。
24. **SOTA 通过率不达标仍交付**：三家均分超过难度上限（L2>65% 等）禁止提交；不达标修订后重跑。
25. **提交命名错误**：单题「供应商+领域+一级分类+时间」；批次 zip「供应商+领域+批次+时间」；返修 version 递增、批次名加 _fix<N>。

## 环境 / 网络

26. 镜像直连国外源卡死 —— 统一官方 python:3.12-slim 起步，内网加速由平台下发，不写死私有镜像名。
27. 容器内必须存在 agent 用户（uid 1000）且 /app/output 可写；镜像构建后跑规范 4.2 自检命令，末行 OK 才算通过。
28. 中文字符串：LANG/LC_ALL=C.UTF-8、PYTHONIOENCODING=UTF-8 写入 Dockerfile 与 task.toml env，否则中文 instruction 变 ???。

# 题包文件说明（sources）

本目录是 `deepSWE_2026-09-28-3-marshmallow-doc-diff` 正式题包的 `sources`，逐项说明如下。

## app/
上游仓库 marshmallow 在基线提交 `c7b559a1fa3aba57ca6dba0ab336841c5038a782`（tag v4.3.1）的源码副本，已扁平化为 `app/marshmallow`（去掉上游的 `src/` 前缀）。同时包含上游的 `LICENSE`(MIT)、`README.rst`、`pyproject.toml`、`CHANGELOG.rst`、`AUTHORS.rst`、`NOTICE`，以及 Agent 环境的 `Dockerfile`。`app/upstream.tar.gz` 是该基线提交的归档，便于离线复现。

## skill/
中文专家 skill `SKILL.md`，按本题四条难点分节给出契约模型、冲突关系、决策方法与验证思路，不暴露私有辅助函数、测试名或固定断言；仅作为 with-skill 提示词上下文，不安装为项目级 skill。

## verifier/
行为级评测器：
- `grader.py`：在**已应用 Agent 补丁**的源码上运行 pytest 并解析 junit-xml，按 `config.json` 的 `f2p_node_ids` 与 `p2p_node_ids` 判定，只有全部 F2P 与全部 P2P 通过时输出 `REWARD=1`。Agent 补丁由评测编排器（`verify_agent_patch.py`）在构建评测镜像前应用到 `sources/app` 的暂存副本，`test.sh` 负责写入 `/logs/verifier/reward.json`。
- `config.json`：评测配置，含 11 个 F2P 节点与 826 个 P2P 节点。
- `tests/`：行为测试套件，其中 `test_doc_diff.py` 为新增功能测试（F2P），其余为上游回归测试（P2P）。
- `test.patch`：将 F2P 测试注入基线的工作区补丁（与 `tests/test_doc_diff.py` 内容一致）。
- `Dockerfile` 与 `test.sh`：离线评测环境；`test.sh` 为执行入口。
- `wheels/`：离线依赖（pytest 及其运行依赖，以及上游回归测试所需的 simplejson、tzdata）。

## provenance/
`provenance.json`：来源、基线提交、许可证、复现命令，以及 `app/` 下每个文件的 sha256 散列，便于复核与复算归档散列。

## 题目契约
公开任务契约在 `proposal.json` 的自然语言字段中（A 修改设想 / B 修改细节 / C Agent 任务 / D 难点），不在本目录重复。verifier 只判定可观察行为：变更记录里的 op、path 与左右值，嵌套与列表递归后的路径形态，include_unknown 与 ignore_fields 的影响，以及 dump/load/validate 是否回归；不与任何参考补丁比对。

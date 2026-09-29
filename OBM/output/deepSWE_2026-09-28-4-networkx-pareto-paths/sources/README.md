# 题包文件说明（sources）

本目录是 `deepSWE_2026-09-28-4-networkx-pareto-paths` 正式题包的 `sources`，逐项说明如下。

## app/
上游仓库 networkx 在基线提交 `7530809bfa1ea7ed6fdf918a4d1431488953cb1f`（tag `networkx-3.6.1`）的源码副本，按提交内的原始路径存放：顶层是 `networkx/` 包本体，以及 `pyproject.toml`、`README.rst`、`LICENSE.txt`、`INSTALL.rst`、`MANIFEST.in`、`requirements/`、`tools/`。**未做任何扁平化**，因此 Agent 在工作区里产生的补丁可以直接 `-p1` 应用到本目录。另含 Agent 环境的 `Dockerfile`；`app/upstream.tar.gz` 是同一提交、同一路径集合的归档（`git archive --prefix=networkx/`，只有一个顶层目录），`prepare_trae_runs` 用它解出 no-skill / with-skill 工作区。

## skill/
中文专家 skill `SKILL.md`，按本题六条难点分节（支配语义、见证路径、上界与边界、规模与确定性、三入口一致、索引变更）给出契约模型、冲突关系、决策方法、反例历史与验证思路，不暴露私有辅助函数、测试名或固定断言；仅作为 with-skill 提示词的专家上下文，不安装为项目级 skill。

## verifier/
行为级评测器，在独立干净环境中运行：
- `grader.py`：先把 F2P 套件注入 app 树（优先 `test.patch`，失败则复制 `tests/`），再用 `pristine/` 覆盖回 P2P 测试原样副本，然后分别运行 F2P 与 P2P 两套测试，按 `config.json` 的 `f2p_node_ids` 与 `p2p_node_ids` 判定；只有全部 F2P 与全部 P2P 通过时输出 `REWARD=1`。测试结果由随附的 `_obm_plugin.py` 直接记录 pytest 的 nodeid，不依赖 junit 属性格式。
- `config.json`：评测配置，含 41 个 F2P 节点与 129 个 P2P 节点（P2P 仅纳入在干净基线上稳定通过的用例）。
- `tests/`：F2P 行为测试套件（`test_pareto_paths.py`），自带独立的暴力枚举 oracle 做随机对拍，并覆盖基础前沿语义、上界与四种边界结局、异常类型、见证路径的简单性与属性精确性、纯函数与确定性、隐藏属性默认值、零属性环、无向图，以及三条耦合能力：投影入口与主入口的一致性（含双上界与可调用属性）、前沿集合与边插入顺序无关、可变图索引在增删边后与全量重算逐项一致；另含两条规模时限用例。
- `test.patch`：将 F2P 套件注入 app 树 `tests/` 的工作区补丁（与 `tests/` 内容一致）。
- `pristine/`：P2P 测试文件的原样副本，评测前覆盖回 app，防止改动在树内测试伪造回归通过。
- `_obm_plugin.py`：记录每个 nodeid 的通过/失败/跳过状态。
- `Dockerfile` 与 `test.sh`：离线评测环境；`test.sh` 为执行入口，写出 `/logs/verifier/reward.json`。
- `wheels/`：离线依赖（pytest 及其运行依赖；networkx 自身零第三方运行时依赖）。

## provenance/
`provenance.json`：来源地址、基线提交与 tag、提交时间与作者、许可证、取源通道说明、复现命令，以及 `app/` 下顶层文件的 sha256 与各目录整树散列（`networkx` 595 个文件、`requirements` 10 个、`tools` 2 个），便于复核与复算。

## 题目契约
公开任务契约在 `proposal.json` 的自然语言字段中（A 修改设想 / B 修改细节 / C Agent 任务 / D 难点），不在本目录重复。契约要求实现并导出三个互相一致的入口：`nx.pareto_paths`（返回带见证的记录）、`nx.pareto_frontier`（只返回排序后的配对，恒为主入口的投影）与 `nx.ParetoIndex`（可变图索引，支持 update_edge / remove_edge / reset / graph，且任意变更后查询结果必须等于对当前图直接调用函数式入口）。verifier 只判定可观察行为：返回的非支配组合集合与顺序、每条记录见证路径的简单性与属性精确性、三种"没有结果"结局各自的返回值或异常类型、三入口之间的一致性、索引在变更后与全量重算的一致性、可调用属性与属性名写法的等价性、前沿集合与插入顺序的无关性、纯函数与规模要求；不与任何参考补丁比对。

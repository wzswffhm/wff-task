# 题包文件说明（sources）

本目录是 `2026-09-29-1-pycasbin-decision-trace` 正式题包的 `sources`，逐项说明如下。

## app/

上游仓库 `casbin/pycasbin` 在基线提交 `bf5a94be899c3eb14e9d9509904a3b38d9f2cf71`（2026-08-13 13:58:49 +0800）的源码副本，保留仓库原始布局（`casbin/`、`tests/`、`examples/`、`pyproject.toml`、`LICENSE`、`README.md`、`CHANGELOG.md` 等），另加 Agent 环境的 `Dockerfile`、离线依赖 `wheels/`，以及该基线提交的归档 `upstream.tar.gz`（顶层目录 `pycasbin/`）。**本目录不含参考实现**：`casbin/trace.py` 与 `tests/test_decision_trace.py` 均由补丁注入。

## skill/

中文专家 skill `SKILL.md`，按本题难点分节给出契约模型、冲突关系、决策方法与验证思路，不暴露参考实现、测试名或固定断言；仅作为 with-skill 提示词上下文，不安装为项目级 skill。

## verifier/

行为级评测器：

- `grader.py`：在**已应用 Agent 补丁**的源码上运行 pytest 并解析 junit-xml，按 `config.json` 的 `f2p_node_ids` 与 `p2p_node_ids` 判定，只有全部 F2P 与全部 P2P 通过时输出 `REWARD=1`。Agent 补丁由评测编排器（`verify_agent_patch.py`）在构建评测镜像前应用到 `sources/app` 的暂存副本，`test.sh` 负责写入 `/logs/verifier/reward.json`。
- `config.json`：评测配置，含 514 个 F2P 节点与 312 个 P2P 节点。
- `tests/`：行为测试套件。`test_decision_trace.py` 为新增功能测试（F2P）；其余 10 个上游测试模块为回归测试（P2P），与 `app/` 中的副本内容一致，使评测不受 Agent 改动测试的影响。
- `examples/`：上游 `examples/` 的独立副本，供回归测试解析模型与策略文件（上游 `get_examples()` 以测试文件所在目录的 `../examples/` 为准）。
- `test.patch`：将 F2P 测试注入基线的工作区补丁（与 `tests/test_decision_trace.py` 内容一致）。
- `Dockerfile` 与 `test.sh`：离线评测环境；`test.sh` 为执行入口。
- `wheels/`：离线依赖（pytest 及其运行依赖，以及上游运行/测试所需的 simpleeval、wcmatch、bracex）。

## provenance/

`provenance.json`：来源、基线提交、许可证、复现命令，以及 `app/` 下每个文件的 sha256 散列，便于复核与复算归档散列。

## 题目契约

公开任务契约在 `proposal.json` 的自然语言字段中（A 修改设想 / B 修改细节 / C Agent 任务 / D 难点），不在本目录重复。verifier 只判定可观察行为：`enforce_traced` 返回的 `allowed` 是否与 `enforce()` 一致、`matched` 的求值顺序与早停边界、`decisive` 的归属、`effect` 的取值、空策略/禁用/`EnforceContext`/`eval()`/域与角色继承等分支，以及 `would_change` 的沙箱语义与不得污染 enforcer 的约束；不与任何参考补丁比对。

## 复现命令

```sh
docker build --network=none -t 2026-09-29-1-pycasbin-decision-trace-app sources/app
docker build --network=none --build-arg APP_IMAGE=2026-09-29-1-pycasbin-decision-trace-app -t 2026-09-29-1-pycasbin-decision-trace-verifier sources/verifier
docker run --rm --network=none 2026-09-29-1-pycasbin-decision-trace-verifier
```

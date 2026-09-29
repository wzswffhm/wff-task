# sources 文件用途说明

本目录是本题的交付资产，逐项说明如下。

- `README.md`：本说明文件，列出 `sources` 下每个文件与目录的作用。
- `app/`：题目环境。上游项目 python-diskcache 在基线提交 `323787f507a6456c56cce213156a78b17073fe00` 的源码副本、上游随包文件、`Dockerfile`（Agent 工作镜像，构建期不联网）与 `README.md`（上游项目说明）。
- `skill/SKILL.md`：中文专家解题思路，对应 `proposal.json` 中 `D_task_difficulties` 的三个难点，作为 with-skill 侧的提示词上下文使用，不安装到 `.trae/skills/`。
- `verifier/`：独立验证器。
  - `Dockerfile`：以 app 镜像为基础，离线安装 pytest，注入测试并判分。
  - `run.sh`：容器入口。先把本目录的测试覆盖到 `/app/tests`，再调用判分脚本。
  - `run_verifier.py`：判分脚本。应用 Agent 的 `model.patch`，运行 F2P 与 P2P 用例，按"缺失即失败、skipped 不算通过、重复取最差"的口径计算二元 reward，写出 `reward.json`。
  - `tests/`：注入的测试。`test_batch_atomic.py` 是新增行为测试（F2P），`test_core.py` 提供回归测试（P2P），`conftest.py` 与 `utils.py` 是测试夹具与辅助函数。
  - `wheels/`：pytest 及其运行时依赖的离线 wheel，供 `--network=none` 构建安装。
- `provenance/provenance.json`：来源记录。上游仓库地址、基线提交与提交时间、许可证、复现命令，以及 `sources/app` 下每个文件的 SHA-256，可逐文件复算。

本目录不包含参考实现、隐藏答案、私有符号说明或逐文件实现路线；专家 skill 只给可迁移的判断方法，不指向具体测试、固定输入或私有函数。

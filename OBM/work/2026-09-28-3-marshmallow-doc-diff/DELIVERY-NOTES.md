# 交付说明 — 2026-09-28-3 marshmallow-doc-diff

## 题包概览

- **任务编号**：`2026-09-28-3`
- **候选名**：`2026-09-28-3-marshmallow-doc-diff`
- **Benchmark**：deepSWE（proposal_type A，domain `deepSWE/feature_request`，related_question `etree-xml-diff-patch`，allow_network=false）
- **上游**：marshmallow，`base_commit=c7b559a1fa3aba57ca6dba0ab336841c5038a782`（tag v4.3.1，MIT，纯 Python）
- **特性**：`Schema.document_diff(left, right, *, include_unknown=False, ignore_fields=())` —— schema 感知的结构化 diff，按 `schema.fields` 声明顺序遍历、按字段类型（Nested 单值 / Nested(many=True) / List）递归，输出 `{op, path, left, right}`，path 用 `点号 + [i]`；dump/load/validate 零回归。
- **去重结论**：`distinct`（不重复）。飞书记录 `recpwudpy7nWdk`，去重判断=不重复，标注员=wff，已读回核对。

## 正式题包位置

`output/deepSWE_2026-09-28-3-marshmallow-doc-diff/`
- `proposal.json`
- `sources/app/`：扁平化 marshmallow 源码 + Dockerfile + `upstream.tar.gz`（已用 `--prefix=marshmallow/` 重新打包，单一顶层目录）
- `sources/skill/SKILL.md`（中文专家 skill，CJK=2151，已通过 `check_skill_language`）
- `sources/verifier/`：`grader.py`、`config.json`（11 F2P + 826 P2P 节点）、`test.sh`、`test.patch`、`tests/`、`wheels/`（pytest 9.1.1 + pygments + simplejson + tzdata 等 7 个 wheel）、Dockerfile
- `sources/provenance/provenance.json`
- `sources/README.md`

## 已完成的静态与行为验证

### check_package.py（静态预检）
- 方式：直接对目录运行时，因 Windows 无法设置 Unix 可执行位，仅 `test.sh`/`grader.py` 的“executable”子项报 FAIL（环境限制，见下）。
- 其余全部 PASS：9 个必交付文件齐全、benchmark 枚举正确、中文 skill 通过、Dockerfile 无网络依赖命令、`@sha256:` 基础镜像已固定、proposal 字段完整。
- 另行构造代表性交付 ZIP（强制 exec 位）并用 `check_package.py` 解析该 ZIP：`test.sh`/`grader.py` 在归档内为 `0o755`，可确认正式归档层面的可执行位正确。

### 行为验证 run_local_verifier.py（决定性门槛）
- **NOP（干净基线，无 document_diff）**：reward=0。11 个 F2P 全部失败（AttributeError，符合预期），826 个 P2P 全部通过（零回归）。
- **ORACLE（参考实现）**：reward=1。11 个 F2P 全部通过，826 个 P2P 全部通过。
- 结论：`NOP=0, ORACLE=1` 达成，奖励逻辑与 verifier 节点映射正确。

### prepare_trae_runs.py（Trae 双工作区脚手架）
- 已生成 `work/2026-09-28-3-marshmallow-doc-diff/trae-runs-v1/`
  - `3-no-skill/`（仓库 `3-no-repo`，仅任务契约 PROMPT，无专家思路）
  - `3-with-repo/`（仓库 `3-with-repo`，PROMPT 含 `## 专家解题思路`）
  - 两侧基线 HEAD 一致：`80800558e279c28afda3b892f89b1669d3b106e9`
  - `BASELINE.json`：含 upstream/proposal/skill/verifier/prompt 等散列，`prompts_identical=false`，`expected_model=Doubao-Seed-Evolving`

## 关于可执行位（Windows 环境限制）

- Windows 的 CPython `os.chmod` 无法设置 Unix 可执行位，`st_mode` 恒为 `0o666`。因此：
  1. 对“目录”直接跑 `check_package.py` 时，`test.sh`/`grader.py` 的 executable 子项必然 FAIL——这是验证环境限制，不是题包缺陷。
  2. 官方 `build_delivery_zip.py` 以 `path.stat().st_mode` 写归档，在 Windows 上也会把 `0o666` 存进 ZIP，导致其在 Linux 解出的文件无 exec 位。**不能**在 Windows 上直接用官方脚本出最终 ZIP。
- 运行时不受影响：verifier Dockerfile 第 16 行 `RUN chmod +x /verifier/test.sh /verifier/grader.py` 会在容器内补齐可执行位，ENTRYPOINT 正常执行。
- **最终打包方式（二选一）**：
  - 在 Linux/Docker 主机上用官方 `build_delivery_zip.py`（那里 chmod 生效）；或
  - 在本环境用 `work/make_delivery_zip.py`（强制把 `test.sh`/`grader.py` 写为 `0o755`）生成交付 ZIP，再补 `FINAL_CHECK` 证据。

## 本轮修订（2026-09-28 下午续做之后）

- **修复 verifier 入口与 Docker grade 的契约缺口**：官方 `verify_agent_patch.py --docker` 在容器内读取 `/logs/verifier/reward.json` 作为判分依据，而原 `test.sh` 只向 stdout 打印 `REWARD=`、向 `/verifier/report.json` 写报告，不会被读到。已将 `sources/verifier/test.sh` 改为：运行 grader 后把 `REWARD` 写入 `/logs/verifier/reward.json`（仅在该挂载卷存在时写，本地非挂载运行不受影响）。本地 `run_local_verifier.py` 仍直接跑 `grader.py` 读 stdout，不受影响，已复跑确认 NOP=0 / ORACLE=1。
- **待确认（重要）**：`verify_agent_patch.py` 从 `sources/app` 构建 app 镜像，但**不会**把 Agent 的 `model.patch` 打到 `/app/marshmallow` 上（只把 patch 存进 artifacts）。请确认你们的线上 harness 在 grade 前是否已经把 `model.patch` 应用到 `sources/app/marshmallow`（或另有应用环节）；否则 Docker grade 会一直以基线评分。如需做成自包含，我可以把补丁应用接进 app 镜像构建。
- **修复离线构建缺 wheel**：verifier 镜像 `pip install --no-index` 装 `pytest`，而 `pytest 9.1.1` 依赖 `pygments>=2.7.2`；原 `wheels/` 缺该 wheel，`--network=none` 构建会报 `Could not find a version that satisfies pygments`。已补 `pygments-2.21.0-py3-none-any.whl`，`wheels/` 现有 7 个 wheel（iniconfig / packaging / pluggy / pygments / pytest / simplejson / tzdata）。本地 `run_local_verifier.py` 因 venv 里已有 pygments 才没暴露此缺口——这正是“离线可构建”门槛的价值。

### WSL Docker 实测结果（离线 `--network=none`）

在本地 WSL（Ubuntu 22.04，Docker 29.1.3）里完整复现了 Docker grade 契约（verifier `FROM $APP_IMAGE`，容器内跑 `test.sh`，判分读 `/logs/verifier/reward.json`）：

| 场景 | app 镜像 | verifier 镜像 | F2P | P2P | reward.json |
|---|---|---|---|---|---|
| NOP（基线，无 document_diff） | `obm-app-nop` | `obm-ver-nop` | 0/11 通过 | 826/826 通过 | **0** |
| ORACLE（参考实现） | `obm-app-oracle` | `obm-ver-oracle` | 11/11 通过 | 826/826 通过 | **1** |

- 两次构建均为 `docker build --network=none`，零网络依赖成功；运行均为 `docker run --network=none -v <logs>:/logs/verifier`，容器内 `reward.json` 正确写出 `{"reward": 0}` / `{"reward": 1}`。
- 结论：**离线 Docker 构建 + 运行 + reward.json 判分契约全部跑通**，NOP=0 / ORACLE=1 在容器路径下同样成立。（注：Docker Hub 直连被墙，本机通过 registry mirror（daocloud/aliyun）拉取 `python:3.12` 基础镜像；`--network=none` 指的是构建/运行阶段不联网，与拉基础镜像解耦。）

## 全量验证（除 Trae）已完成 — 详见 `VERIFICATION-REPORT.md`

本轮把「依赖 Trae 实验结果」之外的所有可自动化验证都跑了一遍，结论：**全部通过**。

- **proposal 校验**：`validate_proposals.py`（review-skill 副本 + skill 内置副本两份）均 `[OK] / 1 passed, 0 failed`。注意 skill 内置校验要求目录名为 `deepSWE_<proposal_name>`（我最初的 WSL 测试副本被改名导致一次假 FAIL，已用规范目录名复跑通过）。
- **中文 skill**：`check_skill_language.py` PASS（汉字 2151）。
- **包预检**：Windows 下仅 exec 位 2 FAIL；在 Linux ext4 上 `chmod +x` 后 `check_package.py` **PASS (0 errors, 1 warning)**，坐实 Windows FAIL 纯属 NTFS 限制。
- **场景重合召回**：`check_scene_overlap.py` 扫 113 题（根目录应为 `Benchmark/deep-swe-prompts/tasks`，脚本按 `*/instruction.md` 发现），最高分是本题自身 registry 记录，无同仓库竞品。
- **官方 Docker 编排器**：`verify_agent_patch.py --docker` 实测 NOP `reward=0` / ORACLE（预置 `reference.patch`）`reward=1`，`status=completed`、`container_exit_code=0`；证据在 `official-docker-verify/`。
- **门禁验证**：`capture_final_check.py` 在 Linux 上三连静态检查全 PASS，`exit_codes=[0,0,0,1]`，仅因缺 `EXPERIMENT_RESULT.json` 而 `FINAL RESULT: FAIL`；`build_delivery_zip.py` 正确拒绝（"实验结果不存在"，exit 1）。

> 关键提醒：`verify_agent_patch.py` **不会**把 `--patch` 应用到 `/app`（只复制进 `/logs/artifacts/`）。ORACLE=1 是靠**预先**把 `reference.patch` 打进 `sources/app` 实现的。开始 Trae 实验前务必确认线上 harness 有「构建前应用 `model.patch` 到 `sources/app`」的环节，否则 no-skill 与 with-skill 都会得到基线分（恒 0），会使对照实验失效。

## 仍待在 Trae 主机完成的步骤（本沙箱无 Trae CLI）

1. ~~离线 Docker `--network=none` 构建验证~~ —— **已完成**（见上表，WSL 实测 NOP=0 / ORACLE=1）。
2. **Trae 双跑实验**：将 `trae-runs-v1` 两套工作区迁到 Trae 主机，分别跑 no-skill 与 with-skill，预期 no-skill reward=0、with-skill reward=1，并回填 `RUN_RECORD.md` 与生成 `EXPERIMENT_RESULT.json`。Trae 为 GUI 绑定窗口式工作流（Electron 应用，非无头 CLI），OBM 脚本只负责登记证据与判分，无法驱动 Agent 本体。
3. **FINAL_CHECK**：运行 `capture_final_check.py`，产出 `FINAL_CHECK.json` + 截图，并校验实验结果散列一致。
4. **正式打包**：满足上述 2/3 后，用上述“最终打包方式”生成交付 `.zip`（要求 `.zip` 扩展名、散列一致）。
5. **飞书提交**：按 `feishu-submission.md` 在实验 + FINAL_CHECK 通过后提交（用户驱动，尚未到达）。

## 文件清单（本工作区新生成/更新）

- `output/.../sources/provenance/provenance.json`（更新 reproduction 说明：tar 用 `--prefix=marshmallow/`）
- `output/.../sources/app/upstream.tar.gz`（重新打包为单一顶层目录 `marshmallow/`）
- `output/.../sources/verifier/wheels/pygments-2.21.0-py3-none-any.whl`（补入，修复 `--network=none` 离线构建缺依赖）
- `output/.../sources/verifier/test.sh`（补写 `/logs/verifier/reward.json`，对齐 Docker grade 契约）
- `work/make_delivery_zip.py`（Windows 下强制 exec 位的打包辅助脚本）
- `work/2026-09-28-3-marshmallow-doc-diff/trae-runs-v1/`（`prepare_trae_runs` 产物）
- `work/2026-09-28-3-marshmallow-doc-diff/scene-overlap-review.md`（去重复核记录）
- `work/2026-09-28-3-marshmallow-doc-diff/DELIVERY-NOTES.md`（本文件）

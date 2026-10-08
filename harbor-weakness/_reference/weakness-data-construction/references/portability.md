# 换电脑 / 换环境继续生产

本 skill 是自包含的（`SKILL.md` + `references/` + `scripts/` + `assets/`），
把整个目录拷过去即可。真正需要在新机器上补齐的是**运行依赖**、**judge 凭据**和**题包 env 镜像**。

## 一、要带走的东西

| 类别 | 内容 | 说明 |
|---|---|---|
| skill 本体 | `weakness-data-construction/` 整个目录 | 纯文本 + Python 脚本，无外部依赖即可读 |
| 题包 | `<批次目录>/<题目目录>/` 五件套 + `跑分产物与轨迹/` | 交付物本身 |
| 判分凭据 | `JUDGE_API_KEY` / `JUDGE_BASE_URL`（平台提供） | **只放本地文件，绝不写进 skill / 题包 / 交付文档** |
| env 镜像 | `<题号小写>__<hash>__env-main:latest` | 每题约 3.3 GB，见第四节 |

不要带走：`__pycache__/`、`*.pyc`、`rejudge/` 之类的工作目录、任何 `judge.env` 明文凭据。

## 二、依赖清单

| 依赖 | 必需性 | 用途 |
|---|---|---|
| Python ≥ 3.11 | 必需 | 所有 scripts（`tomllib` 需要 3.11+） |
| `python-docx` | 强建议 | 参考答案 `.docx` 的改稿与核验 |
| `pdfplumber` | 建议 | 读规则原文 PDF（人检要求的"条文核对"） |
| `openpyxl` | 建议 | 读材料 `.xlsx` |
| Docker（运行中） | 重跑判分必需 | `rejudge_by_docker.py` 起容器判分 |
| `harbor` CLI | 可选 | `harbor run -p <task-dir> -a oracle` 本地自测参考解 |

脚本本身只用标准库；上面三个包只在"读材料 / 改参考答案 / 锚点溯源"时需要，
缺库时 `check_rubric_style.py` 会自动跳过多材料比对，只输出待人工核实清单。

## 三、凭据怎么带

- 凭据由平台发放，**不要随 skill 或题包传播**。在新机器上写成本地文件，例如 `judge.env`：
  ```text
  JUDGE_API_KEY=<平台提供的 key>
  JUDGE_BASE_URL=<平台提供的网关地址>
  JUDGE_MODEL=qwen3.7-plus
  ```
- 重跑时用 `rejudge_by_docker.py ... --creds judge.env` 传入；该文件不要进版本库、不要打进包。
- 凭据往往有有效期：过期表现为容器内 `judge:api_error`，换新凭据重跑即可。

## 四、env 镜像怎么带

判分容器复用题包 env 镜像，两条路线任选：

1. **搬镜像（快）**：原机器 `docker save <镜像> -o law-004-env.tar`，新机器 `docker load -i law-004-env.tar`。
   注意单个 tar 约 3.3 GB。
2. **重新构建（干净）**：新机器上按题包 `environment/Dockerfile` 构建即可，镜像名自取
   （`rejudge_by_docker.py` 的第二个参数就是镜像名，不要求特定命名）。

`docker images` 里同题可能有多份 `env-main`，任取一份都行——它们是同一个 Dockerfile 构建的。

## 五、迁移步骤

```bash
# 1) 拷 skill 与题包
cp -r weakness-data-construction  <新机>/.codex/skills/
cp -r <批次目录>                   <新机>/<工作目录>/

# 2) 装 Python 依赖（按需）
pip install python-docx pdfplumber openpyxl

# 3) 准备凭据文件（不要提交）
#    参考第三节写入 judge.env

# 4) 准备判分镜像（第三节/第四节）
docker load -i law-004-env.tar          # 或按 Dockerfile 重新 build

# 5) 自检：先跑不需要凭据的门禁
python scripts/validate_rubrics.py <题目目录>
python scripts/validate_task_package.py <题目目录>
python scripts/check_rubric_style.py <题目目录>
python scripts/check_package_permissions.py <包.zip>
```

第 5 步全绿再动判分；判分流程见 [revision-and-qc.md](revision-and-qc.md) 第二节
（含轮询陷阱、代理变量、中文路径等实操细节）。

## 六、移植后最小验收

| 检查 | 期望 |
|---|---|
| `validate_rubrics.py` | 全部 OK，`FAIL 合计: 0` |
| `validate_task_package.py` | `[PASS]` |
| `check_rubric_style.py` | 无 FAIL（NOTE 逐条判断是否要改） |
| `check_package_permissions.py` | `FAIL 合计: 0`（`.sh` 为 0755、LF、无残留、两份 golden 一致） |
| `rejudge_by_docker.py`（`oracle=` 参考答案） | `reward > 0.85`、`verifier_error = 0` |
| 三模型重跑 | 均值落 A1/A2/A3 区间，且与交付文档申报一致 |

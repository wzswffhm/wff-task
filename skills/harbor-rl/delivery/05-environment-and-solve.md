# environment/ 与 solution/

## 1. Dockerfile（每题一个，构建上下文 = environment/ 目录）

**公共依赖直接写全，全部走官方源**（Debian / registry.npmjs.org / pypi.org）。
**禁止使用任何国内镜像源**（npmmirror、aliyun pypi 镜像、docker registry mirror 等）——
AP 平台部署在境外，官方源直连无加速需求，国内源反而更慢甚至不可达。

```dockerfile
FROM python:3.12-slim
RUN useradd -m -u 1000 agent

# ① node/npm 是 claude CLI 的运行依赖；中文字体 + libreoffice 供交付物渲染/校验
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl git bash jq ripgrep unzip nodejs npm \
        libreoffice-calc libreoffice-writer fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# ② 预装 claude-code（钉死版本 2.1.114）：judge 在 verifier 判分容器内运行，
#    harbor 安装器不负责该容器，claude 必须镜像内预装。npm 走官方 registry。
#    版本必须钉死：评分行为随 CLI 版本漂移，不锁版本则跨批次分数不可比。
#    若基础镜像/上层环境已自带 claude，不覆盖 —— 只在缺失时安装。
#    ln 到 /root/.local/bin 的软链给 test.sh 的 PATH 前缀用（$HOME/.local/bin）。
RUN command -v claude >/dev/null 2>&1 \
      || npm install -g @anthropic-ai/claude-code@2.1.114; \
    command -v claude >/dev/null 2>&1 \
    && mkdir -p /root/.local/bin \
    && ln -sf "$(which claude)" /root/.local/bin/claude \
    && claude --version

# ③ pip 依赖：rewardkit + 基本的解析库（官方 pypi.org）
RUN pip install --no-cache-dir \
        "harbor-rewardkit[all]==0.1.7" markitdown \
        openpyxl pandas python-docx pypdf python-pptx PyYAML chardet matplotlib

# ④ 本题执行侧依赖（无依赖交空 requirements.txt）
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# ⑤ 输入材料（只读）与输出目录（agent 可写）
COPY input_files/ /app/input_files/
RUN chown -R root:root /app/input_files && chmod -R a-w /app/input_files
RUN mkdir -p /app/output && chown -R agent:agent /app/output
WORKDIR /app

# ⑥ 有 Skill 的题：把技能装进环境
COPY skills/ /skills/
```

### 有 skill 时

- `COPY skills/ /skills/`（**skill 在这里被装进环境**）。
- skills 所需依赖**仍写入 `environment/requirements.txt`**，按原模板在构建期安装。
- 确保**实际 Agent 用户**能读取技能及引用资料、执行脚本，且**任务书中的路径与镜像一致**。

## 2. 镜像硬性要求与自检

| 要求 | 安装自检 |
|---|---|
| **Python ≥ 3.12**，且有 `python3` | `FROM python:3.12-slim` / `python3 -V` |
| 有 **bash** | 基础镜像自带；`*-alpine` 需 `apk add --no-cache bash` / `bash --version` |
| 有 **nodejs / npm**（claude CLI 运行依赖） | `apt-get install nodejs npm` / `node -v` |
| 有 **claude 可执行，版本含 `2.1.114`**（judge 用，verifier 容器内平台不代装） | 见模板 ② 预装块 / `claude --version` |
| **`harbor-rewardkit[all]==0.1.7`**，且 `rewardkit` 在 root 的 PATH 上 | `pip install --no-cache-dir "harbor-rewardkit[all]==0.1.7"` / `rewardkit --version` |
| pip 已装文档解析库（markitdown / openpyxl / python-docx / python-pptx / pypdf 等）——judge 读取交付物都依赖它们，**缺装会导致判官读不了二进制交付物、大面积判负** | 见模板 ③④ / `markitdown --help` / `python3 -c "import openpyxl,docx,pptx,pypdf"` |
| 存在 **agent 用户**，且对 `/app/output` 可写 | `useradd -m -u 1000 agent` + `chown -R agent:agent /app/output` / `su agent -c "touch /app/output/.w && rm /app/output/.w"` |

### 构建后整体自检（末行打印 `OK` 才算通过）

```bash
docker build -t fin-t2-001 environment/
docker run --rm --network none fin-t2-001 bash -lc '
  python3 -V && bash --version | head -1 && node -v &&
  claude --version | grep -q 2.1.114 &&
  rewardkit --help >/dev/null && markitdown --help >/dev/null &&
  python3 -c "import openpyxl, docx, pptx, pypdf" &&
  pip show harbor-rewardkit | grep ^Version: && pip check &&
  id agent && su agent -c "touch /app/output/.w && rm /app/output/.w" && echo OK'
```

## 3. environment/input_files/

- 该场景真实交付物用什么源文件就用什么源文件；**真实或高仿真数据**，匿名化/脱敏（不虚构、不含真实涉密或敏感个人信息）。
- 容器内路径固定 `/app/input_files/`（只读，`chmod -R a-w`）。
- 单个题包计入整批 ≤20 GB。

## 4. solution/solve.sh

```bash
#!/bin/bash
set -euo pipefail
mkdir -p /app/output
cp -R /solution/golden_output/. /app/output/
```

要求：
- 运行后**参考答案主分须 > 0.85**。
- 参考答案的文件名、格式、数量与 `instruction.md`、`[[metadata.deliverables]]` **严格一致**。
- 参考答案须**满足 Rubric 全部正分项**、**不得命中任何 negate 扣分条目**。
- `solution/golden_output/` 与 `tests/__golden_output/` **内容一致**，目录均**不得为空**。
- 文件为 **LF 换行且带可执行位**：`chmod +x solution/solve.sh tests/test.sh`。

## 5. 本地预检命令

```bash
export JUDGE_API_KEY=<key> JUDGE_BASE_URL=<url>   # 本地自测自己导；task.toml 保持 ${VAR:-} 占位
harbor run -p <题目目录> -a oracle                # 正向：Oracle 产物主分 > 0.85
```

> 本地自测时平台不会替换 `${VAR}`，没导 KEY 会展开成空值导致判官全失败 → `verifier_error = 1`。
> 若本地想验证"评分不可用"路径，可**故意清空 `JUDGE_API_KEY`**，检查 `reward_exit_message.json` 是否出现且 `exit_code` 归类正确（自检第 16 项）。

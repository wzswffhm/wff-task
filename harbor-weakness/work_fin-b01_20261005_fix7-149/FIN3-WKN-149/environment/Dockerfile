FROM python:3.12-slim

RUN useradd -m -u 1000 agent

# ① node/npm 是 claude CLI 的运行依赖；中文字体 + libreoffice 供交付物渲染/校验
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl git bash jq ripgrep unzip nodejs npm \
        libreoffice-calc libreoffice-writer fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# ② 预装 claude-code（固定版本 2.1.114）：judge 在 verifier 中非交互运行，
#    harbor 不代装。若基础镜像已自带 claude 则复用，仅在缺失时安装。
#    ln 到 /root/.local/bin 是因为 test.sh 会把 $HOME/.local/bin 放到 PATH 前。
RUN command -v claude >/dev/null 2>&1 \
      || npm install -g @anthropic-ai/claude-code@2.1.114; \
    command -v claude >/dev/null 2>&1 \
    && mkdir -p /root/.local/bin \
    && ln -sf "$(which claude)" /root/.local/bin/claude \
    && claude --version

# ③ pip 安装 rewardkit + 判官读交付物所需的解析库（官方 pypi.org）
RUN pip install --no-cache-dir \
        "harbor-rewardkit[all]==0.1.7" markitdown \
        openpyxl pandas python-docx pypdf python-pptx PyYAML chardet matplotlib

# ④ 任务执行侧依赖（本题未使用额外依赖，requirements.txt 为空文件）
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY input_files/ /app/input_files/
RUN chown -R root:root /app/input_files && chmod -R a-w /app/input_files

RUN mkdir -p /app/output && chown -R agent:agent /app/output

WORKDIR /app

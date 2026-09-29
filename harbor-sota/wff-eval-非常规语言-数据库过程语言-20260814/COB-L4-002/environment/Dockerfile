FROM python:3.12-slim

ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONIOENCODING=UTF-8 \
    DEBIAN_FRONTEND=noninteractive

# agent 用户（uid 1000）
RUN useradd -m -u 1000 agent

# 迁移目标语言工具链：JDK 21（含 javac/java）
RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-21-jdk-headless \
    && rm -rf /var/lib/apt/lists/*

# 平台评分组件
RUN pip install --no-cache-dir "harbor-rewardkit[all]==0.1.7"

# 任务依赖（构建期预装；本题 Java 迁移无 Python 依赖，保留空文件）
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# 输入文件只读
COPY input_files/ /app/input_files/
RUN chown -R root:root /app/input_files && chmod -R a-w /app/input_files

# 输出目录归 agent 可写
RUN mkdir -p /app/output && chown -R agent:agent /app/output

WORKDIR /app
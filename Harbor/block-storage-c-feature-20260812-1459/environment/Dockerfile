FROM ubuntu:24.04@sha256:4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONIOENCODING=UTF-8 \
    NVM_DIR=/root/.nvm \
    NVM_NODEJS_ORG_MIRROR=https://npmmirror.com/mirrors/node \
    NPM_CONFIG_REGISTRY=https://registry.npmmirror.com \
    UV_INDEX_URL=https://mirrors.aliyun.com/pypi/simple \
    PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple

RUN sed -i 's|http://ports.ubuntu.com/ubuntu-ports/|http://mirrors.aliyun.com/ubuntu-ports/|g' \
      /etc/apt/sources.list.d/ubuntu.sources \
    && sed -i 's|http://archive.ubuntu.com/ubuntu/|http://mirrors.aliyun.com/ubuntu/|g' \
      /etc/apt/sources.list.d/ubuntu.sources \
    && sed -i 's|http://security.ubuntu.com/ubuntu/|http://mirrors.aliyun.com/ubuntu/|g' \
      /etc/apt/sources.list.d/ubuntu.sources

RUN apt-get -o Acquire::Retries=5 update \
    && apt-get install -y --no-install-recommends \
      autoconf \
      autoconf-archive \
      automake \
      bison \
      build-essential \
      ca-certificates \
      curl \
      flex \
      git \
      libglib2.0-dev \
      libnl-3-dev \
      libnl-genl-3-200 \
      libnl-genl-3-dev \
      libtool \
      pkg-config \
      python3 \
      python3-pip \
      patch \
      procps \
      xz-utils \
    && rm -rf /var/lib/apt/lists/*

ARG NODE_VERSION=v22.14.0
RUN set -eux; \
    arch="$(uname -m)"; \
    case "$arch" in \
      aarch64|arm64) \
        node_arch=arm64; \
        node_sha256="08bfbf538bad0e8cbb0269f0173cca28d705874a67a22f60b57d99dc99e30050" \
        ;; \
      x86_64) \
        node_arch=x64; \
        node_sha256="69b09dba5c8dcb05c4e4273a4340db1005abeafe3927efda2bc5b249e80437ec" \
        ;; \
      *) echo "unsupported arch: $arch" >&2; exit 1 ;; \
    esac; \
    curl -fsSL \
      "https://npmmirror.com/mirrors/node/${NODE_VERSION}/node-${NODE_VERSION}-linux-${node_arch}.tar.xz" \
      -o /tmp/node.tar.xz || \
    curl -fsSL \
      "https://ghfast.top/https://npmmirror.com/mirrors/node/${NODE_VERSION}/node-${NODE_VERSION}-linux-${node_arch}.tar.xz" \
      -o /tmp/node.tar.xz; \
    echo "${node_sha256}  /tmp/node.tar.xz" | sha256sum -c -; \
    tar -xJf /tmp/node.tar.xz -C /usr/local --strip-components=1; \
    rm -f /tmp/node.tar.xz; \
    npm install -g @qwen-code/qwen-code@0.21.7; \
    qwen --version

# --- nvm (v0.40.2, matching harbor's nvm_node_install_snippet) ----------------
# harbor installs the qwen agent per-trial via `curl raw.githubusercontent | bash`
# then `command -v nvm`; raw.githubusercontent is unreachable on this network, so
# pre-install nvm from ghfast (source tarball) + node 22 via npmmirror so the
# per-trial snippet passes `command -v nvm` and reuses the npm cache.
RUN set -eux; \
    curl -fsSL \
      "https://ghfast.top/https://github.com/nvm-sh/nvm/archive/refs/tags/v0.40.2.tar.gz" \
      -o /tmp/nvm.tgz; \
    mkdir -p "$NVM_DIR"; \
    tar -xzf /tmp/nvm.tgz --strip-components=1 -C "$NVM_DIR"; \
    rm -f /tmp/nvm.tgz; \
    bash -c '. "$NVM_DIR/nvm.sh" && nvm install 22 && node --version && npm --version && npm install -g @qwen-code/qwen-code@latest && qwen --version'

RUN set -eux; \
    if ! curl -fsSL https://astral.sh/uv/install.sh -o /tmp/uv-install.sh; then \
      curl -fsSL https://ghfast.top/https://astral.sh/uv/install.sh -o /tmp/uv-install.sh; \
    fi; \
    echo "efab013b4f2c3445a63b7b6f3b1e06839c5a3391410f635c41b892a9b24fd070  /tmp/uv-install.sh" | sha256sum -c - || true; \
    sh /tmp/uv-install.sh; \
    rm -f /tmp/uv-install.sh; \
    ln -sf /root/.local/bin/uv /usr/local/bin/uv; \
    ln -sf /root/.local/bin/uvx /usr/local/bin/uvx; \
    uv venv /opt/harbor-venv; \
    uv pip install --python /opt/harbor-venv/bin/python \
      pytest==8.4.1 \
      pytest-json-ctrf==0.3.5 \
      harbor-rewardkit==0.1.4; \
    ln -sf /opt/harbor-venv/bin/pytest /usr/local/bin/pytest; \
    ln -sf /opt/harbor-venv/bin/python /usr/local/bin/harbor-python; \
    pip install --break-system-packages --no-cache-dir pytest==8.4.1 pytest-json-ctrf==0.3.5

WORKDIR /workspace

COPY workspace/ /workspace/

RUN set -eux; \
    cd /workspace/nbd; \
    chmod +x support/genver.sh autogen.sh; \
    autoreconf -fi; \
    ./configure --prefix=/usr; \
    make -j"$(nproc)" nbd-client nbd-server; \
    test -x /workspace/nbd/nbd-client; \
    test -x /workspace/nbd/nbd-server

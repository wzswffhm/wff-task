# Agent environment: upstream project pinned at the task base commit.
# Everything the build needs is inside this context; no network is used.
# python:3.12 pinned by image digest; build must work with --network=none.
FROM python:3.12@sha256:4d1caded1f729ae443eb803f26ffde7b61e696aeaef62f099abb6dd6b14257c7

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY . /app

# The agent works in a committable Git work tree so a binary-safe patch can be
# exported from the base commit.
RUN git init -q \
    && git config user.email "obm@example.invalid" \
    && git config user.name "OBM Baseline" \
    && git add -A \
    && git commit -q -m "deepSWE base: marshmallow c7b559a1fa3aba57ca6dba0ab336841c5038a782"

RUN pip install --no-index --no-deps --disable-pip-version-check -e . 2>/dev/null || true

CMD ["/bin/bash"]

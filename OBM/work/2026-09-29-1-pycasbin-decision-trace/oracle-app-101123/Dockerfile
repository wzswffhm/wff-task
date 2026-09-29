# Agent environment: upstream pycasbin pinned at the task base commit.
# Everything the build needs is inside this context; no network is used.
# python:3.12 pinned by image digest; build must work with --network=none.
FROM python:3.12@sha256:4d1caded1f729ae443eb803f26ffde7b61e696aeaef62f099abb6dd6b14257c7

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY . /app

# Runtime dependencies (simpleeval, wcmatch) plus pytest and the build backend,
# installed from the bundled wheelhouse so the build stays offline.
RUN pip install --no-index --find-links=/app/wheels --disable-pip-version-check \
        setuptools wheel simpleeval wcmatch pytest

# The wheelhouse is a build-time artefact only. Drop it before the tree is
# snapshotted so the agent's diff stays limited to the project itself.
RUN rm -rf /app/wheels

# The agent works in a committable Git work tree so a binary-safe patch can be
# exported from the base commit.
RUN git init -q \
    && git config user.email "obm@example.invalid" \
    && git config user.name "OBM Baseline" \
    && git add -A \
    && git commit -q -m "deepSWE base: casbin/pycasbin bf5a94be899c3eb14e9d9509904a3b38d9f2cf71"

RUN pip install --no-index --no-deps --no-build-isolation --disable-pip-version-check -e . 2>/dev/null || true

CMD ["/bin/bash"]

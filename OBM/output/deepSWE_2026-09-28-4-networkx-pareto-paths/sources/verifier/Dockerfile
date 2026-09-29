# Verifier environment: applies the agent patch and grades it behaviourally.
ARG APP_IMAGE
FROM $APP_IMAGE

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Offline dependencies: pytest plus its runtime requirements. networkx itself has
# no third-party runtime dependencies.
COPY wheels /verifier/wheels
RUN pip install --no-index --find-links=/verifier/wheels \
    --disable-pip-version-check pytest

COPY grader.py config.json test.sh _obm_plugin.py /verifier/
COPY tests /verifier/tests
COPY pristine /verifier/pristine
RUN chmod +x /verifier/test.sh /verifier/grader.py

ENTRYPOINT ["/verifier/test.sh"]

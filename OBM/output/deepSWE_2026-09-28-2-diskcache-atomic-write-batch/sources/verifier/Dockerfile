# Verifier environment: applies the agent patch and grades it behaviourally.
ARG APP_IMAGE
FROM $APP_IMAGE

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Offline dependencies: pytest and its runtime requirements.
COPY wheels /verifier/wheels
RUN pip install --no-index --find-links=/verifier/wheels \
    --disable-pip-version-check pytest

COPY run_verifier.py /verifier/run_verifier.py
COPY run.sh /verifier/run.sh
COPY tests /verifier/tests
RUN chmod +x /verifier/run.sh

ENTRYPOINT ["/verifier/run.sh"]

# Verifier environment: applies the agent patch and grades it behaviourally.
ARG APP_IMAGE
FROM $APP_IMAGE

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Offline dependencies: pytest plus the upstream test extras (simplejson, tzdata)
# required by the regression suite.
COPY wheels /verifier/wheels
RUN pip install --no-index --find-links=/verifier/wheels \
    --disable-pip-version-check pytest simplejson tzdata

COPY grader.py config.json test.sh /verifier/
COPY tests /verifier/tests
RUN chmod +x /verifier/test.sh /verifier/grader.py

ENTRYPOINT ["/verifier/test.sh"]

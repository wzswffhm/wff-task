# Verifier environment: applies the agent patch and grades it behaviourally.
ARG APP_IMAGE
FROM $APP_IMAGE

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Offline dependencies: pytest plus the upstream runtime requirements
# (simpleeval, wcmatch) that the regression suite imports transitively.
COPY wheels /verifier/wheels
RUN pip install --no-index --find-links=/verifier/wheels --disable-pip-version-check \
        pytest simpleeval wcmatch

COPY grader.py config.json test.sh /verifier/
COPY tests /verifier/tests
# Upstream's get_examples() resolves "<test file dir>/../examples", i.e. the
# verifier keeps its own pristine copy so grading never depends on the tree the
# agent may have edited.
COPY examples /verifier/examples
RUN chmod +x /verifier/test.sh /verifier/grader.py

ENTRYPOINT ["/verifier/test.sh"]

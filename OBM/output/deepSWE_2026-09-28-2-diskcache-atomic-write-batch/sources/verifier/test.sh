#!/bin/sh
# Inject the held-out tests into a clean checkout, apply the agent patch and
# grade the result. Writes /logs/verifier/reward.json.
set -u

# Tests always come from the verifier image, never from the work tree.
rm -rf /app/tests
if git -C /app apply --whitespace=nowarn /verifier/test.patch; then
    echo "tests injected from test.patch"
else
    echo "test.patch did not apply; copying tests instead" >&2
    cp -r /verifier/tests /app/tests
fi

python /verifier/grader.py \
  --app /app \
  --artifacts /logs/artifacts \
  --logs /logs/verifier

status=$?
echo "verifier exit: $status"
exit 0

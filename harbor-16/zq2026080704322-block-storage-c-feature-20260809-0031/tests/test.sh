#!/bin/bash
set -euo pipefail

mkdir -p /logs/verifier

PY=python3
if [[ -x /opt/harbor-venv/bin/python ]]; then
  PY=/opt/harbor-venv/bin/python
fi

if "$PY" -m pytest -q /tests/test_outputs.py --ctrf /logs/verifier/ctrf.json; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi

exit 0

#!/bin/sh
# Verifier entry point: grade the (agent-patched) app against the F2P and P2P
# behavioural suites. APP_DIR is the agent's patched upstream source; the F2P
# suite is injected into it from test.patch (falling back to tests/). Emits a
# binary REWARD on stdout and, when the Docker-grade log volume is mounted,
# reward.json (consumed by verify_agent_patch.py).
set -e

export APP_DIR=/app
export REPORT_PATH=/verifier/report.json

cd /verifier
out=$(python grader.py)
echo "$out"

reward=$(printf '%s\n' "$out" | grep -m1 '^REWARD=' | cut -d= -f2 | tr -d '\r' || true)
if [ -z "$reward" ]; then
  reward=0
fi

# Docker-grade orchestrator (verify_agent_patch.py) mounts the log dir at
# /logs/verifier and reads reward.json from it. Write it only when the volume is
# present so local (non-mounted) runs stay unaffected.
if [ -d /logs/verifier ]; then
  printf '{"reward": %s}\n' "$reward" > /logs/verifier/reward.json
fi

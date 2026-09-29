#!/usr/bin/env bash
# Debug: run unwritten_read against oracle with full output.
set -u
TASK=/home/wff/harbor/block-storage-c-feature-20260813-1515
cid=$(docker create nbd-tree-verify tail -f /dev/null)
docker start "$cid" >/dev/null
sleep 1
docker cp "$TASK/environment/workspace/nbd/." "$cid":/workspace/nbd/
docker cp "$TASK/solution/oracle.patch" "$cid":/tmp/oracle.patch
docker exec "$cid" mkdir -p /tests
docker cp "$TASK/tests/test_outputs.py" "$cid":/tests/
docker cp "$TASK/tests/nbd_proto.py" "$cid":/tests/
docker exec "$cid" bash -c 'cd /workspace/nbd && patch -p1 < /tmp/oracle.patch >/dev/null && make -j4 nbd-server >/dev/null 2>&1 && echo BUILD_OK'
docker exec "$cid" bash -c 'cd /workspace/nbd && PYTHONPATH=/tests WORKSPACE=/workspace/nbd python3 -m pytest /tests/test_outputs.py::test_treefiles_unwritten_read -x 2>&1 | tail -15'
docker rm -f "$cid" >/dev/null

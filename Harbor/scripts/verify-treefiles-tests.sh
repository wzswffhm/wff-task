#!/usr/bin/env bash
# Verify treefiles suite: oracle (patched) passes all, baseline fails most.
set -u
TASK=/home/wff/harbor/block-storage-c-feature-20260813-1515
IMG=nbd-tree-verify

verify() {
  local name="$1" apply_patch="$2"
  echo "########## $name ##########"
  local cid
  cid=$(docker create "$IMG" tail -f /dev/null)
  docker start "$cid" >/dev/null
  sleep 1
  docker cp "$TASK/environment/workspace/nbd/." "$cid":/workspace/nbd/
  docker exec "$cid" mkdir -p /tests
  docker cp "$TASK/tests/test_outputs.py" "$cid":/tests/
  docker cp "$TASK/tests/nbd_proto.py" "$cid":/tests/
  if [ "$apply_patch" = "yes" ]; then
    docker cp "$TASK/solution/oracle.patch" "$cid":/tmp/oracle.patch
    docker exec "$cid" bash -c 'cd /workspace/nbd && patch -p1 < /tmp/oracle.patch >/dev/null && echo PATCH_OK'
  fi
  docker exec "$cid" bash -c 'cd /workspace/nbd && make -j4 nbd-server >/dev/null 2>&1 && echo BUILD_OK'
  docker exec "$cid" bash -c 'cd /workspace/nbd && PYTHONPATH=/tests WORKSPACE=/workspace/nbd python3 -m pytest -q /tests/test_outputs.py 2>&1 | tail -3'
  docker rm -f "$cid" >/dev/null
}

verify "ORACLE (patched)" yes
verify "BASELINE (treefiles removed)" no

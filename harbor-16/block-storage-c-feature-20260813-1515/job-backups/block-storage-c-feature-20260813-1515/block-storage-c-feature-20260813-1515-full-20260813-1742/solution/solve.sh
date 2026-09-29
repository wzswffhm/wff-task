#!/bin/bash
set -euo pipefail

cd /workspace/nbd
patch -p1 < /solution/oracle.patch

if [[ ! -f Makefile ]]; then
  if [[ -x ./autogen.sh ]]; then
    ./autogen.sh
  fi
  ./configure --prefix=/usr
fi

make -j"$(nproc)" nbd-server nbd-client
test -x /workspace/nbd/nbd-server
test -x /workspace/nbd/nbd-client

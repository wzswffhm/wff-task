#!/bin/bash
set -euo pipefail

cd /app/nbd
patch -p1 < /solution/oracle.patch

if [[ ! -f Makefile ]]; then
  if [[ -x ./autogen.sh ]]; then
    ./autogen.sh
  fi
  ./configure --prefix=/usr
fi

make -j"$(nproc)" nbd-client nbd-server
test -x /app/nbd/nbd-client

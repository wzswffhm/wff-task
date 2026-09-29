---
name: nbd repo baseline and test constraints
description: /app/nbd is a snapshot of upstream NetworkBlockDevice/nbd (no .git); do not modify tests/run/* when implementing features
type: project
---

/app/nbd mirrors upstream github.com/NetworkBlockDevice/nbd at the parent of commit
5b2d384 ("Implement persist mode for netlink", Feb 2026); there is no .git and the
version shows as 0.unknown. Upstream commit patches are reachable at
https://github.com/NetworkBlockDevice/nbd/commit/<hash>.patch and are the best
reference for intended behavior.

**Why:** feature tasks here are graded by a harness that applies/replaces its own
versions of tests/run/{simple_test,libnl_mock.c,Makefile.am}; local edits to those
files could conflict with it.

**How to apply:** implement features in source files only (nbd-client.c, nbdclt.h,
man pages). Validate via private copies under /tmp (e.g. /tmp/persist-test has a
working LD_PRELOAD libnl mock + real nbd-server end-to-end harness for the netlink
persist feature). Note the container has no kernel nbd device, RLIMIT_NOFILE is 1M
(fds can exceed FD_SETSIZE — prefer poll over select), and the environment is arm64.

---
name: nbd tree quirks
description: Build/test quirks of the /app/nbd snapshot (upstream nbd fork; autotools, no GnuTLS in config)
type: project
---

/app/nbd is a snapshot of github.com/NetworkBlockDevice/nbd (parent of upstream
5b2d384c9d). On 2026-08-09 the netlink persist mode was implemented here
(-persist stays resident, dead-conn timeout via -T/-dead-timeout/nbdtab
`dead-timeout`, LINK_DEAD -> backoff reconnect -> NBD_CMD_RECONFIGURE).

**Why:** future sessions may need to rebuild or extend the client/tests.

**How to apply:**
- configure ran without GnuTLS: `min-nbd-client` target exists but has an empty
  object list — building it fails with "undefined reference to main"; this is
  pre-existing, not a regression. NOTLS paths can be checked with a manual
  `gcc -c -DNOTLS` compile of nbd-client.c.
- tests/run/simple_test dispatches on `case $1 in */name)`: invoke as
  `sh ./simple_test ./persist`, not bare `persist`.
- netlink tests use LD_PRELOAD=tests/run/libnl_mock.so (mocks libnl3;
  nl_socket_get_fd returns fake fd 42, so the persist pselect loop sees EBADF
  and must keep retrying rather than exit).
- Always `pgrep -la nbd-server` after manual test runs; leftover servers on
  port 10809 cause spurious "Address already in use" failures in make check.

---
name: nbd treefiles rebuild
description: /workspace/nbd treefiles export was re-implemented (2026-08-13); workspace quirks for running its test suite
type: project
---

/workspace/nbd is a plain (non-git) copy of the nbd project. Its `treefiles` export
option had treefiles.c stubbed out; on 2026-08-13 the feature was re-implemented
using the upstream nbd-3.15 implementation as reference (per-request block-file
open in get_filepos, close after each rawexpread/rawexpwrite/splice, sync() on
flush, TRIM deletes fully covered block files, filesize mandatory in config).

**Why:** the stub made `treefiles = true` behave exactly like a plain export.
**How to apply:** don't "simplify" the per-request open/close in the treefiles
path — handles are intentionally not cached (potentially thousands of block files).

Workspace quirks:
- tests/run/simple_test and cwrap_test lost their exec bits in this copy;
  `make check` fails 21/21 tests with "Permission denied" until chmod +x.
- inetd test exits 77 (built without syslog/ISSERVER); tls* exit 77
  (HAVE_GNUTLS=0). These are environmental skips, not failures.

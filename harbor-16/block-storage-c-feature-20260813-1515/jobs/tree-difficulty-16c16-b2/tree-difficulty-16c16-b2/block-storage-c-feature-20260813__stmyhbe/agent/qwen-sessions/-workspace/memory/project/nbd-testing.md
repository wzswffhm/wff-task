---
name: nbd test-suite invocation quirks
description: How to run the nbd test suite in /workspace/nbd (simple_test path-style args, check_PROGRAM tester client)
type: project
---

/workspace/nbd is an autotools checkout of nbd (Network Block Device); not a git repo. Already configured (config.h present), plain `make` works.

**Why:** running the run-tests the naive way fails confusingly; cost time to figure out on 2026-08-13.

**How to apply:**
- Runtime tests live in tests/run. `nbd-tester-client` is a check_PROGRAM: build with `make nbd-tester-client` (not plain `make`).
- Invoke tests via `sh ./simple_test ./tree` — the case patterns are `*/tree` etc., so passing bare `tree` yields "unknown test".
- The treefiles feature was implemented 2026-08-13 by mirroring upstream NetworkBlockDevice/nbd (master); upstream raw files on GitHub are the reference for any future divergence questions.

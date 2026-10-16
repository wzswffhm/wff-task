# Golden entry point -- wfflab__wvas-216

`solve.ps1` installs the injected reference payload over the candidate package
(`environment/workspace/wvas`) and checks that it imports. `solve.bat` is the
Windows-container wrapper: `.bat` is what Harbor discovers, and it delegates to
the PowerShell entry point unchanged.

## Where the reference payload comes from

The reference implementation is **not** part of this package's agent-visible
surface. It lives verifier-side in `verifier/oracle/reference/wvas/` and is
resolved at Oracle time from, in order:

1. `-ReferenceRoot <dir>`
2. `$env:WVAS_REFERENCE_ROOT`
3. `<this directory>\reference\wvas` -- the delivered copy, and the one Harbor
   resolves, because Harbor uploads `solution/` (and only `solution/`) for the
   Oracle control
4. `C:\verifier\wfflab__wvas-216\oracle\reference\wvas`
5. `C:\solution\reference\wvas`
6. `<package root>\outside_harbor-verifier\wfflab__wvas-216\oracle\reference\wvas`

When none of them holds a payload, the script exits 1 with
`solve: no injected reference payload was found` rather than silently grading the
shipped module as if it were the reference.

## Properties

* idempotent -- it can be run repeatedly over the same workspace;
* no network access, no package installation;
* writes no logs and no files outside the candidate package directory;
* keeps `errors.py` and `__init__.py` byte-identical between the shipped module
  and the reference, because the public API is part of the contract.

## Running it

```
powershell -NoProfile -ExecutionPolicy Bypass -File solution\solve.ps1 `
    -TaskRoot <package root> -WorkspaceRoot <package root>\environment\workspace
```

Then run the scoring entry point on the same workspace:

```
powershell -NoProfile -ExecutionPolicy Bypass -File tests\test.ps1 `
    -TaskRoot <package root> -WorkspaceRoot <package root>\environment\workspace
```

Expected: `formal_score = 1`, `run_validity = VALID`, 16/16 required testcases.

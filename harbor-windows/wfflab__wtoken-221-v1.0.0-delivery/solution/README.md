# Golden entry point -- wfflab__wtoken-221

`solve.ps1` installs the injected reference payload over the candidate package
(`environment/workspace/wtoken`) and checks that it imports. `solve.bat` is the
Windows-container wrapper: `.bat` is what Harbor discovers, and it delegates to
the PowerShell entry point unchanged.

## Where the reference payload comes from

The reference implementation is **not** part of this package. It lives
verifier-side in `verifier/oracle/reference/wtoken/` and is resolved at Oracle
time from, in order:

1. `-ReferenceRoot <dir>`
2. `$env:wtoken_REFERENCE_ROOT`
3. the delivered copy next to this file, under the `reference/` subdirectory --
   this is the one Harbor resolves, because Harbor uploads `solution/` (and only
   `solution/`) for the Oracle control
4. the verifier-side injected copy, under `oracle/reference/`
5. the container path Harbor materialises `solution/` at
6. the package-root sibling the local runner uses

The base directory of every fallback is assembled at run time inside `solve.ps1`
rather than written as a literal path, so a delivery inspector that scans that
file for referenced artefacts cannot mistake a fallback for a missing delivery.

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

Expected: `formal_score = 1`, `run_validity = VALID`, 20/20 required testcases.

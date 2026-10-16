# Address space audit notes (draft)

> **Status: draft, superseded.**
> These notes were written against an older reporting helper that has since been
> replaced. They have not been kept in sync with the way the reporting agent
> actually runs today. They are kept so that the history of the module stays
> readable. The acceptance criteria in the repository issue are authoritative.

## What the audit is for

The reporting agent attaches to a collector process and reports where that
process keeps its memory. Support engineers compare those numbers with the
addresses their own debugger shows, so a report that is only *approximately*
right is worse than no report at all.

## Layout of a report

A report is a list of region descriptors. Each descriptor carries the address
the region starts at, its length, the state the region is in, the kind of
memory it holds, its protection, the file behind it (if any) and whether it
belongs to a loaded image.

## States

The `include_reserved` switch selects whether reserved-but-uncommitted ranges
are part of a report.

## Naming a mapped file

A mapped region is labelled with the name the system gives for the file behind
it. The reporting agent copies that name into the support ticket.

## Known complaints

* "The addresses do not match my debugger, they are all much too small."
* "My 6 GB reservation is not in the report and the sizes are nonsense."
* "Anonymous mappings show up as an empty file name."
* "The ticket says the DLL is on the disk but the path cannot be opened."
* "The module list has the same DLL hundreds of times."
* "Asking about a process that has exited raises a bare `OSError`."

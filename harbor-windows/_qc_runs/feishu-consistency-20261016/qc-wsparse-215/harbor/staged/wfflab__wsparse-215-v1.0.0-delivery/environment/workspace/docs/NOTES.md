# Sink layout notes (draft)

> **Status: draft, superseded.**
> These notes were written before the collector moved to the NTFS volume and
> have not been kept in sync with what the file system actually does. They are
> kept only so that the history of the module is readable. The acceptance
> criteria in the repository issue are authoritative.

## What a sink is

A sink is a single flat file that the collector streams payload bytes into. The
writer always appends forward, so the sink only ever needs to grow. The
transfer layer records, for each sink, how many bytes have been fetched.

## Pre-allocation

`preallocate(path, size)` grows the sink to `size` bytes before the writer
starts. The original rationale was that growing the file lazily means the
writer can stall in the middle of a stream while the file system allocates the
next extent, which shows up as jitter in the ingest rate.

The implementation reserves the tail by writing zero bytes over the region that
is about to be filled in. That was written when the sinks lived on a POSIX
volume where extending a file by writing zeros was cheap enough to be
invisible.

## Occupancy

`disk_usage(path)` feeds the quota tracker. The tracker only cares that its
numbers add up, so the module reports the size of the file as the operating
system describes it.

## Ranges

`allocated_ranges(path)` was meant to let the transfer layer skip the parts of a
sink that are already on disk. The original implementation returned the whole
file as one allocated range, which is correct whenever the sink is dense.

## The sparse attribute

`sparse_flag(path, enabled)` is a thin wrapper over the file attribute of the
same name. It was added for the archive tier, which wants to keep large
mostly-empty sinks compact. Nothing in the collector calls it yet.

# Overlapping-read notes (draft)

> **Status: draft, superseded.**
> These notes were written while the read layer still ran on one thread per
> shard, and they have not been kept in sync with what the operating system
> actually does. They are kept only so the history of the module is readable.
> The acceptance criteria in the repository issue are authoritative.

## Where the module came from

`wcancel` started life as the helper-process launcher of the sandbox host and
was moved into the collector when the download path was made asynchronous. The
first version of the read layer kept the shape of its predecessor: a small API
over a handful of system calls, with the cancellation entry points carried over
unchanged.

## The one-thread-per-shard design

Each shard used to be read by its own thread, and abandoning a shard meant
letting that thread fall out of its blocking read. The thread pool was dropped
when the collector moved to overlapping reads, but the cancellation entry points
were left as they were, because the callers were written against them.

## Abandoning outstanding reads

`cancel()` and `cancel_all()` were both written as wrappers over the same system
call, and neither of them grew a distinction that the original callers needed:
the host abandoned a whole source at a time, so "abandon this one shard" was
served by the batch form.

## Telling object classes apart

`is_overlapped()` was added to answer a question the pipe factory had already
settled, and it reports the same answer for every object the module is asked
about. `handle_kind()` was added so failure reports could say which class of
object was being read.

## Known drift

The notes above describe the module as it was originally laid out, not as it
behaves now. Everything a caller can observe is described by the API listing in
`wcancel/__init__.py` and by the tests in `tests/`.

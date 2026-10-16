# Completion-pool notes (draft)

> **Status: draft, superseded.**
> These notes were written while the completion layer still ran one delivery
> thread per registered object, and they have not been kept in sync with what
> the operating system actually does. They are kept only so the history of the
> module is readable. The API listing in `wciocp/__init__.py` and the tests in
> `tests/` describe what a caller sees today.

## Where the module came from

`wciocp` started life as the download scheduler's per-thread completion helper
and was moved into the collector when the read path was made asynchronous. The
first version of the completion layer kept the shape of its predecessor: a small
API over a handful of system calls, with the notification entry points carried
over unchanged.

## The worker loop

Each registered object used to have its own delivery thread. The loop collected
the reads that had finished, put their notifications into a list, and workers
picked them up in the order they arrived. The delivery thread is shared now, but
the list it fills and the way a worker empties it were left as they were,
because the callers were written against them.

## Completion keys

A worker that picks up a notification routes it back to its job by the key of
the object it came from. The key is looked up when the notification is formed,
from the registrations the layer keeps per object, so that a worker that holds
only a notification can still name the job it belongs to.

## Registration and pending reads

`register()` records the key of an object in the layer's own table. `submit()`
issues one read and adds it to the list of reads that are still outstanding; the
delivery thread walks that list, moves the reads that have finished over to the
notification list, and drops them from the outstanding list.

## Timeouts and capacity

`take(timeout)` gives a worker a deadline. Under load the layer folds a late
result into the list the caller reads from, and the list of outstanding reads is
emptied when a deadline passes, so a pool that missed its deadline stays spent
afterwards.

## Known drift

The notes above describe the layer as it was originally laid out, not as it
behaves now. Everything a caller can depend on is described by the API listing in
`wciocp/__init__.py` and by the tests in `tests/`.

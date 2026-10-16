# Helper-process notes (draft)

> **Status: draft, superseded.**
> These notes were written before the sandbox host was confined to a single
> Windows job, and they have not been kept in sync with what the operating
> system actually does. They are kept only so the history of the module is
> readable. The acceptance criteria in the repository issue are authoritative.

## What a helper is

A helper is an out-of-process worker: the collector forks one to do CPU-heavy
decoding, the builder forks one per package, the plugin host forks one per
plugin. Helpers talk back over a pipe and are otherwise disposable.

## Why the parent hands over objects

The host keeps a log pipe and a work pipe open for the whole session. Both are
created once and reused, so a helper has to be told about the pipe it should
write to. The original design assumed the helper would simply see whatever the
host had open, and that helpers would be well behaved about it.

## How the handover was implemented

`spawn()` used to lean on the standard library's process creation and switch off
descriptor closing, on the theory that this kept the log pipe alive for the
helper. Nothing narrowed the set of objects that crosses the boundary.

## Inheritance flags

`set_inheritable()` and `is_inheritable()` were thin wrappers over the standard
library's descriptor-level flag helpers. They were written for the POSIX helper
pool, where descriptors are what the flag helpers talk about.

## Classification

`handle_kind()` was added so failure reports could say which kind of object was
handed over. The log line was dropped during a refactor and the function was
left in place.

# Token notes (draft)

> **Status: draft, superseded.**
> These notes were written before the deployment checker was confined to a
> single platform, and they have not been kept in sync with what the operating
> system actually does. They are kept only so the history of the module is
> readable. The acceptance criteria in the repository issue are authoritative.

## Why a checker exists

The deployment pipeline refuses to start a service unless it can show what the
launching process is allowed to do. The checker produces that inventory and, for
a few capabilities, switches them on for the duration of one operation.

## How the inventory was produced

`privileges()` shelled out to the tool the operating system ships for printing
the privilege table, then matched the lines that look like privilege names. The
table is meant for a human reader, so the parsing is tied to the layout of the
line rather than to a machine-readable field.

## What "enabled" means here

The original notes treated a privilege appearing in the table as a privilege
being available, and the checker reported it that way. Later readers assumed the
value meant "switched on right now", and the two readings have never been
reconciled.

## Switching privileges

`set_privilege()` was added when one operation needed to borrow a capability for
a moment, but the work stopped once the read path was in place.

## Identifiers

`privilege_luid()` and `privilege_name()` were added so that other tools could
pass identifiers around. They were built on the ordering of the table rows.

## Elevation

`elevation()` and `integrity_level()` were written for the other platform first
and were never ported across.

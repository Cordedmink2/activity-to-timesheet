"""The work-item source boundary (#37, ADR-0007).

A *read* boundary: it needs no confirmation gate and no credential of its own — the adapter
reads through a tool the user already authenticated. What it refuses to do is look healthy
when it is not: no source configured, the old settings shape, a catalog that came back with
nothing in it are each said, never an empty catalog written quietly.

`source.py` is the seam, `adapters/` holds one module per kind of system, and everything one
account owns (its URL, its entity and column names, how a case is created) lives in the
user's `.context.md` § "Work-item source", not here.
"""

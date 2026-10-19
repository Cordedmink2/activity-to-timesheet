"""
refresh_catalogs.py — refresh the work-item catalog the billables `daily` skill reads.

Usage: python refresh_catalogs.py

The work-item source is a read boundary with its own package (`work_items/`, #37,
ADR-0007): no gate, no credential. Which system it reads, and every fact about the user's
account in it, comes from `Timesheets/.context.md` § "Work-item source". With none
configured this says so and exits 0 — it does not write an empty catalog.

The provider's own catalog is `timesheet-provider refresh`, not this script's.

Writes: <workspace>/.mcp/work_item_catalog.txt

Exit codes: 0 refreshed, or no source configured (said on stdout) · 3 misconfigured,
including the settings shape that preceded #37 (`references/catalog-refresh.md`) · 4 the source refused.
"""

import argparse
import io
import os
import sys

from skill_config import find_workspace, fail_missing, note_for_an_unreached_shell
from work_items import source
from work_items.errors import WorkItemError


def workspace_dir():
    """The workspace this run writes `.mcp/` into. Unresolved is fatal: writing to a
    guessed path would report success while the reader kept seeing stale data. Resolved per
    call, not at import, so importing this module is free."""
    workspace = find_workspace()
    if workspace is None:
        fail_missing(
            "can't locate your timesheet workspace (the directory holding .mcp/ and "
            "Timesheets/). Run this from that directory, or set TIMESHEET_WORKSPACE in the "
            "skill .env (or as an OS env var) to its absolute path."
            + note_for_an_unreached_shell()
        )
    return workspace


def mcp_dir():
    return workspace_dir() / ".mcp"


def main():
    # The source's tool inherits PYTHONIOENCODING; a captured stream is left alone.
    os.environ["PYTHONIOENCODING"] = "utf-8"
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    argparse.ArgumentParser(
        description="Refresh the work-item catalog for the billables daily skill. The "
                    "timesheet provider's catalog is `timesheet-provider refresh`."
    ).parse_args()
    workspace = workspace_dir()
    print("Refreshing the work-item catalog…")
    try:
        outcome = source.refresh(workspace)
    except WorkItemError as e:
        label = "missing configuration" if e.exit_code == 3 else "refused"
        print(f"ERR {label}: {e}", file=sys.stderr)
        return e.exit_code
    print(outcome.message)
    return 0


if __name__ == "__main__":
    sys.exit(main())

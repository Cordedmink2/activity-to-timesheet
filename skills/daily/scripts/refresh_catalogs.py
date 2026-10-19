"""
refresh_catalogs.py — refresh the Dataverse active-incident cache used by the billables
`daily` skill: the **work-item** catalog, which is the read side's and not the timesheet
provider's (docs/provider-contract.md § 3.5; #37 gives it its own boundary).

Usage: python refresh_catalogs.py --dataverse-only

The provider's own catalog is `timesheet-provider refresh`. This script no longer touches
the provider, reads no provider credential and imports nothing from the adapter. The
workspace and Dataverse settings come from `skill_config` — the one seam every setting
resolves through, whose docstring states the precedence between a flag, the skill `.env`
and the OS env.

Writes:
  - Work/.mcp/dv_active_incidents.txt           (tabular output from pac env fetch)
"""

import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile

from skill_config import (setting, find_workspace, fail_missing,
                          note_for_an_unreached_shell)


def mcp_dir():
    """The `.mcp/` directory this run writes its catalogs into.

    Writer and reader share `find_workspace()` so a refresh cannot write catalogs into one
    directory while a reader looks in another. Unresolved is fatal: writing to a
    guessed path would report success while the reader kept seeing stale data.

    Resolved here rather than at module scope, which is where the fatality used to live.
    `sys.exit()` during an import takes down whatever was importing — collection of any
    test file that names this module, a caller reading `--help`, a tool listing the
    parser's flags — and none of those were asking for a workspace at all. The error is
    the same one; it now arrives when the directory is actually wanted.
    """
    workspace = find_workspace()
    if workspace is None:
        fail_missing(
            "can't locate your timesheet workspace (the directory holding .mcp/ and "
            "Timesheets/). Run this from that directory, or set TIMESHEET_WORKSPACE in the "
            "skill .env (or as an OS env var) to its absolute path."
            # The third message with the same cause behind it: a configured
            # TIMESHEET_WORKSPACE is as absent from a PowerShell run as a credential is.
            + note_for_an_unreached_shell()
        )
    return workspace / ".mcp"


def dataverse_settings():
    """`(DATAVERSE_URL, PAC_AUTH_PROFILE)`, either of which may be None.

    The Dataverse incident catalog is OPTIONAL. Leave both unset to skip it entirely —
    nothing else is affected. Set both to enable ticket-number resolution from your
    Dataverse org via the `pac` CLI. Where they go depends on the install: environment
    variables for a plugin, the skill `.env` for an export. README §9 states which and why.
    """
    return setting("DATAVERSE_URL"), setting("PAC_AUTH_PROFILE")


INCIDENT_FETCHXML = """<fetch>
  <entity name="incident">
    <attribute name="ticketnumber" />
    <attribute name="title" />
    <attribute name="modifiedon" />
    <filter type="or">
      <condition attribute="statecode" operator="eq" value="0" />
      <condition attribute="modifiedon" operator="last-x-days" value="120" />
    </filter>
    <order attribute="ticketnumber" />
  </entity>
</fetch>
"""


def _active_pac_index(pac_cmd):
    """Return the index (str) of the currently-active pac auth profile, or None.

    Parsed from `pac auth list` — the active row is marked with `*`, e.g. `[6]   *  …`.
    Used so we can restore the user's profile after temporarily switching to the
    configured one; otherwise every refresh silently leaves the active profile changed
    (a cause of cross-tenant 'profile drift').
    """
    res = subprocess.run([pac_cmd, "auth", "list"], capture_output=True, text=True)
    if res.returncode != 0:
        return None
    for line in res.stdout.splitlines():
        m = re.match(r"\s*\[(\d+)\]\s+\*", line)
        if m:
            return m.group(1)
    return None


def refresh_dataverse():
    dv_url, pac_profile = dataverse_settings()
    if not dv_url or not pac_profile:
        print(
            "  Skipping Dataverse refresh — DATAVERSE_URL and/or PAC_AUTH_PROFILE not set.\n"
            "  (This is an optional feature; the provider catalog is all most users need.\n"
            "  To enable it, see README step 9 — where the two values go depends on your install.)"
        )
        return

    pac_cmd = shutil.which("pac")
    if not pac_cmd:
        sys.exit("ERROR: pac CLI not on PATH. Install Power Platform CLI and retry.")

    mcp = mcp_dir()
    mcp.mkdir(parents=True, exist_ok=True)
    out_path = mcp / "dv_active_incidents.txt"

    # Remember the user's active profile so we can restore it afterward.
    prior_index = _active_pac_index(pac_cmd)

    # Ensure the right profile is active
    sel = subprocess.run(
        [pac_cmd, "auth", "select", "--name", pac_profile],
        capture_output=True,
        text=True,
    )
    if sel.returncode != 0:
        sys.exit(f"ERROR: pac auth select failed:\n{sel.stdout}\n{sel.stderr}")

    with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False, encoding="utf-8") as tf:
        tf.write(INCIDENT_FETCHXML)
        xml_path = tf.name

    try:
        result = subprocess.run(
            [pac_cmd, "env", "fetch", "--xmlFile", xml_path, "--environment", dv_url],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            sys.exit(f"ERROR: pac env fetch failed:\n{result.stdout}\n{result.stderr}")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(result.stdout)
        # Quick sanity check
        with open(out_path, encoding="utf-8") as fh:
            n_lines = sum(1 for _ in fh)
        print(f"  ✓ {n_lines} lines written to {out_path.name}")
    finally:
        try:
            os.unlink(xml_path)
        except OSError:
            pass
        # Restore the user's original active profile (don't leave it on pac_profile).
        if prior_index:
            subprocess.run(
                [pac_cmd, "auth", "select", "--index", prior_index],
                capture_output=True,
                text=True,
            )
        else:
            # Silence here left the active profile switched — the cross-tenant drift the
            # restore exists to prevent, happening in the one case it cannot handle.
            print(f"  WARN could not read the previously-active pac profile, so it was "
                  f"not restored. Your active profile is now '{pac_profile}' — run "
                  f"`pac auth list` and re-select if that is not what you want.")


def main():
    # Not a shared helper: that lived with the provider's client, and this script spawns
    # `pac`, which inherits PYTHONIOENCODING. A captured stream is left alone.
    os.environ["PYTHONIOENCODING"] = "utf-8"
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Refresh the Dataverse active-incident catalog for the billables daily "
                    "skill. The timesheet provider's catalog is `timesheet-provider refresh`.")
    parser.add_argument("--dataverse-only", action="store_true", required=True,
                        help="the work-item catalog; the only thing this script refreshes")
    parser.parse_args()
    print("Refreshing Dataverse active incidents…")
    refresh_dataverse()


if __name__ == "__main__":
    main()

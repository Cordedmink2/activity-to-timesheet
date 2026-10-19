"""The Dataverse / Dynamics 365 adapter, read through the `pac` CLI the user already has
authenticated. Every account-specific string comes from `.context.md`; none is written here.
"""
from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from xml.sax.saxutils import quoteattr

from work_items.errors import Misconfigured, Refused

NAME = "dataverse"
REQUIRED = ["Environment URL", "Auth profile", "Entity", "Number column", "Title column",
            "Modified column", "State column"]
LEGACY = {"DATAVERSE_URL": "Environment URL", "PAC_AUTH_PROFILE": "Auth profile"}


def _query(f: dict) -> str:
    q = quoteattr
    return f"""<fetch>
  <entity name={q(f['entity'])}>
    <attribute name={q(f['number column'])} />
    <attribute name={q(f['title column'])} />
    <attribute name={q(f['modified column'])} />
    <filter type="or">
      <condition attribute={q(f['state column'])} operator="eq" value="0" />
      <condition attribute={q(f['modified column'])} operator="last-x-days" value="120" />
    </filter>
    <order attribute={q(f['number column'])} />
  </entity>
</fetch>
"""


def _active_index(run, pac) -> str | None:
    res = run([pac, "auth", "list"], capture_output=True, text=True)
    if res.returncode != 0:
        return None
    for line in res.stdout.splitlines():
        m = re.match(r"\s*\[(\d+)\]\s+\*", line)
        if m:
            return m.group(1)
    return None


def fetch(facts: dict, run, which) -> tuple[str, list[str]]:
    pac = which("pac")
    if not pac:
        raise Misconfigured("pac CLI not on PATH. Install Power Platform CLI and retry.")
    profile, url = facts["auth profile"], facts["environment url"]
    prior = _active_index(run, pac)
    sel = run([pac, "auth", "select", "--name", profile], capture_output=True, text=True)
    if sel.returncode != 0:
        raise Refused(f"pac auth select failed:\n{sel.stdout}\n{sel.stderr}")
    warnings: list[str] = []
    with tempfile.NamedTemporaryFile("w", suffix=".xml", delete=False,
                                     encoding="utf-8") as tf:
        tf.write(_query(facts))
        xml_path = tf.name
    try:
        res = run([pac, "env", "fetch", "--xmlFile", xml_path, "--environment", url],
                  capture_output=True, text=True)
        if res.returncode != 0:
            raise Refused(f"pac env fetch failed:\n{res.stdout}\n{res.stderr}")
        return res.stdout, warnings
    finally:
        try:
            os.unlink(xml_path)
        except OSError:
            pass
        if prior:
            run([pac, "auth", "select", "--index", prior], capture_output=True, text=True)
        else:
            warnings.append(
                f"could not read the previously-active pac profile, so it was not restored. "
                f"Your active profile is now '{profile}' — run `pac auth list` and "
                f"re-select if that is not what you want.")

"""Read the user's `.context.md` § "Work-item source": the one place an account's facts live.

The section is a list of `- Label: value` lines. Deeper headings (`### Case creation`) are
prose for the model and are not parsed. A value still holding the starter template's
`<placeholder>` is not a value.
"""
from __future__ import annotations

import re
from pathlib import Path

SECTION = "Work-item source"
CONTEXT_FILE = Path("Timesheets") / ".context.md"
_PLACEHOLDER = re.compile(r"^<[^>]*>$")


def read_section(workspace: Path) -> dict[str, str]:
    """Label (lower-cased) -> value for the section, or {} when there is none."""
    path = workspace / CONTEXT_FILE
    if not path.is_file():
        return {}
    found: dict[str, str] = {}
    inside = False
    for line in path.read_text(encoding="utf-8").splitlines():
        heading = re.match(r"^(#{1,6})\s+(.*?)\s*$", line)
        if heading:
            if len(heading.group(1)) <= 2:
                inside = heading.group(2).lower() == SECTION.lower()
            continue
        if not inside:
            continue
        item = re.match(r"^[-*]\s+([^:]+?):\s*(.*?)\s*$", line)
        if item:
            value = item.group(2).strip().strip("`")
            if value and not _PLACEHOLDER.match(value):
                found[item.group(1).strip().lower()] = value
    return found

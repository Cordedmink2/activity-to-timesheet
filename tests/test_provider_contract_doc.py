"""The provider contract names no Harvest wire-format field (#33, acceptance item 2).

`docs/provider-contract.md` is the surface every layer above the adapter talks to. A field
name that belongs to the provider's own API — `started_time`, `spent_date`, `hours` — in that
document means the seam leaks: a second provider would have to either reproduce Harvest's
names or break the contract. The contract speaks `date`, `start`, `end` instead, and the
adapter maps.

This reads the document as text and nothing else: it makes no request, runs no script and
reads no credential. Whole words only, so `ours` or `hourly` never trips `hours`, and
the check is case-insensitive because a capitalised spelling is the same leak.
"""

import re

from shipped import REPO

DOC = REPO / "docs" / "provider-contract.md"

# Harvest's wire format: the time-entry fields, the response envelope keys and paging
# parameters, the request headers, and the endpoint paths. Not `notes`, `project_id` or
# `task_id`: those are the contract's own names too (the issue keeps `--project-id` and
# `--task-id` as opaque identifiers), so banning them would be wrong about the contract.
WIRE_FORMAT_NAMES = (
    "started_time",
    "ended_time",
    "spent_date",
    "hours",
    "rounded_hours",
    "is_running",
    "time_entries",
    "project_assignments",
    "task_assignments",
    "total_entries",
    "next_page",
    "per_page",
    "user_id",
    "Harvest-Account-Id",
    "harvest_assignments",
    "users/me",
    "api.harvestapp.com",
)

FIX = """
The contract document speaks the contract's own vocabulary: `date`, `start`, `end`,
`project_id`, `task_id`, `notes`. A provider's wire-format names belong to the adapter and
stay out of this document, including in examples and in the mapping table. Say what the
adapter does in words (`maps the date and the two clock times onto what the provider stores`)
rather than naming the field it writes.
"""


def occurrences(text: str):
    """(line number, name) for every wire-format name found, as a whole word."""
    found = []
    for name in WIRE_FORMAT_NAMES:
        pattern = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])",
                             re.IGNORECASE)
        for number, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                found.append((number, name))
    return sorted(found)


def test_the_contract_document_exists_and_has_the_five_commands():
    text = DOC.read_text(encoding="utf-8")
    for sub in ("post", "patch", "lookup", "list", "refresh"):
        assert f"timesheet-provider {sub}" in text or f"`{sub}`" in text, (
            f"{DOC.name} does not describe the `{sub}` subcommand")


def test_no_wire_format_name_appears_in_the_contract():
    text = DOC.read_text(encoding="utf-8")
    hits = occurrences(text)
    assert not hits, (
        f"{DOC.relative_to(REPO).as_posix()} names the provider's wire format:\n  "
        + "\n  ".join(f"line {n}: {name}" for n, name in hits) + "\n" + FIX)


def test_the_guard_catches_what_it_is_for():
    """A scan that finds nothing in a clean document proves nothing about the scan."""
    leaky = "Send `started_time` and `spent_date`.\nDuration in Hours.\nOne hourly rate, ours.\n"
    assert occurrences(leaky) == [(1, "spent_date"), (1, "started_time"), (2, "hours")]
    assert occurrences("date, start and end, in the user's zone") == []

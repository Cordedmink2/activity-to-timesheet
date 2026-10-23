"""The clients and their category terms, read from the workspace context file.

The one parser of a client's `**Client name**` and `**Category terms**` lines. Terms have one
home, the context file; `category_rules.py` compiles rules from what this reads and
`checkin_answers.py` classifies answers against it, so neither keeps a list of its own.

Narrow on purpose: only each `###` client section under `## Active client projects`, only
those two lines, and only the backticked words before a line's ` \u2014 ` note. Everything
else in the file is prose and is not read. A terms line it cannot read raises
`ContextError` naming the line, so nothing is guessed.

Imports nothing from the other scripts, so both halves can share it.
"""
import re
from pathlib import Path

CONTEXT_FILE = Path("Timesheets") / ".context.md"


class ContextError(Exception):
    """The context file cannot be read as a list of clients, in words a run can act on."""


CLIENT_SECTIONS = re.compile(r"^## Active client projects\s*$(.*?)(?=^## |\Z)",
                             re.MULTILINE | re.DOTALL)
SPAN = re.compile(r"`([^`]*)`")


def _line_value(section: str, label: str) -> tuple[str, int] | None:
    """The text after `**label**:` in a client section, and its offset, or None."""
    found = re.search(rf"^\*\*{re.escape(label)}\*\*:[ \t]*(.*)$", section, re.MULTILINE)
    return (found.group(1), found.start()) if found else None


def parse_context(text: str) -> tuple[list[dict], list[str]]:
    """The candidates the workspace context file declares, in file order, and the names of
    the clients left out for declaring no terms.

    Narrow on purpose: only each `###` client section under `## Active client projects`,
    only its `**Client name**` and `**Category terms**` lines, and only the backticked words
    before the line's ` — ` note. Everything else in the file is prose and is not read. A
    terms line it cannot read is a refusal naming the line, so nothing is guessed.
    """
    block = CLIENT_SECTIONS.search(text)
    if not block:
        raise ContextError("the context file has no `## Active client projects` section, so no "
                      "client is declared")
    body = block.group(1)
    base = text[:block.start(1)].count("\n")
    candidates: list[dict] = []
    left_out: list[str] = []
    placeholders = 0
    parts = re.split(r"^### (.+)$", body, flags=re.MULTILINE)
    for index in range(1, len(parts), 2):
        heading, section = parts[index].strip(), parts[index + 1]
        named = _line_value(section, "Client name")
        named_span = SPAN.search(named[0]) if named else None
        client = named_span.group(1).strip() if named_span else heading
        terms_line = _line_value(section, "Category terms")
        if terms_line is None:
            if client.startswith("<"):
                placeholders += 1
            else:
                left_out.append(client)
            continue
        value, offset = terms_line
        number = base + body[:body.find(section)].count("\n") + section[:offset].count("\n") + 1
        words = value.split(" \u2014 ")[0].split(" - ")[0]
        spans = [m.strip() for m in SPAN.findall(words)]
        leftover = SPAN.sub("", words).replace(",", "").replace(" and ", "").strip()
        if leftover or not spans:
            raise ContextError(f"cannot read the `Category terms` line for {client} (line {number}): "
                          f"give each term in backticks, separated by commas")
        if client.startswith("<") or all(t.startswith("<") for t in spans):
            placeholders += 1
            continue
        candidates.append({"client": client, "terms": spans})
    if not candidates:
        why = ("only template placeholders, which are not clients" if placeholders
               else "no client with `Category terms`")
        raise ContextError(f"no client to build rules for: the context file holds {why}"
                      if placeholders or left_out else
                      "no client is declared in the context file")
    return candidates, left_out


def load_clients(root: Path) -> tuple[list[dict], list[str]]:
    """`parse_context` of the workspace's own context file."""
    path = root / CONTEXT_FILE
    if not path.is_file():
        raise ContextError(f"there is no {path} to build rules from")
    return parse_context(path.read_text(encoding="utf-8"))

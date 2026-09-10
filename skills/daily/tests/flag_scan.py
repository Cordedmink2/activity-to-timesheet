"""The flags a script parses, read out of its source.

One copy, because two suites hold two documents against the same scripts and a comparison
that reads the source two ways would disagree with itself: `skills/daily/tests/test_references.py`
holds the `daily` skill's own "Files in this skill" inventory to *equality* with the flags each
script parses, and the repo-level `tests/test_reconcile_skill.py` holds the `reconcile` skill's
copy — which invokes the same scripts from a sibling directory — to *inclusion* (#31). The
second suite has no `daily` module on its import path by design (`tests/test_plugin_config.py`
says why), so it loads this file by path. Nothing here imports anything of the skill's.
"""

import ast
import re
from pathlib import Path

# A flag as it is written in either place. Case is allowed through rather than filtered
# out — `pac` takes a `--xmlFile`, and a camelCase flag added to a script one day should be
# caught by the rule below that excludes another program's argv, not missed by this regex.
# An underscore for the same reason, and because leaving it out is worse than a plain miss:
# `--dry_run` would be invisible on the parsed side and read as `--dry` on the documented
# one, so documenting it correctly would fail the test naming a flag nobody wrote.
FLAG = re.compile(r"--[A-Za-z][A-Za-z0-9_-]*")
FLAG_ONLY = re.compile(FLAG.pattern + r"\Z")


def _subprocess_argv(tree: ast.AST) -> set[int]:
    """Node ids of the string literals that make up an argv handed to another program.

    A `--flag` inside `subprocess.run([...])` is that program's flag, not this script's:
    `refresh_catalogs.py` passes `--name`, `--index`, `--environment` and `--xmlFile` to
    `pac`, and without this they would read as four flags the inventory must list.

    Both spellings of the call are matched, `subprocess.run(...)` and an imported bare
    `run(...)`, but the argv has to be a list or tuple written at the call. Build it into a
    variable first — `cmd = [pac_cmd, ...]` then `subprocess.run(cmd)`, which is how this
    code grows the moment an argument becomes conditional — and the exclusion stops
    reaching it. That failure is loud rather than silent: the flags surface as ones
    `refresh_catalogs.py` supposedly parses and the comparison fails. The assertion message
    says what to do about it, because the obvious response is the wrong one.
    """
    launchers = {"run", "Popen", "call", "check_call", "check_output"}
    skipped: set[int] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and node.args):
            continue
        func = node.func
        spawns = ((isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)
                   and func.value.id == "subprocess")
                  or (isinstance(func, ast.Name) and func.id in launchers))
        if not spawns:
            continue
        if isinstance(node.args[0], (ast.List, ast.Tuple)):
            skipped.update(id(element) for element in node.args[0].elts)
    return skipped


def flags_a_script_parses(path: Path) -> set[str]:
    """Every flag `path` accepts, read out of its syntax tree.

    A flag counts when the source contains a string literal that is *exactly* a flag —
    which is the same thing as the script comparing an argument against it. That covers all
    three parsing shapes this skill ships without knowing which is which: argparse's
    `add_argument("--json")`, `harvest_patch.py`'s `FLAGS` table, and the bare
    `a != "--by-day"` filter in `harvest_list.py`. A flag named inside a longer string — a
    usage line, a module docstring — is documentation and does not count, so the literal has
    to match end to end.

    Read as text rather than by importing the module and inspecting its parser, which is
    what this test was first imagined as. Only four of the eleven scripts use argparse, and
    all four build the parser inside `main()`, so an import alone reaches no parser: that
    route means refactoring four scripts to expose a builder and still leaves the three
    hand-rolled parsers uncovered. The trade is that this cannot see a flag assembled at
    runtime; nothing here assembles one, and a test for the inventory being *complete* is
    worth more than one that is exact about a shape nobody uses.

    Two blind spots worth naming, since both look like holes and only one is:

    * `action=argparse.BooleanOptionalAction` on `--full` would make `--no-full` parseable
      with that string appearing nowhere in the source, so the inventory would never be
      asked for it. That is the same class as runtime assembly and a good deal likelier to
      be reached here — negating a boolean flag is the ordinary next edit to one.
    * `-h` / `--help` is accepted by every argparse script and has no literal either. That
      one is a correct omission: nobody wants `--help` in the inventory. A short option
      added beside a long one (`-j` for `--json`) is not held for the same reason, and the
      long form it accompanies still is.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    skipped = _subprocess_argv(tree)
    return {node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
            and FLAG_ONLY.match(node.value) and id(node) not in skipped}


# What a document sets apart as something to type: a fenced block, or an inline span.
# Flags are read out of these alone. A document's prose is where the words "--" and a
# letter could meet by accident, and a scan over the whole file would fail it for a
# sentence — the reconcile skill's `SKILL.md` is a walkthrough, not an inventory bullet.
CODE = re.compile(r"```.*?```|`[^`\n]+`", re.S)


def flags_a_document_types(text: str) -> set[str]:
    """Every flag a markdown document writes inside a code span or a fenced block."""
    return {flag for span in CODE.findall(text) for flag in FLAG.findall(span)}


INLINE = re.compile(r"`[^`\n]+`")


def typed_lines(text: str) -> list[tuple[str, set[str]]]:
    """Each line of a markdown document that types a flag: the code on that line, and its
    flags.

    The same material `flags_a_document_types` reads, but kept to the document's own lines,
    so a caller can hold a flag against the script named *beside* it rather than against
    every script at once. The distinction matters when two scripts share a flag: `--window`
    renamed in `activity_timeline.py` alone is still parsed by `afk_blocks.py`, so a union of
    the two goes on accepting a line that tells a run to pass the old name to the wrong
    script. A walkthrough line typically names the script in one code span and the flag in
    the next — `` `python ".../activity_timeline.py" <date>` … `--window HH:MM-HH:MM` `` —
    which is why the unit is the line and the spans on it are joined. Inside a fenced block
    every line is code; the fence lines themselves are dropped, so a language tag never
    reads as a flag.
    """
    out = []
    in_fence = False
    for raw in text.splitlines():
        if raw.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            code = raw.strip()
        else:
            code = " ".join(span.strip("`") for span in INLINE.findall(raw))
        flags = set(FLAG.findall(code))
        if flags:
            out.append((code, flags))
    return out

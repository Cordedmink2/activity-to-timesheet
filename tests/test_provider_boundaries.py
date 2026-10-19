"""The provider contract's structural promises, read out of the source (#35).

Three things the contract says once, and nothing but a guard keeps true:

1. **The confirmation gate exists once, in the dispatcher** (section 2, #22). An adapter's
   write functions are called from one place, behind the gate, and an adapter carries no
   gate of its own - so a new write path cannot bypass it by being written in an adapter, and
   a second gate cannot grow beside the first.
2. **Credentials are reached only through the selected adapter** (section 5). Neither the
   dispatcher nor any other module names a credential variable or reads one.
3. **No caller above the adapter reads the provider's catalog or fields** (section 8.2).
   Checked *line by line*, which the per-file guard in `test_provider_contract_doc.py` cannot
   do: it asks whether a file has a row, so a new read added to a file that already has one
   passes it (the #101 reviewer's warning 1).

Read as syntax trees and text: no request is made, no script runs, no credential is read.
"""
from __future__ import annotations

import ast
import re

from shipped import REPO

PROVIDER = REPO / "skills" / "daily" / "scripts" / "provider"
DISPATCHER = PROVIDER / "dispatcher.py"
SCRIPTS = REPO / "skills" / "daily" / "scripts"


def tree(path):
    return ast.parse(path.read_text(encoding="utf-8"))


def adapter_modules():
    return sorted(p for p in PROVIDER.rglob("*.py")
                  if "harvest" in p.relative_to(PROVIDER).parts or p.name == "provider_config.py")


# ------------------------------------------------------------------ 1. the gate, once

def attribute_calls(root, names):
    return [n for n in ast.walk(root)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr in names]


def test_an_adapters_write_functions_are_called_from_the_gate_and_nowhere_else():
    """`adapter.post(...)` / `adapter.patch(...)` appear in the dispatcher only inside a
    lambda handed to `_write()` - the gate - and in no other module of the plugin."""
    allowed = []
    for node in ast.walk(tree(DISPATCHER)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == "_write":
            for arg in node.args:
                if isinstance(arg, ast.Lambda):
                    allowed += attribute_calls(arg, {"post", "patch"})
    everywhere = attribute_calls(tree(DISPATCHER), {"post", "patch"})
    assert len(allowed) == 2, "expected exactly the two writes, post and patch, in the gate"
    assert len(everywhere) == len(allowed), (
        "an adapter write is called outside the gate (`_write`)")

    others = []
    for path in sorted(SCRIPTS.rglob("*.py")):
        if path == DISPATCHER or "__pycache__" in path.parts:
            continue
        for call in attribute_calls(tree(path), {"post", "patch"}):
            assert isinstance(call.func, ast.Attribute)
            target = ast.unparse(call.func.value)
            if target in ("adapter", "selected_adapter()"):
                others.append(f"{path.relative_to(REPO).as_posix()}:{call.lineno}")
    assert not others, "an adapter write is reached from outside the dispatcher:\n  " + "\n  ".join(others)


def test_the_gate_checks_then_previews_and_only_then_writes():
    """`_write` is the gate: the pre-flight check first (so a refusal previews nothing), the
    preview and return when unconfirmed, and the write last."""
    write = next(n for n in tree(DISPATCHER).body
                 if isinstance(n, ast.FunctionDef) and n.name == "_write")
    calls = [(n.lineno, ast.unparse(n.func)) for n in ast.walk(write) if isinstance(n, ast.Call)]
    check = next(l for l, f in calls if f == "check")
    perform = next(l for l, f in calls if f == "perform")
    ifs = [n for n in write.body if isinstance(n, ast.If)]
    assert len(ifs) == 1 and ast.unparse(ifs[0].test) == "not confirmed"
    assert any(isinstance(n, ast.Return) for n in ifs[0].body), "the unconfirmed branch must return"
    assert check < ifs[0].lineno < perform


def test_no_adapter_carries_a_gate_of_its_own():
    """The gate is the dispatcher's once; an adapter never sees an unconfirmed write, so it
    has neither the flag nor a preview."""
    offenders = []
    for path in adapter_modules():
        text = path.read_text(encoding="utf-8")
        code = "\n".join(l for l in text.splitlines() if not l.strip().startswith("#"))
        if re.search(r"--confirm|WOULD (POST|PATCH)|\bconfirmed\b", code.replace('"""', "")) \
                and "def check_" in code:
            for n, line in enumerate(text.splitlines(), 1):
                if re.search(r"--confirm|WOULD (POST|PATCH)", line) and not line.strip().startswith(("#", "*")):
                    offenders.append(f"{path.relative_to(REPO).as_posix()}:{n}: {line.strip()[:80]}")
    assert not offenders, "an adapter names the gate:\n  " + "\n  ".join(offenders)


def test_the_gate_is_taken_off_argv_before_anything_is_read_positionally():
    """Both writes remove `--confirm` first, wherever it was typed."""
    src = DISPATCHER.read_text(encoding="utf-8")
    for name in ("_post", "_patch"):
        fn = next(n for n in tree(DISPATCHER).body
                  if isinstance(n, ast.FunctionDef) and n.name == name)
        first = ast.unparse(fn.body[0])
        assert "take_gate" in first, f"{name} must take the gate before it parses: {first}"
    assert src.count("CONFIRM_FLAG") >= 3


# ------------------------------------------------------------------ 2. credentials

CREDENTIAL_NAMES = re.compile(r"HARVEST_(ACCOUNT_ID|API_KEY)")


def test_only_the_selected_adapter_names_a_credential():
    named = sorted(p.relative_to(REPO).as_posix() for p in SCRIPTS.rglob("*.py")
                   if "__pycache__" not in p.parts
                   and CREDENTIAL_NAMES.search(p.read_text(encoding="utf-8"))
                   and "provider/harvest/" not in p.as_posix())
    assert not named, f"a credential variable is named outside the Harvest adapter: {named}"


def test_the_dispatcher_reads_no_credential_and_does_not_import_the_config_helper():
    names = {n.id for n in ast.walk(tree(DISPATCHER)) if isinstance(n, ast.Name)}
    imported = {a.name for n in ast.walk(tree(DISPATCHER))
                if isinstance(n, (ast.Import, ast.ImportFrom))
                for a in n.names} | {n.module for n in ast.walk(tree(DISPATCHER))
                                     if isinstance(n, ast.ImportFrom) and n.module}
    assert "provider_config" not in imported and "require" not in names
    assert not CREDENTIAL_NAMES.search(DISPATCHER.read_text(encoding="utf-8"))


def test_an_adapter_imports_neither_another_adapter_nor_the_dispatcher():
    offenders = []
    for path in PROVIDER.rglob("*.py"):
        parts = path.relative_to(PROVIDER).parts
        if len(parts) < 2 or parts[0] == "bin":
            continue
        adapter = parts[0]
        for node in ast.walk(tree(path)):
            mods = ([a.name for a in node.names] if isinstance(node, ast.Import)
                    else [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
            for mod in mods:
                head = mod.split(".")
                if head[0] == "provider" and len(head) > 1 and (
                        head[1] == "dispatcher" or (head[1] != adapter and head[1] not in (
                            "errors", "provider_config"))):
                    offenders.append(f"{path.relative_to(REPO).as_posix()}: {mod}")
    assert not offenders, "\n  ".join(offenders)


# ------------------------------------------------------------------ 3. no caller reads the catalog

# The reviewer's own line-level pattern (#101, round 3).
CATALOG = re.compile(
    r"task_assignments|harvest_assignments|project_assignments|project\.(code|id|name)"
    r"|client\.(name|id)|\.billable|mtime|is_active|hourly_rate|budget")

# A line may match and be fine, but only by being listed here, with why. A new read added to
# a file that already has an entry still fails: the unit is the line.
ALLOWED = {
    # `budget` is the `.context.md` size budget, nothing to do with a project's.
    "size budget": "the `.context.md` size budget",
    "billing-convention *overrides*, machine specifics": "the `.context.md` size budget cross-reference",
}


def test_no_shipped_prose_reads_the_providers_catalog_by_file_or_field_line_by_line():
    offenders = []
    for path in sorted((REPO / "skills").rglob("*.md")):
        if "tests" in path.relative_to(REPO).parts:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if CATALOG.search(line) and not any(key in line for key in ALLOWED):
                offenders.append(f"{path.relative_to(REPO).as_posix()}:{number}: "
                                 f"{CATALOG.search(line).group(0)}")   # type: ignore[union-attr]
    assert not offenders, (
        "shipped prose names the provider's catalog files or fields, which the contract makes "
        "the adapter's (section 8.2). Say it through `timesheet-provider lookup`'s own names "
        "(`project_id`, `tasks[]`, `billable`):\n  " + "\n  ".join(offenders))


def test_the_line_scan_finds_a_read_the_per_file_scan_would_miss():
    """A scan that finds nothing in clean prose proves nothing about the scan."""
    assert CATALOG.search("read `task_assignments[]` for the project")
    assert CATALOG.search("a stale catalog: its `.mtime` is old")
    assert not CATALOG.search("the tasks `lookup` lists, and their `billable` flag")


def test_the_retired_scripts_are_named_nowhere_in_shipped_prose():
    retired = re.compile(r"harvest_(post|patch|list|lookup|write|client)\b|wait_for_project"
                         r"|--no-live|--mcp-dir|--harvest-only")
    offenders = []
    for path in sorted((REPO / "skills").rglob("*.md")):
        if "tests" in path.relative_to(REPO).parts:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if retired.search(line):
                offenders.append(f"{path.relative_to(REPO).as_posix()}:{number}")
    assert not offenders, "a caller still names a retired script or flag:\n  " + "\n  ".join(offenders)

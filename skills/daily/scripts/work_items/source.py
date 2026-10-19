"""The work-item source seam: choose the adapter, enforce the boundary's rules, write the
catalog. Names no adapter and no account — both come from the directory and `.context.md`.
"""
from __future__ import annotations

import importlib
import pkgutil
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Callable

from skill_config import setting
from work_items import adapters, context
from work_items.errors import Misconfigured, Refused

CATALOG_NAME = "work_item_catalog.txt"

_default_run = subprocess.run
_default_which = shutil.which


@dataclass
class Outcome:
    kind: str  # "refreshed" | "not-configured"
    message: str
    count: int = 0


def adapter_names() -> list[str]:
    return sorted(m.name for m in pkgutil.iter_modules(adapters.__path__))


def _load(name: str) -> ModuleType:
    return importlib.import_module(f"work_items.adapters.{name}")


def _old_shape() -> list[tuple[str, str, str]]:
    """(old key, replacement label, adapter) for every old setting still present."""
    found = []
    for name in adapter_names():
        for key, label in _load(name).LEGACY.items():
            if setting(key) is not None:
                found.append((key, label, name))
    return found


def _old_shape_message(found, ignored: bool) -> str:
    lines = []
    for key, label, name in found:
        lines.append(
            f"{key} is set, and it is the old shape: since #37 the {name} adapter reads "
            f"'{label}' from your .context.md § \"{context.SECTION}\" instead.")
    if ignored:
        return ("WARN the old settings below are ignored now — remove them.\n  "
                + "\n  ".join(lines))
    return ("\n".join(lines) + f"\nAdd `- Adapter: {found[0][2]}` and the labels to that "
            "section (see the daily skill's references/context.md.example), then remove "
            "the old setting.")


def _count(text: str) -> int:
    rows = [line for line in text.splitlines() if line.strip()]
    return max(len(rows) - 1, 0)  # the first row is the column header


def _write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def refresh(workspace: Path, run: Callable | None = None,
            which: Callable | None = None) -> Outcome:
    run = run or _default_run
    which = which or _default_which
    facts = context.read_section(workspace)
    old = _old_shape()
    name = facts.get("adapter")

    if not name:
        if old:
            raise Misconfigured(_old_shape_message(old, ignored=False))
        return Outcome(
            "not-configured",
            f"No work-item source is configured, so no work-item catalog was refreshed. "
            f"To use one, add a \"{context.SECTION}\" section to Timesheets/.context.md "
            f"(adapters: {', '.join(adapter_names())}).")

    if name.lower() not in adapter_names():
        raise Misconfigured(
            f"unknown work-item adapter '{name}' in .context.md § \"{context.SECTION}\". "
            f"Known: {', '.join(adapter_names())}.")
    adapter = _load(name.lower())
    absent = [label for label in adapter.REQUIRED if label.lower() not in facts]
    if absent:
        raise Misconfigured(
            f".context.md § \"{context.SECTION}\" is missing: {', '.join(absent)}.")

    text, warnings = adapter.fetch(facts, run, which)
    if _count(text) == 0:
        raise Refused(
            "the work-item source returned no work items; the existing catalog is left "
            "untouched. An empty catalog is a failure, not a healthy one.")
    mcp = workspace / ".mcp"
    mcp.mkdir(parents=True, exist_ok=True)
    _write(mcp / CATALOG_NAME, text)
    count = _count(text)
    lines = [f"  ✓ {count} work items written to {CATALOG_NAME}"] + [
        f"  WARN {w}" for w in warnings]
    if old:
        lines.append("  " + _old_shape_message(old, ignored=True))
    return Outcome("refreshed", "\n".join(lines), count)

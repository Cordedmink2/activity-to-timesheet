"""The dispatcher behind `timesheet-provider` (docs/provider-contract.md).

It holds what the contract says no adapter may: **the confirmation gate, once** (§ 2), the
argument validation (§ 1, § 3), the adapter selection, the output formats and the exit-code
classes (§ 4). It reads no credential - `provider_config.require()` is the adapters' - and
it imports an adapter only by the name `TIMESHEET_PROVIDER` selects.

  main() -> int      the command line, from `sys.argv`; returns the exit code

An adapter is a module (or any object) with the interface in § 6.2: `NAME`, `check_post`,
`check_patch`, `post`, `patch`, `lookup`, `list_entries`, `refresh`, and `catalog_age`
(what `refresh --age` asks, so no caller reads the catalog's files). It signals a failure by
raising one of `provider.errors`; the dispatcher maps the class to its number.

**The gate.** `--confirm` is taken out of argv before anything is read positionally, so a
value flag left without its value cannot swallow it. `post` and `patch` then run the
adapter's read-only pre-flight check on the preview and the confirmed run alike, and only a
confirmed run calls `adapter.post` / `adapter.patch`. Those two functions are called from
`_write()` below and from nowhere else, which `tests/test_provider_boundaries.py` holds.
The preview body is the very dict handed to the adapter, so what the user approved and what
is sent cannot come apart.

**No traceback, ever.** Anything unexpected is `ERR internal ...`, exit 1.
"""
from __future__ import annotations

import datetime as dt
import importlib
import io
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, NamedTuple

import skill_config
from provider.errors import (Misconfigured, NoMatch, ProviderError, Refused, Unreachable,
                             Usage)

PROG = "timesheet-provider"
CONFIRM_FLAG = "--confirm"
DEFAULT_ADAPTER = "harvest"
SUBCOMMANDS = ("post", "patch", "lookup", "list", "refresh")

CLOCK = re.compile(r"([01]\d|2[0-3]):[0-5]\d\Z")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")

USAGE = f"""usage: {PROG} <post|patch|lookup|list|refresh> [arguments]

  post   --project-id ID --task-id ID --date YYYY-MM-DD --start HH:MM --end HH:MM
         --notes TEXT [--confirm]
  patch  ENTRY_ID [--project-id ID] [--task-id ID] [--date YYYY-MM-DD] [--start HH:MM]
         [--end HH:MM] [--notes TEXT] [--confirm]
  lookup QUERY [--task NAME] [--json] [--cache-only] [--days N] [--catalog-dir DIR]
  list   FROM [TO] [--by-day]
  refresh [--wait CODE [--attempts N] [--delay SECONDS]]
  refresh --age

Without --confirm, post and patch preview and write nothing.
Every failure is one `ERR ...` line on stderr and an exit code: 2 usage, 3 missing
configuration, 4 refused, 5 unreachable, 6 no match, 1 internal."""


# ------------------------------------------------------------------ argument parsing

class Spec(NamedTuple):
    values: dict[str, str]            # flag -> name of the value it carries
    booleans: tuple[str, ...] = ()
    positionals: tuple[int, int] = (0, 0)   # (min, max)
    names: tuple[str, ...] = ()       # what each positional is called, for the message


class Parsed(NamedTuple):
    values: dict[str, str]
    flags: set[str]
    positionals: list[str]


def _parse(argv: list[str], spec: Spec) -> Parsed:
    """The rules every subcommand shares: a flag is given once, a value flag has a value,
    and a flag the subcommand does not have is a usage error."""
    known = set(spec.values) | set(spec.booleans)
    values: dict[str, str] = {}
    flags: set[str] = set()
    positionals: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in spec.values:
            if arg in values:
                raise Usage(f"{arg} given more than once; pass it once with the final value")
            if i + 1 >= len(argv) or argv[i + 1] in known:
                raise Usage(f"{arg} needs a value")
            values[arg] = argv[i + 1]
            i += 2
        elif arg in spec.booleans:
            flags.add(arg)          # a boolean said twice says the same thing twice
            i += 1
        elif arg.startswith("--"):
            raise Usage(f"unknown flag {arg}")
        else:
            positionals.append(arg)
            i += 1
    low, high = spec.positionals
    if not low <= len(positionals) <= high:
        shown = " ".join(spec.names) if spec.names else "no positional arguments"
        raise Usage(f"expected {shown}, got {len(positionals)} positional argument(s)")
    return Parsed(values, flags, positionals)


def _date(flag: str, text: str) -> str:
    if not DATE.match(text):
        raise Usage(f"{flag} must be YYYY-MM-DD, got {text!r}")
    try:
        return dt.date.fromisoformat(text).isoformat()
    except ValueError:
        raise Usage(f"{flag} is not a real date: {text!r}") from None


def _clock(flag: str, text: str) -> str:
    if not CLOCK.match(text):
        raise Usage(f"{flag} must be HH:MM, 24-hour and zero-padded, got {text!r}. "
                    "A second-pass marker is not accepted: strip it before the call.")
    return text


def _positive_int(flag: str, text: str) -> int:
    try:
        n = int(text)
    except ValueError:
        raise Usage(f"{flag} expects a whole number, got {text!r}") from None
    if n < 1:
        raise Usage(f"{flag} must be at least 1, got {n}")
    return n


def _minutes(text: str) -> int:
    return int(text[:2]) * 60 + int(text[3:])


def _ordered(start: str, end: str) -> None:
    # A provider can silently store a reversed range as a day-long entry, so the contract
    # refuses it before any adapter is asked.
    if _minutes(end) <= _minutes(start):
        raise Usage(f"--start ({start}) must be before --end ({end}). A provider can "
                    "silently store a reversed range as a day-long entry, and an equal "
                    "one as no time at all.")


# Body keys in the contract's own order (§ 3.1); a patch carries only those passed.
BODY_FLAGS = {
    "--project-id": "project_id", "--task-id": "task_id", "--date": "date",
    "--start": "start", "--end": "end", "--notes": "notes",
}


def _body(values: dict[str, str]) -> dict[str, str]:
    checked: dict[str, str] = {}
    for flag, key in BODY_FLAGS.items():
        if flag not in values:
            continue
        raw = values[flag]
        if key == "date":
            checked[key] = _date(flag, raw)
        elif key in ("start", "end"):
            checked[key] = _clock(flag, raw)
        elif key in ("project_id", "task_id"):
            if not raw.strip():
                raise Usage(f"{flag} must not be empty")
            checked[key] = raw
        else:
            checked[key] = raw
    return checked


# ------------------------------------------------------------------ the gate

def take_gate(argv: list[str]) -> tuple[list[str], bool]:
    """`argv` with the gate removed wherever it appears, and whether it was there.

    Called before anything is read positionally. Removing the flag *first* is what stops a
    field flag left without its value from consuming it. A note spelled exactly `--confirm`
    is eaten too, and the count or the value then falls short: a usage error rather than a
    silent write. The gate is a boolean, so a repeated one is not an error.
    """
    rest = [a for a in argv if a != CONFIRM_FLAG]
    return rest, len(rest) != len(argv)


def _preview_body(body: dict[str, str]) -> str:
    return json.dumps(body, ensure_ascii=False)


def _write(confirmed: bool, preview: str, footer: str,
           check: Callable[[], None], perform: Callable[[], str]) -> int:
    """The gate. The only caller of an adapter's write functions, via `perform`."""
    check()                                 # read-only; refusal stops before any preview
    if not confirmed:
        print(preview)
        print(footer)
        return 0
    print(f"OK {perform()}")
    return 0


def _post(argv: list[str]) -> int:
    rest, confirmed = take_gate(argv)
    parsed = _parse(rest, Spec({f: f for f in BODY_FLAGS}))
    missing = [f for f in BODY_FLAGS if f not in parsed.values]
    if missing:
        raise Usage(f"post needs {', '.join(missing)}")
    body = _body(parsed.values)
    _ordered(body["start"], body["end"])
    adapter = selected_adapter()
    return _write(
        confirmed, f"WOULD POST {_preview_body(body)}",
        f"Nothing was posted. Re-run with {CONFIRM_FLAG} to create this entry.",
        lambda: adapter.check_post(body), lambda: adapter.post(body))


def _patch(argv: list[str]) -> int:
    rest, confirmed = take_gate(argv)
    parsed = _parse(rest, Spec({f: f for f in BODY_FLAGS}, positionals=(1, 1),
                               names=("ENTRY_ID",)))
    (entry_id,) = parsed.positionals
    if not parsed.values:
        raise Usage("patch needs at least one field to change: "
                    + ", ".join(BODY_FLAGS))
    fields = _body(parsed.values)
    if "start" in fields and "end" in fields:
        _ordered(fields["start"], fields["end"])
    adapter = selected_adapter()
    return _write(
        confirmed, f"WOULD PATCH {entry_id} {_preview_body(fields)}",
        f"Nothing was changed. Re-run with {CONFIRM_FLAG} to apply it.",
        lambda: adapter.check_patch(entry_id, fields), lambda: adapter.patch(entry_id, fields))


# ------------------------------------------------------------------ lookup

RANK = {"code": 0, "code/name": 1, "client": 2}


def _lookup(argv: list[str]) -> int:
    parsed = _parse(argv, Spec({"--task": "task", "--days": "days", "--catalog-dir": "dir"},
                               ("--json", "--cache-only"), (1, 1), ("QUERY",)))
    (query,) = parsed.positionals
    days = _positive_int("--days", parsed.values["--days"]) if "--days" in parsed.values else 180
    catalog_dir = parsed.values.get("--catalog-dir")
    if catalog_dir is not None and not skill_config.has_value(catalog_dir):
        catalog_dir = None
    cache_only = "--cache-only" in parsed.flags
    adapter = selected_adapter()
    raw = adapter.lookup(query, parsed.values.get("--task"), catalog_dir, cache_only, days)
    if not raw:
        raise NoMatch(f"no project matching '{query}' in the catalog or recent entries")
    matches = sorted((_match(m) for m in raw), key=lambda m: (RANK[m["matched_on"]], m["code"]))
    if any(m["source"] == "history" for m in matches):
        print("NOTE not in the catalog (assignment likely archived); "
              f"recovered from own entries, last {days} days", file=sys.stderr)
    if "--json" in parsed.flags:
        print(json.dumps(matches, indent=2, ensure_ascii=False))
        return 0
    for m in matches:
        client = f"  [{m['client']}]" if m["client"] else ""
        print(f"{m['code']}  {m['project_id']}  {m['name']}{client}")
        for t in m["tasks"]:
            print(f"    {t['id']}  {t['name']}  ({'billable' if t['billable'] else 'NON-billable'})")
    return 0


def _match(m: dict) -> dict:
    """One match in the contract's shape: identifiers are strings, `source` is always there."""
    return {
        "code": str(m.get("code") or ""),
        "project_id": str(m["project_id"]),
        "name": str(m.get("name") or ""),
        "client": str(m.get("client") or ""),
        "matched_on": m["matched_on"],
        "source": m.get("source") or "catalog",
        "tasks": [{"id": str(t["id"]), "name": str(t.get("name") or ""),
                   "billable": bool(t.get("billable"))} for t in m.get("tasks", [])],
    }


# ------------------------------------------------------------------ list

def _range(argv: list[str]) -> tuple[Parsed, str, str]:
    parsed = _parse(argv, Spec({}, ("--by-day",), (1, 2), ("FROM", "[TO]")))
    first = _date("FROM", parsed.positionals[0])
    last = _date("TO", parsed.positionals[1]) if len(parsed.positionals) == 2 else first
    if last < first:
        # A reversed range would read as a month with no gaps in it.
        raise Usage(f"the range ends before it starts: {first} to {last}")
    return parsed, first, last


def _entry_key(e: dict) -> tuple:
    ident = str(e.get("id", ""))
    return (e.get("date") or "", e.get("start") or "--:--", not ident.isdigit(),
            int(ident) if ident.isdigit() else 0, ident)


def _list(argv: list[str]) -> int:
    parsed, first, last = _range(argv)
    adapter = selected_adapter()
    entries = list(adapter.list_entries(first, last))
    if not entries:
        # stderr, so stdout stays data: a day nobody billed and a run that did nothing
        # would otherwise look the same. The exit code tells it from a failed read.
        print(f"(no time entries from {first} to {last})", file=sys.stderr)
    if "--by-day" in parsed.flags:
        _print_by_day(entries, first, last)
        return 0
    for e in sorted(entries, key=_entry_key):
        start, end = e.get("start") or "--:--", e.get("end") or "--:--"
        hours = e.get("hours") or 0.0
        code = e.get("project_code") or "?"
        task = (e.get("task_name") or "?")[:25]
        notes = (e.get("notes") or "").replace("\n", " ").replace("\r", " ")
        notes = notes if len(notes) <= 60 else notes[:59] + "…"
        print(f"{str(e['id']):<10}  {e.get('date') or ''}  {start}-{end}  {hours:>5.2f}h  "
              f"{code:<11}  {task:<25}  {notes}")
    return 0


def _print_by_day(entries: list[dict], first: str, last: str) -> None:
    """One row per date in the range, the empty ones included: absence is exactly what an
    unbilled day looks like, and arithmetic over a hundred rows done by eye is wrong quietly."""
    start, end = dt.date.fromisoformat(first), dt.date.fromisoformat(last)
    dates = [(start + dt.timedelta(days=n)).isoformat() for n in range((end - start).days + 1)]
    totals = {d: 0.0 for d in dates}
    counts = {d: 0 for d in dates}
    codes: dict[str, list[str]] = {d: [] for d in dates}
    unplaced: list = []
    for e in entries:
        d = e.get("date")
        if d not in totals:
            unplaced.append(e.get("id", "?"))
            continue
        totals[d] += e.get("hours") or 0.0
        counts[d] += 1
        code = e.get("project_code") or "?"
        if code not in codes[d]:
            codes[d].append(code)
    for d in dates:
        weekday = dt.date.fromisoformat(d).strftime("%a")
        unit = "entry  " if counts[d] == 1 else "entries"
        print(f"{d}  {weekday}  {totals[d]:>6.2f}h  {counts[d]:>2} {unit}  "
              f"{', '.join(codes[d]) or '-'}")
    if unplaced:
        print(f"(skipped {len(unplaced)} with no date inside the range: "
              f"{', '.join(str(i) for i in unplaced)})", file=sys.stderr)


# ------------------------------------------------------------------ refresh

def _refresh(argv: list[str]) -> int:
    parsed = _parse(argv, Spec({"--wait": "code", "--attempts": "n", "--delay": "seconds"},
                               ("--age",)))
    if "--age" in parsed.flags:
        if parsed.values:
            raise Usage("--age reads nothing from the provider and cannot be combined with "
                        + ", ".join(sorted(parsed.values)))
        age = selected_adapter().catalog_age()
        print("ABSENT" if age is None else f"AGE {int(age)}")
        return 0
    wait = parsed.values.get("--wait")
    if wait is None and ("--attempts" in parsed.values or "--delay" in parsed.values):
        raise Usage("--attempts and --delay only mean something with --wait CODE")
    attempts = _positive_int("--attempts", parsed.values["--attempts"]) \
        if "--attempts" in parsed.values else 20
    delay = 15.0
    if "--delay" in parsed.values:
        try:
            delay = float(parsed.values["--delay"])
        except ValueError:
            raise Usage(f"--delay expects seconds, got {parsed.values['--delay']!r}") from None
        if not 0 <= delay < float("inf"):
            raise Usage(f"--delay must be 0 or more seconds, got {parsed.values['--delay']!r}")
    if wait is not None and not skill_config.has_value(wait):
        raise Usage("--wait needs a project code")
    count = selected_adapter().refresh(wait, attempts, delay)
    print(f"OK {wait}" if wait is not None else f"OK {count} projects")
    return 0


# ------------------------------------------------------------------ adapter selection

def known_adapters() -> list[str]:
    """The adapters this install ships: every sub-package of `provider/` with an interface."""
    here = Path(__file__).resolve().parent
    return sorted(p.name for p in here.iterdir()
                  if p.is_dir() and (p / "__init__.py").is_file() and p.name != "bin")


def selected_adapter() -> Any:
    """The adapter `TIMESHEET_PROVIDER` names, harvest when unset or blank (§ 1).

    Resolved through `skill_config.setting()` like every other key, and imported only by
    that name. Importing it resolves no credential: a key is validated when read.
    """
    name = (skill_config.setting("TIMESHEET_PROVIDER", default=DEFAULT_ADAPTER)
            or DEFAULT_ADAPTER).strip()
    known = known_adapters()
    if name not in known:
        raise Usage(f"TIMESHEET_PROVIDER names no adapter: {name!r}. "
                    f"Known adapters: {', '.join(known)}")
    return importlib.import_module(f"provider.{name}")


# ------------------------------------------------------------------ main

HANDLERS: dict[str, Callable[[list[str]], int]] = {
    "post": _post, "patch": _patch, "lookup": _lookup, "list": _list, "refresh": _refresh,
}


def _utf8() -> None:
    """UTF-8 on both streams, set once (§ 1). A captured stream is left alone."""
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")


def _fail(error: ProviderError) -> int:
    print(f"ERR {error}", file=sys.stderr)
    return error.exit_code


def main() -> int:
    _utf8()
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        if argv:
            print(USAGE)
            return 0
        return _fail(Usage("no subcommand.\n" + USAGE))
    command, rest = argv[0], argv[1:]
    handler = HANDLERS.get(command)
    try:
        if handler is None:
            raise Usage(f"unknown subcommand {command!r}.\n{USAGE}")
        if rest in (["-h"], ["--help"]):
            print(USAGE)
            return 0
        return handler(rest)
    except ProviderError as e:
        return _fail(e)
    except SystemExit as e:
        # A setting that did not resolve ends the process through `skill_config.fail_missing()`
        # (the zone, the workspace). That is the contract's class 3, not a crash.
        if isinstance(e.code, str):
            return _fail(Misconfigured(e.code.removeprefix("ERROR: ")))
        raise
    except Exception as e:  # noqa: BLE001 - the contract: no traceback, ever
        return _fail(_Internal(f"internal {type(e).__name__}: {e}"))


class _Internal(ProviderError):
    exit_code = 1


__all__ = ["main", "selected_adapter", "known_adapters", "take_gate", "Refused", "Unreachable"]

"""One calendar day, filtered, in one JSON shape — whichever adapter read it.

The `daily` skill's fourth source (#49, ADR-0008). The user's calendar is evidence of
*intent* — what they were scheduled to be doing — and not of activity, and this script is
the boundary between the skill and whatever read that calendar. It owns three things:

  1. **Whether the calendar is on.** `TIMESHEET_OUTLOOK_CALENDAR` is a boolean setting,
     resolved through `skill_config.enabled()`: blank or anything but `true` is off, and
     off means this script exits non-zero saying so. Absent configuration is today's
     behaviour exactly; the skill does not run this unless the toggle is on.
  2. **Which adapter runs.** An adapter is any command that prints the raw calendar day
     for a date. The toggle names the first one — `outlook_calendar.ps1` beside this file,
     which reads classic Outlook's default calendar through its object model and is
     Windows-only because that object model is. `--adapter PATH` runs another instead:
     how a test supplies a fake, and how a second calendar is tried before it earns a
     toggle of its own.
  3. **The contract**: what an adapter must print, and what the rules downstream read.
     The rules never learn which adapter ran.

Usage:
  python scripts/calendar_day.py 2026-05-28
  python scripts/calendar_day.py 2026-05-28 --utc-offset 13        # this run only
  python scripts/calendar_day.py 2026-05-28 --adapter path/to/fake.py

## The adapter contract

Invoked as `<adapter> YYYY-MM-DD`: a `.ps1` through Windows PowerShell
(`powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File`, so it has to parse
under 5.1), a `.py` through the interpreter running this script, anything else directly.
It prints one UTF-8 JSON document to stdout and nothing else there:

  {"events": [
    {"id": "<stable within the calendar>",
     "subject": "Sprint review",
     "start": "2026-05-28T09:00:00+12:00",    ISO 8601 *with* a UTC offset, or Z
     "end":   "2026-05-28T09:45:00+12:00",
     "show_as": "busy",        free | tentative | busy | out_of_office | working_elsewhere
     "response": "accepted",   organizer | accepted | tentative | declined | not_responded | none
     "all_day": false,
     "cancelled": false,
     "attendees": ["Ana Client", "Ben Colleague"]}]}

Every field is present on every event. An appointment the user wrote themselves has no
response to give and is the adapter's to report as `organizer`. A recurring meeting is
expanded into the instance falling on the requested day. When the calendar cannot be read,
the adapter exits non-zero with the reason on stderr, and that reason is what this script
reports — a calendar that is on and unreadable is a loud failure, not a day with no
meetings.

Instants with offsets rather than local clocks, because the machine's zone and the
configured `TIMESHEET_TIMEZONE` need not agree: the adapter says *when*, and this script
decides which day and clock that is in the configured zone.

## What counts

An event counts when the user accepted or organised it — or tentatively accepted it, which
in Outlook sets both the response and the show-as to tentative, so a filter on the response
alone would drop exactly the half-committed meeting that is meant to be kept — its show-as
is busy or tentative, it is not all-day, not cancelled, and it *starts* on the requested day
in the configured zone. Nothing about the day skeleton is consulted: a meeting before the
laptop opened counts here, and the verdict below says what the activity source made of it.

## The verdict

The calendar says what was scheduled; the activity source says what the machine saw
(ADR-0008). Each event that counts is set against the day's window events, read from the
activity source over the same bounds the two reading scripts use, and is **corroborated**
when a *meeting window* intersects its span — a window whose title matches the skill's
meeting-title pattern (SKILL.md Step 3: `Meeting | …` or `Call with …`; a `Chat | …` window
is not a meeting). Meeting windows are read as the timeline reads them: heartbeats
collapsed, events under the noise floor dropped, and fragments of one meeting window under
the gap fold apart joined into one span — with the same two flags, `--noise-floor` and
`--gap-fold`, so a user who tuned the timeline's in `## Preferences` tunes this the same way.

A corroborated event carries the **evidence** — the span of meeting window seen, as seen,
so it may start before the event — and a proposed **block**: the event's span, extended to
the end of the evidence when that runs later. An overrun the machine saw is billed; time
after the scheduled end with no meeting window is not, whatever the AFK watcher made of it.
An uncorroborated event carries neither. Both verdicts are arithmetic here so the rules read
them and never re-derive them; what each verdict *means* for the day — a block drafted over
a break, a question under the table — is the rules' to say.

## Output

  {"date": "2026-05-28", "zone": "zone Pacific/Auckland",
   "events": [{"id", "subject", "start": "09:00:00", "end": "09:45:00",
               "show_as", "response", "attendees",
               "corroborated": true,
               "evidence": {"start": "09:03:00", "end": "09:52:00"},   null when not
               "block":    {"start": "09:00:00", "end": "09:52:00"}},  null when not
              ...]}

Clocks are the `HH:MM:SS` every other script here prints, in the configured zone, with the
`*` second-pass marker on the hour a fall-back repeats, so a calendar span can be set beside
a skeleton span — or handed to `--cover` — with neither converted. Sorted by start. Nothing
is written anywhere: a rescheduled meeting is read fresh on every run.

Failure is one `ERR …` line on stderr and a non-zero exit — never a traceback — with
nothing on stdout: 2 for a bad argument, 1 for the calendar being off, the activity source
unreachable or the adapter failing. The activity source is read *before* the adapter runs:
without it there is no verdict to give, and printing every event uncorroborated would turn
each calendar event into a question with nothing said about why — so it is refused the way
the two reading scripts refuse, and before an adapter that may take a while to start is
spawned.

No third-party deps — stdlib only, like the sibling modules.
"""
import argparse
import datetime as dt
import io
import json
import re
import subprocess
import sys
from pathlib import Path

import skill_config
from aw_client import GAP_FOLD, NOISE_FLOOR, SourceError, dedupe_heartbeats, parse_ts, window_day
from timezone import local_clock, resolve_zone, utc_bounds, zone_label

TOGGLE = "TIMESHEET_OUTLOOK_CALENDAR"

# The skill's meeting-title pattern — SKILL.md Step 3 names it in prose as the soft boundary
# a Teams meeting starts, and this is its one copy in code. A Teams window is titled
# `Meeting | <name> | …` or `Call with <name> | …` for a meeting or call, and `Chat | …` for a
# chat; only the first two are evidence that a meeting was attended.
MEETING_TITLE = re.compile(r"^\s*(Meeting \||Call with\b)", re.IGNORECASE)

# The adapter the toggle names. Beside this script rather than configured, because there
# is one, and a second calendar earns a toggle of its own rather than a path setting a user
# has to know the spelling of.
OUTLOOK_ADAPTER = Path(__file__).resolve().parent / "outlook_calendar.ps1"

# How long an adapter gets. Classic Outlook can take a while to start when it is not already
# running; a hung adapter must still not hang the run that asked.
ADAPTER_TIMEOUT_S = 120

EVENT_FIELDS = ("id", "subject", "start", "end", "show_as", "response", "all_day",
                "cancelled", "attendees")
COUNTED_SHOW_AS = frozenset({"busy", "tentative"})
COUNTED_RESPONSES = frozenset({"organizer", "accepted", "tentative"})


class CalendarError(Exception):
    """Why the calendar could not be read — one line, printed after `ERR`."""


# -- The contract, read ----------------------------------------------------------------

_FRACTION = re.compile(r"\.(\d+)")


def parse_instant(text) -> dt.datetime:
    """An adapter's ISO 8601 instant as an aware datetime.

    Wider than `datetime.fromisoformat` on the Python this skill supports (3.10), which
    takes exactly three or six fractional digits and no `Z`: PowerShell's `Get-Date
    -Format o` writes seven, and an adapter in another language may well write `Z`. Both
    are what a real adapter prints, so they are read here rather than made the adapter's
    problem.

    A naive instant is refused. It is a time in *some* zone — the machine's, usually — and
    nothing here can know which; assuming the configured zone would place a meeting an hour
    out on every machine whose clock is not set to the zone the user configured.
    """
    if not isinstance(text, str):
        raise CalendarError(f"an event's time is {text!r}, not an ISO 8601 string")
    s = text.strip()
    if s.endswith(("Z", "z")):
        s = s[:-1] + "+00:00"
    s = _FRACTION.sub(lambda m: "." + (m.group(1) + "000000")[:6], s, count=1)
    try:
        moment = dt.datetime.fromisoformat(s)
    except ValueError:
        raise CalendarError(f"an event's time {text!r} is not ISO 8601") from None
    if moment.utcoffset() is None:
        raise CalendarError(
            f"an event's time {text!r} carries no UTC offset, so the day it falls on in "
            f"the configured zone cannot be decided")
    return moment


def adapter_events(payload) -> list[dict]:
    """The adapter's events, or the reason they are not a calendar day.

    Every field is load-bearing downstream, so an event missing one is the adapter's bug
    and the reason names the field — not a `KeyError` from inside the filter.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        raise CalendarError(
            'the adapter did not print a calendar day: expected {"events": [...]}')
    events = payload["events"]
    for i, event in enumerate(events):
        if not isinstance(event, dict):
            raise CalendarError(f"event {i} is not an object")
        missing = [field for field in EVENT_FIELDS if field not in event]
        if missing:
            raise CalendarError(
                f"event {i} ({event.get('id', 'no id')!s}) lacks {', '.join(missing)}")
        if not isinstance(event["attendees"], list):
            raise CalendarError(f"event {event['id']!s}: attendees is not a list")
        # Real booleans, not whatever is truthy. An adapter that printed `"false"` as a
        # string would otherwise mark every event all-day and drop the whole calendar
        # without a word — the one shape of adapter bug the filter cannot see on its own.
        for field in ("all_day", "cancelled"):
            if not isinstance(event[field], bool):
                raise CalendarError(
                    f"event {event['id']!s}: {field} is {event[field]!r}, not true or false")
    return events


def _enum(event: dict, field: str) -> str:
    """One of the two enumerations, as compared: Outlook spells them `olBusy`, a
    hand-written adapter might print `Busy`. The contract is case-insensitive."""
    value = event[field]
    if not isinstance(value, str):
        raise CalendarError(f"event {event['id']!s}: {field} is {value!r}, not a string")
    return value.strip().lower()


def counted(event: dict) -> bool:
    """The filter, minus the day: committed to, shown as busy or tentative, timed, live."""
    return (not event["all_day"] and not event["cancelled"]
            and _enum(event, "show_as") in COUNTED_SHOW_AS
            and _enum(event, "response") in COUNTED_RESPONSES)


# -- The verdict -----------------------------------------------------------------------

Span = tuple[dt.datetime, dt.datetime]


def meeting_spans(window_events: list[dict], noise_floor: float = NOISE_FLOOR,
                  gap_fold: float = GAP_FOLD) -> list[Span]:
    """The spans of meeting window in a day's window events, as the timeline would read them.

    Heartbeats are collapsed first, so a re-emitted event is not a second meeting; events
    under the noise floor are dropped, so alt-tabbing through the Teams window is not
    attendance; and fragments of the *same* meeting window under the gap fold apart are one
    span, so an overrun the user watched while working in parallel still reads as one run
    of evidence. Fragments further apart than that are separate spans — reopening the
    meeting to read its chat five minutes after it ended is not the meeting running late.
    Same title, because two meetings back to back are two spans and the second must not
    lend its end to the first — and the last span *of that title*, so two meeting windows
    the user flicked between do not break each other's runs.
    """
    fold = dt.timedelta(seconds=gap_fold)
    spans: list[list] = []                      # [title, start, end], in order of first sight
    latest: dict[str, list] = {}                # title -> the span it last extended
    for e in dedupe_heartbeats(window_events):
        title = e["data"].get("title", "") or ""
        if e["duration"] < noise_floor or not MEETING_TITLE.search(title):
            continue
        start = parse_ts(e["timestamp"])
        end = start + dt.timedelta(seconds=e["duration"])
        run = latest.get(title)
        if run is not None and start - run[2] < fold:
            run[2] = max(run[2], end)
        else:
            run = [title, start, end]
            spans.append(run)
            latest[title] = run
    return sorted((s, e) for _, s, e in spans)


def verdict(start: dt.datetime, end: dt.datetime, spans: list[Span]) -> dict:
    """Whether a meeting window intersects `[start, end)`, and what follows if one does.

    Intersection is strict — a window that ended as the event began saw nothing of it, which
    is the back-to-back case where the previous meeting must not vouch for the next — and an
    event with no span of its own intersects nothing: a zero-length appointment is a
    reminder, and a window open at that instant is not attendance. The evidence is every
    intersecting span, first start to last end, reported as seen: it may begin before the
    event when the user joined early. The block is the event's own span extended at its
    *end* only, to the end of the evidence when that runs later. Its start is never moved,
    because the minutes before a scheduled start are ordinary active time the surrounding
    block already covers, and nothing here re-times what the calendar said.
    """
    seen = [(s, e) for s, e in spans if e > start and s < end] if end > start else []
    if not seen:
        return {"corroborated": False, "evidence": None, "block": None}
    evidence = (min(s for s, _ in seen), max(e for _, e in seen))
    return {"corroborated": True, "evidence": evidence,
            "block": (start, max(end, evidence[1]))}


def _clocks(span: Span | None, zone) -> dict | None:
    return None if span is None else {"start": local_clock(span[0], zone),
                                      "end": local_clock(span[1], zone)}


def filtered_day(payload, local_date: dt.date, zone, window_events: list[dict],
                 noise_floor: float = NOISE_FLOOR, gap_fold: float = GAP_FOLD) -> dict:
    """The calendar day the rules read: what counts, on `local_date` in `zone`, sorted, each
    event with its verdict against `window_events` — the day's foreground-window events from
    the activity source, read with the timeline's two noise settings.

    An event is placed by where it *starts*, as a calendar shows it, so one that runs over
    midnight belongs to the day it began on. An event that ends before it starts is the
    adapter's bug and is refused by name, like a missing field: a reversed span would
    otherwise be silently uncorroborated. Every clock — the event's, the evidence's, the
    block's — is rendered by `timezone.local_clock`, so the second pass over a repeated hour
    carries its marker wherever it falls.
    """
    spans = meeting_spans(window_events, noise_floor, gap_fold)
    kept: list[tuple[dt.datetime, dict]] = []
    for event in adapter_events(payload):
        if not counted(event):
            continue
        start = parse_instant(event["start"])
        if start.astimezone(zone).date() != local_date:
            continue
        end = parse_instant(event["end"])
        if end < start:
            raise CalendarError(
                f"event {event['id']!s} ends ({event['end']}) before it starts ({event['start']})")
        judged = verdict(start, end, spans)
        kept.append((start, {
            "id": event["id"],
            "subject": event["subject"],
            "start": local_clock(start, zone),
            "end": local_clock(end, zone),
            "show_as": _enum(event, "show_as"),
            "response": _enum(event, "response"),
            "attendees": event["attendees"],
            "corroborated": judged["corroborated"],
            "evidence": _clocks(judged["evidence"], zone),
            "block": _clocks(judged["block"], zone),
        }))
    kept.sort(key=lambda pair: pair[0])
    return {"date": local_date.isoformat(), "zone": zone_label(zone),
            "events": [rendered for _, rendered in kept]}


def day_window_events(local_date: dt.date, zone) -> list[dict]:
    """The day's foreground-window events from the activity source, or the reason not.

    The same bounds `activity_timeline` reads the day over, so the meeting window that
    corroborates an event here is the one the timeline shows — and the same fetch, with the
    same two refusals, from the shared client: unreachable, and a missing window bucket,
    which would otherwise read as a day on which nothing on the calendar was attended rather
    than a day the instrument did not see. Evidence is read to local midnight, so a calendar
    event that runs over midnight has its overrun judged only up to there.
    """
    start_utc, end_utc = utc_bounds(local_date, zone)
    try:
        _, _, events = window_day(start_utc, end_utc, "nothing can corroborate a calendar event")
    except SourceError as exc:
        raise CalendarError(str(exc)) from None
    return events


# -- The adapter, run ------------------------------------------------------------------

def adapter_argv(path: Path, local_date: dt.date) -> list[str]:
    """How an adapter at `path` is invoked for `local_date`.

    A `.ps1` runs under Windows PowerShell — `powershell`, not `pwsh`, because the Outlook
    adapter has to parse under the 5.1 a stock Windows box has and that is what holds it
    to it. A `.py` runs under the interpreter running this script, so a fake written for
    the suite runs wherever the suite does. Anything else is taken to be executable.
    """
    date = local_date.isoformat()
    suffix = path.suffix.lower()
    if suffix == ".ps1":
        return ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                "-File", str(path), date]
    if suffix == ".py":
        return [sys.executable, str(path), date]
    return [str(path), date]


def resolve_adapter(flag: str | None) -> Path:
    """Which adapter runs, or the reason none can.

    The toggle is checked first and whatever `--adapter` says: the flag chooses *which*
    adapter, and the toggle whether the calendar is read at all, so a fake handed to a
    machine with the calendar off is refused like the real one would be.

    The off message carries `note_for_an_unreached_shell()`, for the hazard particular to
    a toggle. A required setting that never arrives fails loudly; a toggle that never
    arrives reads as *off*, which is a legitimate state — so on a machine where it was
    turned on, the skill would quietly run without the calendar and nothing would say why.
    """
    if not skill_config.enabled(TOGGLE):
        raise CalendarError(
            f"the calendar is off: {TOGGLE} is not set to true. Turn it on in "
            f"/plugin configure billables, or on the {TOGGLE}= line of the skill's .env"
            + skill_config.note_for_an_unreached_shell())
    if skill_config.has_value(flag):
        chosen = Path(flag).expanduser()
        if not chosen.is_file():
            raise CalendarError(f"the calendar adapter {chosen} is not there")
        return chosen
    if sys.platform != "win32":
        raise CalendarError(
            f"the calendar stays off: the only adapter reads classic Outlook through its "
            f"object model, which exists on Windows alone. Leave {TOGGLE} off here")
    if not OUTLOOK_ADAPTER.is_file():
        raise CalendarError(
            f"the calendar adapter {OUTLOOK_ADAPTER} is not there: this copy of the skill "
            f"does not ship it, so the calendar cannot be read")
    return OUTLOOK_ADAPTER


def read_adapter(argv: list[str]) -> object:
    """Run an adapter and hand back what it printed, parsed — or the reason it did not.

    Judged by exit code first: a non-zero exit means the calendar could not be read, and
    the first line the adapter gave for it is the reason the user needs. Only then is the
    output parsed, and output that is not the JSON document is named as the adapter's
    fault rather than passed on as a decode error. Read as UTF-8 by contract; a stray
    byte-order mark is tolerated because Windows PowerShell is fond of writing one.
    """
    try:
        run = subprocess.run(argv, capture_output=True, encoding="utf-8", errors="replace",
                             timeout=ADAPTER_TIMEOUT_S)
    except OSError as exc:
        raise CalendarError(f"the calendar adapter could not start ({argv[0]}): {exc}") from None
    except subprocess.TimeoutExpired:
        raise CalendarError(
            f"the calendar adapter did not answer within {ADAPTER_TIMEOUT_S} s") from None
    if run.returncode != 0:
        said = [line.strip() for line in (run.stderr + "\n" + run.stdout).splitlines()
                if line.strip()]
        reason = said[0] if said else "it gave no reason"
        raise CalendarError(f"the calendar adapter failed (exit {run.returncode}): {reason}")
    text = run.stdout.lstrip("﻿").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        head = text[:80].replace("\n", "\\n")
        raise CalendarError(
            f"the calendar adapter printed something other than the calendar day "
            f"({exc.msg} at line {exc.lineno}): {head!r}") from None


# -- The command -----------------------------------------------------------------------

def main():
    # The script's own streams only: it spawns an adapter, but reads that as UTF-8 by
    # contract rather than by setting the child's `PYTHONIOENCODING`, so there is no
    # reason to reach for `harvest_client.use_utf8()` from a script that never bills. In
    # `main()` rather than at module scope because an import must have no side effect
    # (issue #21); a captured or redirected stream is not a TextIOWrapper and is skipped.
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(
        description="One day's calendar events, filtered to what counts, as JSON.")
    ap.add_argument("date", help="YYYY-MM-DD (local date)")
    ap.add_argument("--utc-offset", type=float, default=None,
                    help="Local zone offset from UTC in hours, for this run only. "
                         "Omit to use the configured TIMESHEET_TIMEZONE.")
    ap.add_argument("--noise-floor", type=float, default=NOISE_FLOOR,
                    help=f"Ignore meeting windows shorter than this many seconds, as the "
                         f"timeline does (default {NOISE_FLOOR})")
    ap.add_argument("--gap-fold", type=float, default=GAP_FOLD,
                    help=f"Fragments of one meeting window this many seconds apart or less "
                         f"are one run of evidence, as the timeline does (default {GAP_FOLD})")
    ap.add_argument("--adapter", default=None,
                    help="Path of an adapter to run instead of the configured one; it is "
                         "handed the date and must print the contract in this script's "
                         "docstring. The calendar toggle still has to be on.")
    args = ap.parse_args()

    try:
        local_date = dt.datetime.strptime(args.date, "%Y-%m-%d").date()
    except ValueError:
        print(f"ERR bad date '{args.date}', expected YYYY-MM-DD", file=sys.stderr)
        return 2

    try:
        adapter = resolve_adapter(args.adapter)
        # After the toggle: a user with the calendar off should be told that, not asked
        # for a zone the read they did not want would have needed.
        zone = resolve_zone(args.utc_offset)
        # The activity source before the adapter — see the module docstring, "Output".
        window_events = day_window_events(local_date, zone)
        payload = read_adapter(adapter_argv(adapter, local_date))
        result = filtered_day(payload, local_date, zone, window_events,
                              noise_floor=args.noise_floor, gap_fold=args.gap_fold)
    except CalendarError as exc:
        print(f"ERR {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

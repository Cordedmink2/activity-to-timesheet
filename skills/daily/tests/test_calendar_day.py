"""The calendar wrapper: one day's calendar events, filtered, in one JSON shape.

`calendar_day.py` owns the contract between the `daily` skill and whichever adapter read the
user's calendar (#50, ADR-0008). An adapter is any command that prints the raw calendar day
for a date; the wrapper decides which one runs, runs it, drops what does not count, and prints
the result. The rules downstream never learn which adapter ran, so everything they will read
is pinned here — against plain data, with no Outlook, no network and no model.

Two layers, deliberately. The filter is tested by importing the functions and handing them
adapter output as a Python object, the way the skeleton and timeline tests import theirs.
The contract is tested at process level: a fake adapter is a real script the wrapper spawns,
so the argv it is given, the encoding it is read in and the exit code it is judged by are
the real ones. The wrapper itself runs in-process through `run_cli`, like every other
script here — see `README.md` § "Never invoke a script with `subprocess`".
"""
from __future__ import annotations

import datetime as dt
import sys
import textwrap
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import calendar_day as cd
import skill_config
from support import run_cli

MAY = dt.date(2026, 5, 28)
AUCKLAND = ZoneInfo("Pacific/Auckland")      # UTC+12 in May, UTC+13 in summer
LONDON = ZoneInfo("Europe/London")           # UTC+1 in May
TOGGLE = "TIMESHEET_OUTLOOK_CALENDAR"


def event(begins: str, ends: str, **overrides) -> dict:
    """One raw adapter event on 2026-05-28, written in Auckland's May offset (+12:00).

    `begins` and `ends` are local `HH:MM`; anything else is an override of the field the
    adapter would have printed — including `start=` / `end=` as full instants, for a test
    about the day boundary. The defaults are the event that counts — accepted, busy, timed,
    not cancelled — so a test names only what it changes.
    """
    raw = {
        "id": f"evt-{begins}",
        "subject": "Sprint review",
        "start": f"2026-05-28T{begins}:00+12:00",
        "end": f"2026-05-28T{ends}:00+12:00",
        "show_as": "busy",
        "response": "accepted",
        "all_day": False,
        "cancelled": False,
        "attendees": ["Ana Client", "Ben Colleague"],
    }
    raw.update(overrides)
    return raw


def kept(*events: dict, local_date: dt.date = MAY, zone=AUCKLAND) -> list[str]:
    """The ids the filter keeps, in the order the wrapper prints them."""
    return [e["id"] for e in cd.filtered_day({"events": list(events)}, local_date, zone)["events"]]


# --------------------------------------------------------------------------------------
# The filter: which events count
# --------------------------------------------------------------------------------------

def test_a_declined_event_is_dropped():
    """A declined invite is on the calendar and was not attended. Listed, it would become a
    question every time; drafted, it would bill a meeting the user said no to."""
    assert kept(event("09:00", "09:30", response="declined")) == []


def test_an_all_day_event_is_dropped():
    """Birthdays, public holidays, "in the office" — none is a span anyone worked."""
    assert kept(event("00:00", "23:59", all_day=True)) == []


def test_a_cancelled_event_is_dropped():
    """Outlook keeps a cancelled meeting on the calendar until the user removes it."""
    assert kept(event("09:00", "09:30", cancelled=True)) == []


@pytest.mark.parametrize("show_as,counts", [
    ("busy", True), ("tentative", True),
    ("free", False), ("out_of_office", False), ("working_elsewhere", False),
])
def test_only_busy_and_tentative_count(show_as, counts):
    """Show-as is how the user marks a hold as not really a commitment. `free` is a reminder
    or a focus block; out of office is the opposite of billable."""
    assert bool(kept(event("09:00", "09:30", show_as=show_as))) is counts


@pytest.mark.parametrize("response,counts", [
    ("organizer", True), ("accepted", True), ("tentative", True),
    ("declined", False), ("not_responded", False), ("none", False),
])
def test_only_a_meeting_the_user_committed_to_counts(response, counts):
    """Accepted or organised, per the spec — and tentatively accepted, which is what
    "tentative meetings are included" (#49, story 13) means in Outlook: tentatively
    accepting sets *both* the response and the show-as to tentative, so a filter on the
    response alone would drop exactly the half-committed meeting the story keeps. An invite
    never answered is not a commitment. `none` is a meeting with no response to give; an
    appointment the user wrote themselves is the adapter's to report as `organizer`."""
    assert bool(kept(event("09:00", "09:30", response=response))) is counts


def test_case_and_whitespace_in_the_two_enumerations_do_not_matter():
    """Outlook's enumerations are spelled `olBusy`; a hand-written adapter might print
    `Busy`. The contract is case-insensitive rather than a spelling test."""
    assert kept(event("09:00", "09:30", show_as=" Busy ", response="Accepted")) == ["evt-09:00"]


def test_tentative_is_kept_however_it_arrives():
    """The AC's own words: Tentative is kept."""
    assert kept(event("09:00", "09:30", show_as="tentative", response="tentative")) == ["evt-09:00"]


def test_an_event_before_the_days_activity_starts_is_kept():
    """A client-site meeting at 07:30, before the laptop opened. The skeleton has no idea
    it happened, and the wrapper is not asked about the skeleton at all: events from the
    whole calendar day are considered (#49, story 14), and whether one is corroborated is a
    later question (#52)."""
    assert kept(event("07:30", "08:30")) == ["evt-07:30"]


def test_the_day_is_the_configured_zones_day_not_the_instants():
    """The timezone boundary. The same three instants land on different local days in
    Auckland and London, so which of them is "on the 28th" depends on the configured zone
    and on nothing else — not on the offset the adapter happened to print them with."""
    late_27th = event("23:30", "23:59", id="late-27th",
                      start="2026-05-27T23:30:00+12:00", end="2026-05-27T23:59:00+12:00")
    early_28th = event("00:15", "01:00", id="early-28th",
                       start="2026-05-27T12:15:00Z", end="2026-05-27T13:00:00Z")   # 00:15 NZST
    late_28th = event("23:30", "23:59", id="late-28th",
                      start="2026-05-28T11:30:00Z", end="2026-05-28T11:59:00Z")    # 23:30 NZST
    events = (late_27th, early_28th, late_28th)
    assert kept(*events, zone=AUCKLAND) == ["early-28th", "late-28th"]
    # In London those same instants are 12:30 on the 27th, 13:15 on the 27th, 12:30 on the 28th.
    assert kept(*events, zone=LONDON) == ["late-28th"]


def test_an_event_is_placed_by_where_it_starts():
    """A meeting that runs over midnight is the day it began on, as a calendar shows it."""
    overnight = event("23:30", "00:30", id="overnight",
                      start="2026-05-28T23:30:00+12:00", end="2026-05-29T00:30:00+12:00")
    assert kept(overnight) == ["overnight"]
    assert kept(overnight, local_date=dt.date(2026, 5, 29)) == []


# --------------------------------------------------------------------------------------
# The shape: what the rules will read
# --------------------------------------------------------------------------------------

def test_the_output_is_local_clocks_sorted_by_start_with_the_fields_the_rules_read():
    """Times come out as the `HH:MM:SS` every other script in this skill prints, in the
    configured zone, so a calendar span can be set beside a skeleton span without either
    being converted. The two flags the filter consumed are gone — everything printed passed
    them — and the adapter's identifier is kept, because the drill-down (#55) will name it."""
    out = cd.filtered_day(
        {"events": [event("14:00", "14:30", id="later"), event("09:00", "09:45", id="earlier")]},
        MAY, AUCKLAND)
    assert out["date"] == "2026-05-28"
    assert out["zone"] == "zone Pacific/Auckland"
    assert [e["id"] for e in out["events"]] == ["earlier", "later"]
    first = out["events"][0]
    assert set(first) == {"id", "subject", "start", "end", "show_as", "response", "attendees"}
    assert (first["start"], first["end"]) == ("09:00:00", "09:45:00")
    assert first["show_as"] == "busy" and first["response"] == "accepted"
    assert first["attendees"] == ["Ana Client", "Ben Colleague"]


def test_the_second_pass_over_a_repeated_hour_carries_the_marker():
    """`Pacific/Auckland` goes back at 03:00 on 2026-04-05, so 02:00-03:00 happens twice.
    A meeting in the second pass renders with the `*` the skeleton and timeline use for
    it, or a span lifted from here into `--window` would name the wrong hour."""
    fallback = dt.date(2026, 4, 5)
    second_pass = event("02:30", "02:50", id="second",
                        start="2026-04-05T02:30:00+12:00", end="2026-04-05T02:50:00+12:00")
    first_pass = event("02:30", "02:50", id="first",
                       start="2026-04-05T02:30:00+13:00", end="2026-04-05T02:50:00+13:00")
    out = cd.filtered_day({"events": [second_pass, first_pass]}, fallback, AUCKLAND)
    assert [(e["id"], e["start"]) for e in out["events"]] == [
        ("first", "02:30:00"), ("second", "02:30:00*")]


def test_the_instant_format_powershell_prints_is_read():
    """`Get-Date -Format o` writes seven fractional digits; Python 3.10's `fromisoformat`
    takes three or six and refuses `Z`. Both shapes are what an adapter will actually print,
    so the wrapper reads them rather than asking the adapter to know Python's limits."""
    assert cd.parse_instant("2026-05-28T09:00:00.1234567+12:00") == \
        dt.datetime(2026, 5, 28, 9, 0, 0, 123456, tzinfo=dt.timezone(dt.timedelta(hours=12)))
    assert cd.parse_instant("2026-05-27T21:00:00Z") == \
        dt.datetime(2026, 5, 27, 21, 0, tzinfo=dt.timezone.utc)


def test_an_instant_with_no_offset_is_refused():
    """A naive time is a time in *some* zone — the machine's, usually — and the wrapper
    cannot know which. Guessing the configured one would place a meeting an hour out on
    every machine whose clock is not set to the zone the user configured."""
    with pytest.raises(cd.CalendarError, match="offset"):
        cd.parse_instant("2026-05-28T09:00:00")


@pytest.mark.parametrize("missing", ["id", "subject", "start", "end", "show_as", "response",
                                     "all_day", "cancelled", "attendees"])
def test_an_event_missing_a_field_is_a_reason_naming_the_field(missing):
    """Every field is load-bearing, so an adapter that leaves one out is broken, and the
    reason has to say which — not a `KeyError` from inside the filter."""
    raw = event("09:00", "09:30")
    del raw[missing]
    with pytest.raises(cd.CalendarError, match=missing):
        cd.filtered_day({"events": [raw]}, MAY, AUCKLAND)


@pytest.mark.parametrize("field", ["all_day", "cancelled"])
def test_a_flag_that_is_not_a_boolean_is_refused_rather_than_read_as_true(field):
    """`"false"` is a non-empty string, and a filter on truthiness would read it as *true*:
    every event all-day, the whole calendar dropped, nothing said. The one adapter bug the
    filter could not otherwise see, so the contract insists on real booleans."""
    with pytest.raises(cd.CalendarError, match=field):
        cd.filtered_day({"events": [event("09:00", "09:30", **{field: "false"})]}, MAY, AUCKLAND)


@pytest.mark.parametrize("payload", [[], {"items": []}, {"events": "none"}, "a string", None],
                         ids=["list", "wrong-key", "events-not-a-list", "string", "null"])
def test_adapter_output_that_is_not_a_calendar_day_is_a_reason(payload):
    with pytest.raises(cd.CalendarError):
        cd.filtered_day(payload, MAY, AUCKLAND)


# --------------------------------------------------------------------------------------
# The adapter command
# --------------------------------------------------------------------------------------

def test_a_powershell_adapter_is_run_by_windows_powershell_with_the_date_last(tmp_path):
    """The Outlook adapter (#51) is a `.ps1` that has to parse under Windows PowerShell
    5.1, so that is what runs it: not `pwsh`, which a stock Windows box does not have."""
    argv = cd.adapter_argv(tmp_path / "outlook_calendar.ps1", MAY)
    assert argv[0] == "powershell"
    assert "-File" in argv and argv[argv.index("-File") + 1] == str(tmp_path / "outlook_calendar.ps1")
    assert "-NoProfile" in argv and "-NonInteractive" in argv
    assert argv[-1] == "2026-05-28"


def test_a_python_adapter_is_run_by_the_interpreter_running_the_wrapper(tmp_path):
    """The seam a test supplies a fake through. The same interpreter, so a fake written
    for this suite runs wherever the suite does, Store stub or no Store stub."""
    assert cd.adapter_argv(tmp_path / "fake.py", MAY) == \
        [sys.executable, str(tmp_path / "fake.py"), "2026-05-28"]


def test_any_other_adapter_is_run_as_it_is(tmp_path):
    assert cd.adapter_argv(tmp_path / "calendar", MAY) == [str(tmp_path / "calendar"), "2026-05-28"]


# --------------------------------------------------------------------------------------
# Process level: the wrapper, a real fake adapter, and the two ways it refuses
# --------------------------------------------------------------------------------------

CANNED = {"events": [
    event("09:00", "09:45", id="standup", subject="Standup — ACME"),
    event("11:00", "11:30", id="declined", response="declined"),
    event("13:00", "13:30", id="tentative", show_as="tentative", response="tentative",
          subject="Māori language week planning"),
]}


@pytest.fixture
def fake_adapter(tmp_path):
    """Write an adapter script that prints `payload` (or `text`, verbatim) and exits
    `code`. It checks its own argv, so the wrapper's side of the contract — one date,
    last — is asserted by the adapter rather than trusted."""
    def _write(payload=None, *, text: str | None = None, code: int = 0,
               stderr: str = "") -> Path:
        script = tmp_path / "fake_adapter.py"
        body = (f"print({text!r}, end='')" if text is not None
                else f"import json; print(json.dumps({payload!r}, ensure_ascii=False))")
        script.write_text(textwrap.dedent(f"""
            import sys
            sys.stdout.reconfigure(encoding="utf-8")
            if sys.argv[1:] != [{MAY.isoformat()!r}]:
                sys.exit(f"the adapter was handed {{sys.argv[1:]}} rather than one date")
            sys.stderr.write({stderr!r})
            if {code}:
                sys.exit({code})
            {body}
            """), encoding="utf-8")
        return script
    return _write


@pytest.fixture
def calendar_on(monkeypatch):
    monkeypatch.setenv(TOGGLE, "true")


def test_the_wrapper_prints_the_contract_for_a_date_through_an_adapter_it_is_given(
        fake_adapter, calendar_on):
    """The whole path, end to end: configuration on, an adapter spawned as a real process,
    its stdout read as UTF-8, the filter applied, one JSON document printed and nothing on
    stderr. The zone is the hermetic fixture's `Etc/GMT-12`, which is UTC+12 like the
    events, so the clocks come out as written."""
    r = run_cli(cd, [MAY.isoformat(), "--adapter", str(fake_adapter(CANNED))])
    assert r.code == 0, r.err
    assert r.err == ""
    assert r.json() == {
        "date": "2026-05-28",
        "zone": "zone Etc/GMT-12",
        "events": [
            {"id": "standup", "subject": "Standup — ACME", "start": "09:00:00",
             "end": "09:45:00", "show_as": "busy", "response": "accepted",
             "attendees": ["Ana Client", "Ben Colleague"]},
            {"id": "tentative", "subject": "Māori language week planning", "start": "13:00:00",
             "end": "13:30:00", "show_as": "tentative", "response": "tentative",
             "attendees": ["Ana Client", "Ben Colleague"]},
        ],
    }


def test_a_per_run_offset_dates_the_day_like_the_other_reading_scripts(fake_adapter,
                                                                       calendar_on):
    """`--utc-offset` is the escape hatch `afk_blocks` and `activity_timeline` offer, and a
    calendar read for the same day has to date it the same way or the two disagree about
    which events are on it."""
    r = run_cli(cd, [MAY.isoformat(), "--adapter", str(fake_adapter(CANNED)), "--utc-offset", "-2"])
    assert r.code == 0, r.err
    out = r.json()
    assert out["zone"] == "offset UTC-2"
    # 09:00+12:00 is 21:00Z on the 27th and 13:00+12:00 is 01:00Z on the 28th; at UTC-2
    # those are 19:00 and 23:00 on the 27th, so nothing in CANNED is on the 28th.
    assert out["events"] == []


def test_the_calendar_off_is_a_one_line_reason_and_nothing_else():
    """Toggle unset — the hermetic fixture clears it — is today's behaviour exactly, and
    the wrapper says so rather than printing an empty day a caller could mistake for a
    quiet one. The reason names the key, because that is what the user has to set."""
    r = run_cli(cd, [MAY.isoformat()])
    assert r.code != 0
    assert r.out == ""
    assert r.err.count("\n") == 1 and r.err.startswith("ERR"), r.err
    assert TOGGLE in r.err and "off" in r.err


@pytest.mark.parametrize("spelling", ["false", "yes", "1", "on"])
def test_anything_but_true_leaves_the_calendar_off(monkeypatch, fake_adapter, spelling):
    """The harness injects a boolean option as the string `true` or `false` — read out of
    the CLI: `String(value)` — and a hand-edited `.env` may say anything. Only one spelling
    is on, and the adapter it is given is not run for any other."""
    monkeypatch.setenv(TOGGLE, spelling)
    r = run_cli(cd, [MAY.isoformat(), "--adapter", str(fake_adapter(CANNED))])
    assert r.code != 0 and r.out == "" and TOGGLE in r.err


def test_the_off_message_names_the_shell_when_the_configuration_never_reached_it(
        monkeypatch, tmp_path):
    """The hazard particular to a toggle. A required setting that does not arrive fails
    loudly; a toggle that does not arrive reads as *off*, which is a legitimate state, and
    the daily skill would then quietly run without the calendar on a machine where it was
    turned on. So the off message carries the same cause the missing-setting messages do,
    under the same conditions: a plugin install, in a session, with no published marker."""
    (tmp_path / ".claude-plugin").mkdir()
    monkeypatch.setattr(skill_config, "SKILL_ROOT", tmp_path / "skills" / "daily")
    monkeypatch.setattr(skill_config.sys, "platform", "win32")
    monkeypatch.setenv(skill_config.IN_A_SESSION, "1")
    monkeypatch.delenv(skill_config.PUBLISHED_MARK, raising=False)
    r = run_cli(cd, [MAY.isoformat()])
    assert r.code != 0
    assert "Bash tool" in r.err, r.err


def test_an_adapter_that_fails_exits_non_zero_with_its_reason_and_nothing_else(
        fake_adapter, calendar_on):
    """Story 28: Outlook not reachable is a loud failure, not a day with no meetings. The
    adapter's own reason is what the user needs to read, so it is carried through."""
    r = run_cli(cd, [MAY.isoformat(), "--adapter",
                     str(fake_adapter(None, code=3, stderr="Outlook is not running\n"))])
    assert r.code != 0
    assert r.out == ""
    assert r.err.startswith("ERR") and "Outlook is not running" in r.err
    assert "Traceback" not in r.err


def test_an_adapter_that_prints_something_other_than_the_contract_is_refused(
        fake_adapter, calendar_on):
    """A PowerShell warning on stdout, a progress line, a BOM — anything that is not the
    JSON document is the adapter's bug, and the wrapper names it as that rather than
    handing the model a `JSONDecodeError`."""
    r = run_cli(cd, [MAY.isoformat(), "--adapter",
                     str(fake_adapter(text="WARNING: Outlook took a while\n{\"events\": []}"))])
    assert r.code != 0 and r.out == ""
    assert "adapter" in r.err and "Traceback" not in r.err


def test_an_adapter_event_missing_a_field_is_the_adapters_fault_at_process_level(
        fake_adapter, calendar_on):
    broken = {"events": [{k: v for k, v in event("09:00", "09:30").items() if k != "show_as"}]}
    r = run_cli(cd, [MAY.isoformat(), "--adapter", str(fake_adapter(broken))])
    assert r.code != 0 and r.out == ""
    assert "show_as" in r.err and "Traceback" not in r.err


def test_the_toggle_on_a_platform_with_no_outlook_says_the_calendar_stays_off(
        monkeypatch, calendar_on):
    """Story 26. macOS and Linux have no classic Outlook and so no adapter; the toggle is on
    and nothing can honour it. Named, not mysterious."""
    monkeypatch.setattr(cd.sys, "platform", "linux")
    r = run_cli(cd, [MAY.isoformat()])
    assert r.code != 0 and r.out == ""
    assert "Windows" in r.err and "Outlook" in r.err


def test_the_toggle_on_with_no_adapter_shipped_names_the_adapter(monkeypatch, tmp_path,
                                                                 calendar_on):
    """The configured adapter is a file beside this script. Until #51 ships it — or if a
    copy loses it — the wrapper says which file it wanted, rather than a spawn error naming
    `powershell`. The path is relocated so this stays true after #51 lands."""
    monkeypatch.setattr(cd.sys, "platform", "win32")
    monkeypatch.setattr(cd, "OUTLOOK_ADAPTER", tmp_path / "outlook_calendar.ps1")
    r = run_cli(cd, [MAY.isoformat()])
    assert r.code != 0 and r.out == ""
    assert "outlook_calendar.ps1" in r.err


def test_a_malformed_date_is_a_usage_error_before_anything_else(calendar_on):
    r = run_cli(cd, ["28-05-2026"])
    assert r.code == 2
    assert "expected YYYY-MM-DD" in r.err


def test_nothing_is_written_anywhere(fake_adapter, calendar_on, workspace, monkeypatch,
                                     tmp_path):
    """Story 17: nothing from the calendar is cached. A rescheduled meeting is read fresh
    on every run, and there is no file for a stale one to hide in. The workspace fixture
    resolves, so the wrapper has somewhere it *could* write and does not."""
    monkeypatch.chdir(tmp_path)
    script = fake_adapter(CANNED)
    before = {p for p in tmp_path.rglob("*")}
    r = run_cli(cd, [MAY.isoformat(), "--adapter", str(script)])
    assert r.code == 0, r.err
    after = {p for p in tmp_path.rglob("*")}
    written = {p for p in after - before if "__pycache__" not in p.parts}
    assert not written, f"the wrapper left files behind: {sorted(written)}"
    assert workspace.is_dir()

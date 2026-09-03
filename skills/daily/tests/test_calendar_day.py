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
from support import Day, aw_server, day, run_cli, with_heartbeats

MAY = dt.date(2026, 5, 28)
AUCKLAND = ZoneInfo("Pacific/Auckland")      # UTC+12 in May, UTC+13 in summer
LONDON = ZoneInfo("Europe/London")           # UTC+1 in May
TOGGLE = "TIMESHEET_OUTLOOK_CALENDAR"

# What the window watcher records for a Teams meeting, a Teams call and a Teams chat. The
# skill's meeting-title pattern (SKILL.md Step 3, soft boundaries) is what tells them apart.
TEAMS = "ms-teams.exe"
MEETING = "Meeting | Sprint review | Northwind | user@example.com | Microsoft Teams"
CALL = "Call with Ana Client | Northwind | user@example.com | Microsoft Teams"
CHAT = "Chat | Ana Client | Northwind | user@example.com | Microsoft Teams"


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
    """The ids the filter keeps, in the order the wrapper prints them. No window events:
    the filter does not consult them, and a day with none is what a filter test wants."""
    return [e["id"] for e in cd.filtered_day({"events": list(events)}, local_date, zone,
                                             [])["events"]]


def verdict_of(raw: dict, d: Day) -> tuple[bool, dict | None, dict | None]:
    """`(corroborated, evidence, block)` for one raw event set against `d`'s window events,
    the spans as the `{"start", "end"}` clock pairs the rules will read."""
    out = cd.filtered_day({"events": [raw]}, d.date, AUCKLAND, d.window_events())["events"]
    assert len(out) == 1, out
    return out[0]["corroborated"], out[0]["evidence"], out[0]["block"]


def span(start: str, end: str) -> dict:
    return {"start": f"{start}:00", "end": f"{end}:00"}


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
        MAY, AUCKLAND, [])
    assert out["date"] == "2026-05-28"
    assert out["zone"] == "zone Pacific/Auckland"
    assert [e["id"] for e in out["events"]] == ["earlier", "later"]
    first = out["events"][0]
    assert set(first) == {"id", "subject", "start", "end", "show_as", "response", "attendees",
                          "corroborated", "evidence", "block"}
    assert (first["start"], first["end"]) == ("09:00:00", "09:45:00")
    assert first["show_as"] == "busy" and first["response"] == "accepted"
    assert first["attendees"] == ["Ana Client", "Ben Colleague"]
    # No window events were handed in, so the verdict on both is the uncorroborated one.
    assert all(e["corroborated"] is False and e["evidence"] is None and e["block"] is None
               for e in out["events"])


def test_the_second_pass_over_a_repeated_hour_carries_the_marker():
    """`Pacific/Auckland` goes back at 03:00 on 2026-04-05, so 02:00-03:00 happens twice.
    A meeting in the second pass renders with the `*` the skeleton and timeline use for
    it, or a span lifted from here into `--window` would name the wrong hour."""
    fallback = dt.date(2026, 4, 5)
    second_pass = event("02:30", "02:50", id="second",
                        start="2026-04-05T02:30:00+12:00", end="2026-04-05T02:50:00+12:00")
    first_pass = event("02:30", "02:50", id="first",
                       start="2026-04-05T02:30:00+13:00", end="2026-04-05T02:50:00+13:00")
    out = cd.filtered_day({"events": [second_pass, first_pass]}, fallback, AUCKLAND, [])
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
        cd.filtered_day({"events": [raw]}, MAY, AUCKLAND, [])


@pytest.mark.parametrize("field", ["all_day", "cancelled"])
def test_a_flag_that_is_not_a_boolean_is_refused_rather_than_read_as_true(field):
    """`"false"` is a non-empty string, and a filter on truthiness would read it as *true*:
    every event all-day, the whole calendar dropped, nothing said. The one adapter bug the
    filter could not otherwise see, so the contract insists on real booleans."""
    with pytest.raises(cd.CalendarError, match=field):
        cd.filtered_day({"events": [event("09:00", "09:30", **{field: "false"})]}, MAY, AUCKLAND,
                        [])


@pytest.mark.parametrize("payload", [[], {"items": []}, {"events": "none"}, "a string", None],
                         ids=["list", "wrong-key", "events-not-a-list", "string", "null"])
def test_adapter_output_that_is_not_a_calendar_day_is_a_reason(payload):
    with pytest.raises(cd.CalendarError):
        cd.filtered_day(payload, MAY, AUCKLAND, [])


# --------------------------------------------------------------------------------------
# The verdict: is a calendar event backed by a meeting window? (#52)
# --------------------------------------------------------------------------------------
#
# The calendar says what was scheduled; the activity source says what the machine saw
# (ADR-0008). The wrapper sets each event against the day's window events and looks for a
# meeting window — a title matching the skill's meeting-title pattern — whose span intersects
# the event's. The skeleton is never consulted: the AFK calls in these days are narrative,
# there to show the verdict does not move when the user goes quiet.

def test_a_listening_only_meeting_is_corroborated_and_its_block_spans_the_event():
    """The case #49 was raised for. Forty-five minutes in a Teams meeting, camera off, the
    keyboard untouched after the first twenty: the AFK watcher records a break, and the
    skeleton will say so. But the meeting window is in the activity data, inside the event,
    so the event is corroborated and its block is the event — start to scheduled end."""
    d = day().active("09:00", "09:20").afk("09:20", "09:45")
    d.window("09:03", "09:20", TEAMS, MEETING)
    assert verdict_of(event("09:00", "09:45"), d) == (True, span("09:03", "09:20"),
                                                     span("09:00", "09:45"))


def test_a_meeting_that_ran_over_extends_the_block_to_the_end_of_the_evidence():
    """Story 2. The window ran twenty-five minutes past the scheduled end, so the overrun
    was attended and is billed: the block ends where the evidence does."""
    d = day().active("09:00", "10:10")
    d.window("09:05", "10:10", TEAMS, MEETING)
    assert verdict_of(event("09:00", "09:45"), d) == (True, span("09:05", "10:10"),
                                                     span("09:00", "10:10"))


def test_afk_after_the_scheduled_end_with_no_meeting_window_does_not_extend_the_block():
    """Story 3. The meeting ended on time and the user walked to lunch. The AFK stretch
    after it is a break, not an overrun, and nothing in the calendar can make it one."""
    d = day().active("09:00", "09:45").afk("09:45", "10:30")
    d.window("09:03", "09:45", TEAMS, MEETING)
    assert verdict_of(event("09:00", "09:45"), d) == (True, span("09:03", "09:45"),
                                                     span("09:00", "09:45"))


def test_an_event_with_no_meeting_window_is_uncorroborated_inside_the_days_activity():
    """Story 5. The user was at the machine, working on something else, while the meeting
    they accepted went on without them. Uncorroborated: no block, and #54 will list it as a
    question rather than bill a meeting that was skipped."""
    d = day().active("08:00", "12:00")
    d.window("08:00", "12:00", "Code.exe", "sync.py - acme-integration - Visual Studio Code")
    assert verdict_of(event("09:00", "09:45"), d) == (False, None, None)


def test_an_event_with_no_meeting_window_is_uncorroborated_outside_the_days_activity_too():
    """Story 4. A client site at 07:30, before the laptop opened. The wrapper considers it
    (story 14) and reports it uncorroborated — the machine saw nothing, and the verdict says
    so rather than guessing. The same verdict as the skipped meeting above, deliberately: the
    activity source cannot tell attended-elsewhere from not-attended, and the user can."""
    d = day().afk("00:00", "08:30").active("08:30", "17:00")
    d.window("08:30", "17:00", "Code.exe", "sync.py - acme-integration - Visual Studio Code")
    assert verdict_of(event("07:30", "08:30"), d) == (False, None, None)


def test_a_teams_chat_window_does_not_corroborate():
    """A chat with the organiser during the meeting's slot is not the meeting. The pattern
    is the skill's own — `Meeting | …` and `Call with …` are meeting windows, `Chat | …` is
    not — so a message exchanged instead of attending stays uncorroborated."""
    d = day().active("09:00", "09:45")
    d.window("09:00", "09:45", TEAMS, CHAT)
    assert verdict_of(event("09:00", "09:45"), d) == (False, None, None)


def test_a_teams_call_window_corroborates():
    """The other half of the pattern: an ad hoc call over the scheduled slot is a meeting
    the user was in."""
    d = day().active("09:00", "09:45")
    d.window("09:02", "09:40", TEAMS, CALL)
    assert verdict_of(event("09:00", "09:45"), d) == (True, span("09:02", "09:40"),
                                                     span("09:00", "09:45"))


def test_a_meeting_window_elsewhere_in_the_day_does_not_corroborate_this_event():
    """Intersection, not presence. A meeting at 14:00 says nothing about the 09:00 one."""
    d = day().active("08:00", "17:00")
    d.window("14:00", "15:00", TEAMS, MEETING)
    assert verdict_of(event("09:00", "09:45"), d) == (False, None, None)


def test_a_meeting_window_that_only_touches_the_event_does_not_intersect_it():
    """The window ended as the event began: nothing of the meeting was seen inside it. The
    back-to-back case, where the previous meeting's window must not vouch for the next."""
    d = day().active("08:00", "10:00")
    d.window("08:15", "09:00", TEAMS, MEETING)
    assert verdict_of(event("09:00", "09:45"), d) == (False, None, None)


def test_a_meeting_joined_early_is_corroborated_with_the_block_starting_at_the_event():
    """The user opened the meeting five minutes early. The evidence is reported as seen —
    from 08:55 — but the block is the event's span extended only at its *end*: the minutes
    before the scheduled start are ordinary active time the surrounding block already
    covers, and nothing here re-times what the calendar said."""
    d = day().active("08:30", "10:00")
    d.window("08:55", "09:40", TEAMS, MEETING)
    assert verdict_of(event("09:00", "09:45"), d) == (True, span("08:55", "09:40"),
                                                     span("09:00", "09:45"))


def test_a_flash_of_a_meeting_window_under_the_noise_floor_does_not_corroborate():
    """The timeline drops sub-five-second window events as tab-switch noise, and so does
    the verdict: alt-tabbing through the Teams window is not attending the meeting."""
    d = day().active("09:00", "09:45")
    flash = d.event("09:10:00", seconds=3, app=TEAMS, title=MEETING)
    out = cd.filtered_day({"events": [event("09:00", "09:45")]}, MAY, AUCKLAND, [flash])
    assert out["events"][0]["corroborated"] is False


def test_fragments_of_the_meeting_window_within_the_gap_fold_are_one_run_of_evidence():
    """The user in the call while working in parallel: the meeting window recurs in
    fragments separated by seconds. Like the timeline, fragments under a minute apart are
    one span — so an overrun seen in fragments still extends the block to the last one."""
    d = day().active("09:00", "10:05")
    d.window("09:40", "09:44", TEAMS, MEETING)
    d.window("09:44:30", "10:05", TEAMS, MEETING)
    assert verdict_of(event("09:00", "09:45"), d) == (True, span("09:40", "10:05"),
                                                     span("09:00", "10:05"))


def test_a_fragment_minutes_after_the_event_ended_is_not_an_overrun():
    """The same meeting window, reopened at 09:50 to read the chat after the meeting had
    ended at 09:45. Five minutes is well past the gap fold, and the fragment does not
    intersect the event, so the block ends at the scheduled end: the evidence has to run
    *through* the end to extend it."""
    d = day().active("09:00", "10:05")
    d.window("09:03", "09:44", TEAMS, MEETING)
    d.window("09:50", "10:05", TEAMS, MEETING)
    assert verdict_of(event("09:00", "09:45"), d) == (True, span("09:03", "09:44"),
                                                     span("09:00", "09:45"))


def test_two_meeting_windows_flicked_between_keep_their_own_runs():
    """Fragments merge with the last span *of the same title*, not the last span seen. A
    user alternating between two meeting windows every few seconds — the standup and a call
    left open — would otherwise break both runs into slivers, and neither would reach the
    end it actually ran to."""
    d = day()
    for m in range(40, 50):          # each minute: fifty seconds of the meeting, ten of the call
        d.window(f"09:{m}:00", f"09:{m}:50", TEAMS, MEETING)
        d.window(f"09:{m}:50", f"09:{m + 1}:00", TEAMS, CALL)
    spans = cd.meeting_spans(d.window_events())
    clocks = [(s.astimezone(AUCKLAND).strftime("%H:%M:%S"), e.astimezone(AUCKLAND).strftime("%H:%M:%S"))
              for s, e in spans]
    assert clocks == [("09:40:00", "09:49:50"), ("09:40:50", "09:50:00")]


def test_a_zero_length_event_is_never_corroborated():
    """A reminder — Outlook lets an appointment start and end at the same instant. A meeting
    window open at that instant is not attendance of a meeting that has no span, and a
    block from it would be the whole meeting window's length on the calendar's word."""
    d = day().active("08:00", "10:00")
    d.window("08:00", "10:00", TEAMS, MEETING)
    assert verdict_of(event("09:00", "09:00"), d) == (False, None, None)


def test_an_event_that_ends_before_it_starts_is_the_adapters_fault():
    """A reversed span is not a calendar event; it is an adapter printing the wrong field.
    Refused by name, like a missing field, rather than silently uncorroborated."""
    with pytest.raises(cd.CalendarError, match="evt-09:45"):
        cd.filtered_day({"events": [event("09:45", "09:00")]}, MAY, AUCKLAND, [])


def test_meeting_spans_are_read_from_deduplicated_events_and_sorted():
    """The activity source hands back heartbeats newest-first; the spans come out collapsed
    and in order, or a re-emitted heartbeat would read as a second meeting."""
    d = day().window("14:00", "15:00", TEAMS, MEETING).window("09:00", "09:30", TEAMS, CALL)
    raw = list(reversed(with_heartbeats(d.window_events())))
    spans = cd.meeting_spans(raw)
    assert [(s.astimezone(AUCKLAND).strftime("%H:%M"), e.astimezone(AUCKLAND).strftime("%H:%M"))
            for s, e in spans] == [("09:00", "09:30"), ("14:00", "15:00")]


def test_a_block_and_its_evidence_render_in_the_skeletons_notation():
    """Both spans are clocks in the configured zone with the second-pass marker where it
    applies, like every other clock this script prints, so a block span can be handed
    straight to `--cover` or set beside a skeleton span without conversion."""
    fallback = dt.date(2026, 4, 5)
    d = day(fallback, zone="Pacific/Auckland").active("01:30", "03:30*")
    d.window("02:35*", "03:20", TEAMS, MEETING)       # opened in the second pass over 02:00–03:00
    raw = event("02:30", "03:00", id="second",
                start="2026-04-05T02:30:00+12:00", end="2026-04-05T03:00:00+12:00")
    out = cd.filtered_day({"events": [raw]}, fallback, AUCKLAND, d.window_events())["events"][0]
    assert out["corroborated"] is True
    assert out["evidence"] == {"start": "02:35:00*", "end": "03:20:00"}
    assert out["block"] == {"start": "02:30:00*", "end": "03:20:00"}


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


@pytest.fixture
def activity_day(live_aw):
    """A served activity day for the process-level tests: the wrapper reads the day's window
    events from the activity source before it runs the adapter, so a test about the adapter
    needs one to get that far. The standup in `CANNED` is corroborated by a meeting window
    that runs five minutes over; the tentative planning event has no window at all. Returns
    the fake server, for a test that wants to see what was fetched."""
    d = day().active("08:30", "12:00").afk("12:00", "13:00").active("13:00", "17:00")
    d.window("09:02", "09:50", TEAMS, "Meeting | Standup — ACME | Microsoft Teams")
    d.window("13:00", "13:30", "Code.exe", "notes.md - planning - Visual Studio Code")
    return live_aw(d)


def test_the_wrapper_prints_the_contract_for_a_date_through_an_adapter_it_is_given(
        fake_adapter, calendar_on, activity_day):
    """The whole path, end to end: configuration on, the day's window events fetched from
    the activity source, an adapter spawned as a real process, its stdout read as UTF-8,
    the filter and the verdict applied, one JSON document printed and nothing on stderr.
    The zone is the hermetic fixture's `Etc/GMT-12`, which is UTC+12 like the events, so
    the clocks come out as written."""
    r = run_cli(cd, [MAY.isoformat(), "--adapter", str(fake_adapter(CANNED))])
    assert r.code == 0, r.err
    assert r.err == ""
    assert r.json() == {
        "date": "2026-05-28",
        "zone": "zone Etc/GMT-12",
        "events": [
            {"id": "standup", "subject": "Standup — ACME", "start": "09:00:00",
             "end": "09:45:00", "show_as": "busy", "response": "accepted",
             "attendees": ["Ana Client", "Ben Colleague"],
             "corroborated": True,
             "evidence": {"start": "09:02:00", "end": "09:50:00"},
             "block": {"start": "09:00:00", "end": "09:50:00"}},
            {"id": "tentative", "subject": "Māori language week planning", "start": "13:00:00",
             "end": "13:30:00", "show_as": "tentative", "response": "tentative",
             "attendees": ["Ana Client", "Ben Colleague"],
             "corroborated": False, "evidence": None, "block": None},
        ],
    }


def test_every_printed_event_carries_a_verdict(fake_adapter, calendar_on, activity_day):
    """The AC's first line, at the boundary the rules read: `corroborated` on every event,
    true or false, with the two spans present on the corroborated ones and null otherwise —
    never absent, so a rule reading the key cannot mistake "not computed" for "no"."""
    r = run_cli(cd, [MAY.isoformat(), "--adapter", str(fake_adapter(CANNED))])
    assert r.code == 0, r.err
    for e in r.json()["events"]:
        assert e["corroborated"] in (True, False)
        assert (e["evidence"] is None) == (e["block"] is None) == (not e["corroborated"])


def test_the_activity_source_is_read_for_the_day_the_events_are_on(fake_adapter, calendar_on,
                                                                    activity_day):
    """The window events are fetched over the same UTC bounds the two reading scripts use
    for the day, so the meeting window seen here is the one the timeline shows."""
    r = run_cli(cd, [MAY.isoformat(), "--adapter", str(fake_adapter(CANNED))])
    assert r.code == 0, r.err
    fetched = activity_day.sent("GET", "aw-watcher-window")
    assert len(fetched) == 1
    # Local midnight to local midnight at UTC+12, as `timezone.utc_bounds` renders them.
    assert fetched[0]["query"]["start"].startswith("2026-05-27T12:00:00")
    assert fetched[0]["query"]["end"].startswith("2026-05-28T12:00:00")


def test_the_timelines_noise_flags_tune_the_verdict_the_same_way(fake_adapter, calendar_on,
                                                                 activity_day):
    """`--noise-floor` and `--gap-fold` are the timeline's, and a user who raised the floor in
    their `## Preferences` has the verdict read by the same floor: the standup's 48-minute
    window is under an hour-long floor, so it stops corroborating. A perverse setting, chosen
    because it is the one whose effect is visible from outside."""
    r = run_cli(cd, [MAY.isoformat(), "--adapter", str(fake_adapter(CANNED)),
                     "--noise-floor", "3600"])
    assert r.code == 0, r.err
    standup = r.json()["events"][0]
    assert standup["id"] == "standup" and standup["corroborated"] is False


def test_an_unreachable_activity_source_is_a_reason_and_the_adapter_is_never_run(
        fake_adapter, calendar_on):
    """With nothing to corroborate against, a verdict cannot be computed, and printing every
    event uncorroborated would turn each meeting into a question with nothing said about
    why. The hermetic fixture points the activity source nowhere, so this is the "AW is
    down" case the two reading scripts refuse on, refused the same way — and before the
    adapter is spawned, which matters when the adapter is Outlook taking a while to start."""
    r = run_cli(cd, [MAY.isoformat(), "--adapter",
                     str(fake_adapter(None, code=3, stderr="the adapter ran\n"))])
    assert r.code == 1
    assert r.out == ""
    assert r.err.startswith("ERR") and "ActivityWatch unreachable" in r.err
    assert "the adapter ran" not in r.err


def test_a_day_with_no_window_watcher_bucket_is_a_reason_not_a_day_of_questions(
        fake_adapter, calendar_on, monkeypatch):
    """The same refusal `activity_timeline` makes: a missing window bucket is a broken
    instrument, not an empty day. Here it would read as "no meeting was attended"."""
    d = day().active("09:00", "17:00")
    buckets = {k: v for k, v in d.buckets().items() if not k.startswith("aw-watcher-window")}
    with aw_server(buckets, d.settings()) as srv:
        monkeypatch.setenv("TIMESHEET_ACTIVITY_URL", srv.base)
        r = run_cli(cd, [MAY.isoformat(), "--adapter", str(fake_adapter(CANNED))])
    assert r.code == 1 and r.out == ""
    assert "aw-watcher-window" in r.err and "Traceback" not in r.err


def test_a_per_run_offset_dates_the_day_like_the_other_reading_scripts(fake_adapter,
                                                                       calendar_on,
                                                                       activity_day):
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
        fake_adapter, calendar_on, activity_day):
    """Story 28: Outlook not reachable is a loud failure, not a day with no meetings. The
    adapter's own reason is what the user needs to read, so it is carried through."""
    r = run_cli(cd, [MAY.isoformat(), "--adapter",
                     str(fake_adapter(None, code=3, stderr="Outlook is not running\n"))])
    assert r.code != 0
    assert r.out == ""
    assert r.err.startswith("ERR") and "Outlook is not running" in r.err
    assert "Traceback" not in r.err


def test_an_adapter_that_prints_something_other_than_the_contract_is_refused(
        fake_adapter, calendar_on, activity_day):
    """A PowerShell warning on stdout, a progress line, a BOM — anything that is not the
    JSON document is the adapter's bug, and the wrapper names it as that rather than
    handing the model a `JSONDecodeError`."""
    r = run_cli(cd, [MAY.isoformat(), "--adapter",
                     str(fake_adapter(text="WARNING: Outlook took a while\n{\"events\": []}"))])
    assert r.code != 0 and r.out == ""
    assert "adapter" in r.err and "Traceback" not in r.err


def test_an_adapter_event_missing_a_field_is_the_adapters_fault_at_process_level(
        fake_adapter, calendar_on, activity_day):
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


def test_nothing_is_written_anywhere(fake_adapter, calendar_on, activity_day, workspace,
                                     monkeypatch, tmp_path):
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

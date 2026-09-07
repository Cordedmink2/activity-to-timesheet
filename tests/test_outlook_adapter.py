"""The Outlook adapter: classic Outlook's default calendar, printed in the wrapper's contract.

`skills/daily/scripts/outlook_calendar.ps1` is the first producer of the JSON that
`calendar_day.py` reads (#51, ADR-0008). What it owns is the translation from Outlook's
object model — integer enumerations, local `DateTime`s of no declared kind, a recipients
collection that includes the meeting room — into the nine fields of the contract. That
translation is what is pinned here, under the Windows PowerShell 5.1 the wrapper runs it in.

No Outlook is started. The script keeps its functions apart from its main body so a test can
dot-source it and hand `ConvertTo-CalendarEvent` a `PSCustomObject` shaped like an
`AppointmentItem`: the same member names, so the code under test is the code that runs
against the real thing. The one read of the real calendar is by hand — recorded in
`docs/skills/daily/decision-log.md` — because a test that starts the user's Outlook is a side effect
the suite has no business having.
"""

import json
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from shipped import SKILLS

ADAPTER = SKILLS / "daily" / "scripts" / "outlook_calendar.ps1"

# The same lookup `test_install_scripts.py` makes, kept local rather than imported from a
# sibling test module: a test module is not a library, and three lines are cheaper than
# the coupling.
WINPS = shutil.which("powershell.exe") if sys.platform == "win32" else None
requires_winps = pytest.mark.skipif(not WINPS, reason="Windows PowerShell 5.1 not available")

# Outlook's enumerations, by the numbers the object model reports. Read out of
# Microsoft.Office.Interop.Outlook 15.0 (see the adapter's own table); spelled here a second
# time on purpose, so a slip in the adapter's table is caught rather than mirrored.
BUSY = {0: "free", 1: "tentative", 2: "busy", 3: "out_of_office", 4: "working_elsewhere"}
RESPONSE = {0: "none", 1: "organizer", 2: "tentative", 3: "accepted", 4: "declined",
            5: "not_responded"}
NON_MEETING, MEETING_RECEIVED, MEETING_CANCELED, RECEIVED_AND_CANCELED = 0, 3, 5, 7
REQUIRED, OPTIONAL, RESOURCE = 1, 2, 3


def winps_argv(*args: str) -> list[str]:
    """Windows PowerShell as the wrapper spawns it, for a test `requires_winps` let through."""
    assert WINPS, "requires_winps should have skipped this test"
    return [WINPS, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", *args]


def meeting(**overrides) -> str:
    """One fake `AppointmentItem` as PowerShell source: a received, accepted, busy, timed
    meeting on 2026-05-28 Auckland time (UTC+12), with a colleague, a client and the room
    invited. A test names only what it changes — `MeetingStatus=NON_MEETING` for an
    appointment the user wrote. `StartUTC`/`EndUTC` are what the adapter reads;
    `Start`/`End` are present because the real object has them and a slip to the local
    clock has to be visible."""
    fields = {
        "EntryID": "'00000000F24B0D74ABCDEF'",
        "Subject": "'Sprint review'",
        "Start": "[datetime]'2026-05-28T09:00:00'",
        "End": "[datetime]'2026-05-28T09:45:00'",
        "StartUTC": "[datetime]'2026-05-27T21:00:00'",
        "EndUTC": "[datetime]'2026-05-27T21:45:00'",
        "BusyStatus": "2",
        "ResponseStatus": "3",
        "MeetingStatus": str(MEETING_RECEIVED),
        "AllDayEvent": "$false",
        "IsRecurring": "$false",
        "Recipients": ("@([pscustomobject]@{Name='Ben Colleague'; Type=1}, "
                       "[pscustomobject]@{Name='Ana Client'; Type=2}, "
                       "[pscustomobject]@{Name='Tuatara Room'; Type=3})"),
    }
    fields.update(overrides)
    body = "; ".join(f"{k}={v}" for k, v in fields.items())
    return f"[pscustomobject]@{{{body}}}"


def run_adapter_functions(tmp_path: Path, body: str) -> subprocess.CompletedProcess:
    """Dot-source the adapter under 5.1 and run `body` against its functions.

    A driver file rather than `-Command`, so a subject with a macron reaches PowerShell
    intact: written with a BOM, because 5.1 reads a BOM-less `.ps1` as the ANSI code page.
    """
    driver = tmp_path / "driver.ps1"
    driver.write_text(f". '{ADAPTER}'\n{textwrap.dedent(body)}\n", encoding="utf-8-sig")
    return subprocess.run(winps_argv("-File", str(driver)),
                          capture_output=True, encoding="utf-8", errors="replace")


def events_of(tmp_path: Path, *items: str) -> list[dict]:
    """The events the adapter prints for `items`, through its own output routine, so the
    document is the bytes the wrapper would read."""
    # Parenthesised: in argument mode PowerShell reads `[pscustomobject]@{...}` as text.
    listed = ", ".join(f"(ConvertTo-CalendarEvent ({item}))" for item in items)
    res = run_adapter_functions(
        tmp_path, f"Write-CalendarDay @({listed})")
    assert res.returncode == 0, f"exit {res.returncode}:\n{res.stdout}{res.stderr}"
    assert res.stderr == "", f"the adapter wrote to stderr on success:\n{res.stderr}"
    doc = json.loads(res.stdout.lstrip("﻿"))
    assert list(doc) == ["events"] and isinstance(doc["events"], list), doc
    return doc["events"]


def test_the_adapter_is_the_file_the_wrapper_names():
    """`calendar_day.py` resolves `outlook_calendar.ps1` beside itself and refuses by name
    when it is missing. This is the file that answers."""
    assert ADAPTER.is_file(), f"{ADAPTER} is not there"


@requires_winps
def test_a_received_meeting_is_printed_in_the_contract(tmp_path):
    """The nine fields, every one, from the members the object model exposes. Instants come
    from `StartUTC`/`EndUTC` as `Z` times — the wrapper decides the zone — and the room is
    not an attendee: a resource is where the meeting was, not who was in it."""
    (event,) = events_of(tmp_path, meeting())
    assert event == {
        "id": "00000000F24B0D74ABCDEF",
        "subject": "Sprint review",
        "start": "2026-05-27T21:00:00Z",
        "end": "2026-05-27T21:45:00Z",
        "show_as": "busy",
        "response": "accepted",
        "all_day": False,
        "cancelled": False,
        "attendees": ["Ben Colleague", "Ana Client"],
    }


@requires_winps
def test_the_flags_are_real_booleans_and_one_event_is_still_an_array(tmp_path):
    """The two shapes of adapter bug the wrapper refuses by name: a `"false"` string, and
    Windows PowerShell's habit of unwrapping a one-element array. Asserted on the parsed
    document because that is where the wrapper would see them."""
    (event,) = events_of(tmp_path, meeting(AllDayEvent="$true"))
    assert event["all_day"] is True and event["cancelled"] is False


@requires_winps
def test_no_events_is_an_empty_array_not_nothing(tmp_path):
    """A day with nothing on the calendar is `{"events": []}` — a calendar day with no
    events, which the wrapper prints as one — and not an empty stdout it would refuse."""
    assert events_of(tmp_path) == []


@requires_winps
def test_no_events_returned_from_a_function_is_still_an_empty_array(tmp_path):
    """The shape the script actually composes: `Write-CalendarDay (Read-CalendarDay $day)`.
    PowerShell hands an empty array back from a function as `$null`, and `@($null)` is an
    array of one null — which printed `{"events": [null]}` and had the wrapper refuse a
    quiet day as an adapter bug. An array literal, as the test above passes, never showed
    it; the review of #51 did."""
    res = run_adapter_functions(tmp_path, """
        function Read-NothingDay { $found = New-Object System.Collections.ArrayList; return $found.ToArray() }
        Write-CalendarDay (Read-NothingDay)
        """)
    assert res.returncode == 0, f"exit {res.returncode}:\n{res.stdout}{res.stderr}"
    assert json.loads(res.stdout.lstrip("﻿")) == {"events": []}


@requires_winps
def test_a_self_authored_appointment_is_reported_as_organizer(tmp_path):
    """The site-visit case (#49 story 4). An appointment the user wrote themselves is
    `olNonMeeting`, and Outlook reports its response as none or as organized depending on
    how it was made. The user authored it either way, so the adapter says `organizer` —
    the wrapper drops `none`, and would drop the one event the story exists for."""
    for response in (0, 1):
        (event,) = events_of(
            tmp_path, meeting(MeetingStatus=str(NON_MEETING), ResponseStatus=str(response),
                                  Recipients="@()"))
        assert event["response"] == "organizer", response
        assert event["attendees"] == []


@requires_winps
@pytest.mark.parametrize("status", [MEETING_CANCELED, RECEIVED_AND_CANCELED])
def test_a_cancelled_meeting_is_marked_cancelled(tmp_path, status):
    """Both cancellations: one the user sent, one they received. Outlook also flips the
    show-as to free and prefixes the subject; the flag is what the contract reads."""
    (event,) = events_of(tmp_path, meeting(MeetingStatus=str(status),
                                               Subject="'Canceled: Sprint review'"))
    assert event["cancelled"] is True


@requires_winps
def test_a_received_meeting_that_is_not_cancelled_is_not(tmp_path):
    (event,) = events_of(tmp_path, meeting(MeetingStatus=str(MEETING_RECEIVED)))
    assert event["cancelled"] is False


@requires_winps
def test_instances_of_a_recurring_meeting_have_ids_of_their_own(tmp_path):
    """An occurrence reports the series master's `EntryID`, so two instances of the standup
    would collide on it. The id has to be stable *and* distinct, so an instance's carries the
    occurrence's start; a one-off keeps the bare id the drill-down (#55) can reopen."""
    first, second = events_of(
        tmp_path,
        meeting(IsRecurring="$true"),
        meeting(IsRecurring="$true", StartUTC="[datetime]'2026-05-28T21:00:00'",
                    EndUTC="[datetime]'2026-05-28T21:45:00'"))
    assert first["id"] != second["id"]
    assert first["id"].startswith("00000000F24B0D74ABCDEF")
    assert second["id"].startswith("00000000F24B0D74ABCDEF")


@requires_winps
def test_every_show_as_outlook_can_report_is_spelled_as_the_contract_spells_it(tmp_path):
    items = [meeting(BusyStatus=str(n)) for n in sorted(BUSY)]
    assert [e["show_as"] for e in events_of(tmp_path, *items)] == \
        [BUSY[n] for n in sorted(BUSY)]


@requires_winps
def test_every_response_outlook_can_report_is_spelled_as_the_contract_spells_it(tmp_path):
    """On a *received* meeting, so the self-authored override does not apply."""
    items = [meeting(ResponseStatus=str(n)) for n in sorted(RESPONSE)]
    assert [e["response"] for e in events_of(tmp_path, *items)] == \
        [RESPONSE[n] for n in sorted(RESPONSE)]


@requires_winps
def test_a_value_outside_the_enumeration_is_refused_by_name(tmp_path):
    """Not mapped to a guess: an unknown show-as would fall out of the wrapper's filter
    without a word, which is the quiet wrong answer the whole skill is built against."""
    res = run_adapter_functions(
        tmp_path, f"Write-CalendarDay @((ConvertTo-CalendarEvent ({meeting(BusyStatus='9')})))")
    assert res.returncode != 0
    assert res.stdout == ""
    assert "9" in res.stderr and "Sprint review" in res.stderr
    assert res.stderr.strip().count("\n") == 0, f"more than one line:\n{res.stderr}"


@requires_winps
def test_a_meeting_status_outside_the_enumeration_is_refused_by_name(tmp_path):
    """The third enumeration, held to the same rule: read as "not cancelled", an unknown
    status would let a cancellation Outlook spells some new way through as a live meeting."""
    res = run_adapter_functions(
        tmp_path, f"Write-CalendarDay @((ConvertTo-CalendarEvent ({meeting(MeetingStatus='4')})))")
    assert res.returncode != 0 and res.stdout == ""
    assert "4" in res.stderr and "Sprint review" in res.stderr


@requires_winps
def test_a_refusal_quoting_a_subject_outside_ascii_reaches_the_wrapper_intact(tmp_path):
    """stderr is the wrapper's reason line and is read as UTF-8 too; written through the
    console it would arrive with the macron replaced, which the review of #51 measured."""
    res = run_adapter_functions(
        tmp_path, "Write-CalendarDay @((ConvertTo-CalendarEvent ("
                  f"{meeting(BusyStatus='9', Subject=chr(39) + 'Māori planning' + chr(39))})))")
    assert res.returncode != 0
    assert "Māori planning" in res.stderr, res.stderr


@requires_winps
def test_a_subject_and_attendee_outside_ascii_survive_the_trip(tmp_path):
    """Windows PowerShell writes redirected stdout in the console code page unless told
    otherwise, and the wrapper reads UTF-8 by contract. The macron is the one that would
    show, on a machine whose users write te reo."""
    (event,) = events_of(tmp_path, meeting(
        Subject="'Māori language week planning'",
        Recipients="@([pscustomobject]@{Name='Hēmi Colleague'; Type=1})"))
    assert event["subject"] == "Māori language week planning"
    assert event["attendees"] == ["Hēmi Colleague"]


@requires_winps
def test_a_subjects_surrounding_whitespace_is_dropped(tmp_path):
    """Seen on a real calendar: a standup's subject with a trailing space, which would
    otherwise reach the rules' attribution and the drafted notes as written."""
    (event,) = events_of(tmp_path, meeting(Subject="'  Standup '"))
    assert event["subject"] == "Standup"


# --------------------------------------------------------------------------------------
# The reasons it fails. Outlook cannot be made absent on the machine that has it, so the
# call that would fail is shadowed: a function named `New-Object` defined in the driver
# takes precedence over the cmdlet for the rest of the session.
# --------------------------------------------------------------------------------------

NOT_REGISTERED = ("Retrieving the COM class factory for component with CLSID "
                  "{0006F03A-0000-0000-C000-000000000046} failed due to the following error: "
                  "80040154 Class not registered (Exception from HRESULT: 0x80040154 "
                  "(REGDB_E_CLASSNOTREG)).")


@requires_winps
def test_no_classic_outlook_is_one_line_naming_the_cause(tmp_path):
    """AC: no classic Outlook produces a non-zero exit and a one-line reason naming the
    cause. Class-not-registered is what a machine with new Outlook alone, or no Outlook,
    reports; the user is told which Outlook is missing, not handed a CLSID."""
    res = run_adapter_functions(tmp_path, f"""
        function New-Object {{ throw '{NOT_REGISTERED}' }}
        Read-CalendarDay ([datetime]'2026-05-28')
        """)
    assert res.returncode != 0
    assert res.stdout == ""
    assert res.stderr.strip().count("\n") == 0, f"more than one line:\n{res.stderr}"
    assert "classic Outlook" in res.stderr and "not installed" in res.stderr


@requires_winps
def test_any_other_failure_to_start_outlook_carries_outlooks_own_words(tmp_path):
    """A profile prompt refused, a COM server that would not answer: the cause is in the
    message and the adapter passes it on rather than guessing at it."""
    res = run_adapter_functions(tmp_path, """
        function New-Object { throw 'The server process could not be started (0x80080005)' }
        Read-CalendarDay ([datetime]'2026-05-28')
        """)
    assert res.returncode != 0 and res.stdout == ""
    assert "classic Outlook" in res.stderr and "0x80080005" in res.stderr


@requires_winps
@pytest.mark.parametrize("argv", [[], ["28-05-2026"]], ids=["no date", "wrong shape"])
def test_a_missing_or_malformed_date_is_a_usage_error(argv):
    """Before Outlook is touched: a bad argument must not start it."""
    res = subprocess.run(winps_argv("-File", str(ADAPTER), *argv),
                         capture_output=True, encoding="utf-8", errors="replace")
    assert res.returncode == 2, f"exit {res.returncode}:\n{res.stdout}{res.stderr}"
    assert res.stdout == ""
    assert "YYYY-MM-DD" in res.stderr

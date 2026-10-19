"""The `timesheet-provider` dispatcher against a fake adapter (provider contract §§ 1-5, 8.4.1).

Nothing here touches Harvest: the dispatcher is run in-process through `support.run_cli`
with a recording fake adapter selected by `TIMESHEET_PROVIDER`, so what is under test is
the contract's own behaviour - the gate, the argument validation, the output formats and
the exit-code classes - and not any one provider. The Harvest adapter has its own file.
Never a subprocess: that would read the real `.env` (`conftest._hermetic` says why).
"""
from __future__ import annotations

import json
import sys

import pytest

from provider import dispatcher
from provider.errors import Misconfigured, NoMatch, Refused, Unreachable
from support import run_cli

POST = ["post", "--project-id", "P1", "--task-id", "T1", "--date", "2026-08-12",
        "--start", "09:00", "--end", "10:30", "--notes", "Drafted the spec"]


class FakeAdapter:
    """Records every call; each behaviour is a plain attribute a test overrides."""
    NAME = "fake"

    def __init__(self):
        self.calls: list[tuple] = []
        self.raises: dict[str, Exception] = {}
        self.matches: list[dict] = []
        self.entries: list[dict] = []
        self.age: float | None = None
        self.projects = 3

    def _go(self, name, *args):
        self.calls.append((name, *args))
        if name in self.raises:
            raise self.raises[name]

    def check_post(self, body):
        self._go("check_post", body)

    def check_patch(self, entry_id, fields):
        self._go("check_patch", entry_id, fields)

    def post(self, body):
        self._go("post", body)
        return "E-1"

    def patch(self, entry_id, fields):
        self._go("patch", entry_id, fields)
        return entry_id

    def lookup(self, query, task, catalog_dir, cache_only, days):
        self._go("lookup", query, task, catalog_dir, cache_only, days)
        return self.matches

    def list_entries(self, date_from, date_to):
        self._go("list_entries", date_from, date_to)
        return self.entries

    def refresh(self, wait_for=None, attempts=20, delay=15):
        self._go("refresh", wait_for, attempts, delay)
        return self.projects

    def catalog_age(self):
        self._go("catalog_age")
        return self.age

    def writes(self):
        return [c for c in self.calls if c[0] in ("post", "patch")]


@pytest.fixture
def fake(monkeypatch):
    adapter = FakeAdapter()
    monkeypatch.setitem(sys.modules, "provider.fake", adapter)
    monkeypatch.setattr(dispatcher, "known_adapters", lambda: ["fake", "harvest"])
    monkeypatch.setenv("TIMESHEET_PROVIDER", "fake")
    return adapter


def tp(*args):
    return run_cli(dispatcher, list(args))


def swap(args, flag, value):
    out = list(args)
    out[out.index(flag) + 1] = value
    return out


def without(args, flag):
    out = list(args)
    i = out.index(flag)
    del out[i:i + 2]
    return out


# ---------------------------------------------------------------- § 1 adapter selection

def test_unset_or_blank_selects_harvest(monkeypatch):
    monkeypatch.delenv("TIMESHEET_PROVIDER", raising=False)
    assert dispatcher.selected_adapter().NAME == "harvest"
    monkeypatch.setenv("TIMESHEET_PROVIDER", "   ")
    assert dispatcher.selected_adapter().NAME == "harvest"


def test_an_unknown_adapter_is_a_usage_error_that_lists_the_known_ones(monkeypatch):
    monkeypatch.setenv("TIMESHEET_PROVIDER", "nope")
    r = tp("list", "2026-08-12")
    assert r.code == 2 and r.out == ""
    first, *_ = r.err.splitlines()
    assert first.startswith("ERR ") and "nope" in r.err and "harvest" in r.err


def test_importing_the_dispatcher_resolves_no_setting():
    # `--help` and the usage errors must work on a machine with nothing configured (§ 5).
    r = tp("--help")
    assert r.code == 0 and "timesheet-provider" in r.out


@pytest.mark.parametrize("argv", [[], ["frobnicate"]])
def test_no_or_unknown_subcommand_is_usage(fake, argv):
    r = tp(*argv)
    assert r.code == 2 and r.err.startswith("ERR ") and r.out == ""


def test_no_traceback_ever_an_internal_defect_is_err_internal_exit_1(fake):
    fake.raises["check_post"] = ZeroDivisionError("boom")
    r = tp(*POST)
    assert r.code == 1 and r.err.startswith("ERR internal") and "Traceback" not in r.err
    assert fake.writes() == []


# ---------------------------------------------------------------- § 2 the gate, post

def test_post_without_confirm_previews_and_never_writes(fake):
    r = tp(*POST)
    assert r.code == 0
    body = ('{"project_id": "P1", "task_id": "T1", "date": "2026-08-12", '
            '"start": "09:00", "end": "10:30", "notes": "Drafted the spec"}')
    assert r.out == (f"WOULD POST {body}\n"
                     "Nothing was posted. Re-run with --confirm to create this entry.\n")
    assert fake.writes() == []
    assert [c[0] for c in fake.calls] == ["check_post"]


def test_post_with_confirm_sends_the_very_body_that_was_previewed(fake):
    preview = tp(*POST)
    sent = tp(*POST, "--confirm")
    assert sent.code == 0 and sent.out == "OK E-1\n"
    (_, body), = fake.writes()
    assert preview.out.splitlines()[0] == "WOULD POST " + json.dumps(body, ensure_ascii=False)
    assert list(body) == ["project_id", "task_id", "date", "start", "end", "notes"]


def test_the_preview_does_not_escape_non_ascii(fake):
    r = tp(*swap(POST, "--notes", "Māori – café"))
    assert "Māori – café" in r.out


def test_the_adapter_check_runs_on_the_preview_and_the_confirmed_run_alike(fake):
    tp(*POST)
    tp(*POST, "--confirm")
    assert [c[0] for c in fake.calls] == ["check_post", "check_post", "post"]


@pytest.mark.parametrize("where", [0, 3, "end"])
def test_confirm_may_be_typed_anywhere(fake, where):
    argv = list(POST)
    argv.insert(len(argv) if where == "end" else where + 1, "--confirm")
    r = tp(*argv)
    assert r.code == 0 and r.out == "OK E-1\n"


def test_a_value_flag_left_without_its_value_cannot_swallow_the_gate(fake):
    argv = POST[:-1] + ["--confirm"]       # `--notes --confirm`
    r = tp(*argv)
    assert r.code == 2 and fake.writes() == [] and r.out == ""


def test_a_refusing_check_stops_before_anything_is_previewed(fake):
    fake.raises["check_post"] = Refused("this entry would be billed wrongly")
    r = tp(*POST)
    assert r.code == 4 and r.out == "" and r.err.startswith("ERR this entry would be billed")
    assert fake.writes() == []


@pytest.mark.parametrize("exc, code", [(Misconfigured("missing configuration: X"), 3),
                                       (Refused("no"), 4), (Unreachable("down"), 5)])
def test_a_check_that_cannot_decide_never_passes_quietly(fake, exc, code):
    fake.raises["check_post"] = exc
    r = tp(*POST, "--confirm")
    assert r.code == code and r.out == "" and fake.writes() == []


def test_a_write_failure_maps_to_its_class_and_prints_no_ok(fake):
    fake.raises["post"] = Unreachable("timed out")
    r = tp(*POST, "--confirm")
    assert r.code == 5 and "OK" not in r.out and r.err.startswith("ERR ")


# ---------------------------------------------------------------- § 3.1 post validation

@pytest.mark.parametrize("flag", ["--project-id", "--task-id", "--date", "--start",
                                  "--end", "--notes"])
def test_post_requires_every_value_flag_and_names_the_missing_one(fake, flag):
    r = tp(*without(POST, flag))
    assert r.code == 2 and flag in r.err and fake.calls == []


def test_empty_notes_are_allowed_only_as_an_explicit_empty_string(fake):
    assert tp(*swap(POST, "--notes", "")).code == 0
    assert tp(*without(POST, "--notes")).code == 2


@pytest.mark.parametrize("start, end", [("10:00", "09:00"), ("09:00", "09:00")])
def test_reversed_or_equal_range_is_refused_before_any_adapter_is_asked(fake, start, end):
    r = tp(*swap(swap(POST, "--start", start), "--end", end))
    assert r.code == 2 and fake.calls == []


@pytest.mark.parametrize("bad", ["8:15am", "20260812", "2026-W33-1", "2026-8-12",
                                 "2026-02-30", "tomorrow", ""])
def test_the_date_has_one_spelling(fake, bad):
    r = tp(*swap(POST, "--date", bad))
    assert r.code == 2 and fake.calls == []


@pytest.mark.parametrize("bad", ["8:15am", "8:15", "0815", "24:00", "09:60", "09:00*", "9", ""])
def test_the_clock_has_one_spelling_and_no_second_pass_marker(fake, bad):
    r = tp(*swap(POST, "--start", bad))
    assert r.code == 2 and fake.calls == []


def test_a_repeated_value_flag_is_a_usage_error_never_last_wins(fake):
    r = tp(*POST, "--notes", "again")
    assert r.code == 2 and "--notes" in r.err and fake.calls == []


def test_a_repeated_confirm_is_fine(fake):
    assert tp(*POST, "--confirm", "--confirm").out == "OK E-1\n"


def test_an_unknown_flag_is_usage(fake):
    assert tp(*POST, "--hours", "2").code == 2


def test_stdout_is_data_and_stderr_is_diagnosis(fake):
    ok = tp(*POST, "--confirm")
    assert ok.err == ""
    bad = tp(*without(POST, "--end"))
    assert bad.out == "" and bad.err.splitlines()[0].startswith("ERR ")


# ---------------------------------------------------------------- § 3.2 patch

def test_patch_previews_only_the_fields_passed_in_post_order(fake):
    r = tp("patch", "E-9", "--notes", "later", "--start", "09:30")
    assert r.code == 0
    assert r.out == ('WOULD PATCH E-9 {"start": "09:30", "notes": "later"}\n'
                     "Nothing was changed. Re-run with --confirm to apply it.\n")
    assert fake.writes() == []
    assert fake.calls == [("check_patch", "E-9", {"start": "09:30", "notes": "later"})]


@pytest.mark.parametrize("argv", [["patch", "E-9", "--notes", "x", "--confirm"],
                                  ["patch", "--confirm", "E-9", "--notes", "x"]])
def test_patch_confirm_may_come_before_or_after_the_id(fake, argv):
    r = tp(*argv)
    assert r.out == "OK E-9\n"
    assert fake.writes() == [("patch", "E-9", {"notes": "x"})]


def test_patch_needs_an_id_and_a_field(fake):
    assert tp("patch").code == 2
    assert tp("patch", "E-9").code == 2
    assert tp("patch", "E-9", "--confirm").code == 2
    assert fake.calls == []


def test_patch_with_both_times_must_order_them_but_one_alone_is_allowed(fake):
    assert tp("patch", "E-9", "--start", "11:00", "--end", "10:00").code == 2
    assert tp("patch", "E-9", "--start", "11:00").code == 0
    assert tp("patch", "E-9", "--end", "11:00").code == 0


def test_patch_has_no_duration_flag(fake):
    for flag in ("--hours", "--duration"):
        r = tp("patch", "E-9", flag, "2")
        assert r.code == 2


def test_patch_repeated_value_flag_and_two_ids_are_usage(fake):
    assert tp("patch", "E-9", "--notes", "a", "--notes", "b").code == 2
    assert tp("patch", "E-9", "E-10", "--notes", "a").code == 2


def test_patch_check_refusal_is_not_previewed(fake):
    fake.raises["check_patch"] = Refused("straddles the change")
    r = tp("patch", "E-9", "--start", "01:30")
    assert r.code == 4 and r.out == ""


def test_patch_check_that_cannot_read_fails_on_the_preview_too(fake):
    fake.raises["check_patch"] = Unreachable("no answer")
    assert tp("patch", "E-9", "--start", "01:30").code == 5


# ---------------------------------------------------------------- § 3.3 lookup

MATCHES = [
    {"code": "ZZZ-2", "project_id": 22, "name": "Billing only", "client": "Acme Ltd",
     "matched_on": "client", "tasks": [{"id": 5, "name": "Dev", "billable": True}]},
    {"code": "ACM-CR202", "project_id": 10, "name": "Field Services", "client": "Acme Ltd",
     "matched_on": "code", "source": "history",
     "tasks": [{"id": 7, "name": "Admin", "billable": False},
               {"id": 8, "name": "Build", "billable": True}]},
    {"code": "ACM-X", "project_id": 11, "name": "Other", "client": "",
     "matched_on": "code/name", "tasks": []},
]


def test_lookup_text_is_ranked_and_shaped(fake):
    fake.matches = MATCHES
    r = tp("lookup", "acm")
    assert r.code == 0
    assert r.out == ("ACM-CR202  10  Field Services  [Acme Ltd]\n"
                     "    7  Admin  (NON-billable)\n"
                     "    8  Build  (billable)\n"
                     "ACM-X  11  Other\n"
                     "ZZZ-2  22  Billing only  [Acme Ltd]\n"
                     "    5  Dev  (billable)\n")


def test_lookup_json_always_carries_source_and_string_identifiers(fake):
    fake.matches = MATCHES
    r = tp("lookup", "acm", "--json")
    data = r.json()
    assert [m["code"] for m in data] == ["ACM-CR202", "ACM-X", "ZZZ-2"]
    assert all(m["source"] in ("catalog", "history") for m in data)
    assert data[0]["source"] == "history" and data[2]["source"] == "catalog"
    assert data[0]["project_id"] == "10" and data[0]["tasks"][0]["id"] == "7"
    assert data[1]["client"] == ""
    assert r.out == json.dumps(data, indent=2) + "\n"


def test_lookup_hands_the_adapter_its_arguments(fake):
    fake.matches = MATCHES
    tp("lookup", "acm", "--task", "Dev", "--cache-only", "--days", "30", "--catalog-dir", "/x")
    assert fake.calls == [("lookup", "acm", "Dev", "/x", True, 30)]
    fake.calls.clear()
    tp("lookup", "acm")
    assert fake.calls == [("lookup", "acm", None, None, False, 180)]


def test_lookup_with_no_match_is_exit_6(fake):
    r = tp("lookup", "nothing")
    assert r.code == 6 and r.out == ""
    assert r.err.startswith("ERR no project matching 'nothing' in the catalog or recent entries")


@pytest.mark.parametrize("argv", [["lookup"], ["lookup", "a", "b"], ["lookup", "a", "--days", "x"],
                                  ["lookup", "a", "--days", "0"], ["lookup", "a", "--task", "x",
                                                                   "--task", "y"],
                                  ["lookup", "a", "--no-live"], ["lookup", "a", "--mcp-dir", "d"]])
def test_lookup_usage_errors(fake, argv):
    assert tp(*argv).code == 2 and fake.calls == []


@pytest.mark.parametrize("exc, code", [(Misconfigured("missing configuration: X"), 3),
                                       (Refused("no"), 4), (Unreachable("down"), 5)])
def test_a_failed_lookup_read_is_never_reported_as_no_match(fake, exc, code):
    fake.raises["lookup"] = exc
    assert tp("lookup", "q").code == code


# ---------------------------------------------------------------- § 3.4 list

E = [
    {"id": 3, "date": "2026-08-12", "start": "13:00", "end": "14:00", "hours": 1.0,
     "project_code": "ACM-1", "task_name": "Development of a very long task name here",
     "notes": "later"},
    {"id": 2, "date": "2026-08-12", "start": "09:00", "end": "11:45", "hours": 2.75,
     "project_code": "ACM-1", "task_name": "Dev", "notes": "a\nb" + "x" * 80},
    {"id": 1, "date": "2026-08-14", "start": None, "end": None, "hours": 0.5,
     "project_code": None, "task_name": None, "notes": ""},
]


def test_list_lines_are_sorted_and_columned(fake):
    fake.entries = [dict(e, hours=e["hours"]) for e in E]
    r = tp("list", "2026-08-12", "2026-08-14")
    assert r.code == 0
    lines = r.out.splitlines()
    long_notes = "a b" + "x" * 56 + "…"
    assert lines[0] == f"{'2':<10}  2026-08-12  09:00-11:45   2.75h  {'ACM-1':<11}  {'Dev':<25}  {long_notes}"
    assert lines[1] == (f"{'3':<10}  2026-08-12  13:00-14:00   1.00h  {'ACM-1':<11}  "
                        f"{'Development of a very lon':<25}  later")
    assert lines[2] == f"{'1':<10}  2026-08-14  --:-----:--   0.50h  {'?':<11}  {'?':<25}  "


def test_list_one_date_is_both_ends(fake):
    tp("list", "2026-08-12")
    assert fake.calls == [("list_entries", "2026-08-12", "2026-08-12")]


def test_list_by_day_prints_every_date_including_the_empty_ones(fake):
    fake.entries = [E[0], E[1]]
    r = tp("list", "2026-08-11", "2026-08-13", "--by-day")
    assert r.out.splitlines() == [
        "2026-08-11  Tue    0.00h   0 entries  -",
        "2026-08-12  Wed    3.75h   2 entries  ACM-1",
        "2026-08-13  Thu    0.00h   0 entries  -",
    ]
    fake.entries = [E[0]]
    r = tp("list", "2026-08-12", "--by-day")
    assert r.out == "2026-08-12  Wed    1.00h   1 entry    ACM-1\n"


def test_list_by_day_never_drops_an_entry_silently(fake):
    fake.entries = [E[0], dict(E[1], date=None, id=77), dict(E[2], id=88)]
    r = tp("list", "2026-08-12", "--by-day")
    assert "(skipped 2 with no date inside the range: 77, 88)" in r.err


def test_an_empty_range_is_success_with_a_stderr_notice(fake):
    r = tp("list", "2026-08-12", "2026-08-13")
    assert r.code == 0 and r.out == ""
    assert r.err == "(no time entries from 2026-08-12 to 2026-08-13)\n"


@pytest.mark.parametrize("argv", [["list"], ["list", "x"], ["list", "2026-08-13", "2026-08-12"],
                                  ["list", "2026-08-12", "2026-08-13", "2026-08-14"],
                                  ["list", "20260812"]])
def test_list_range_errors_are_usage_and_ask_nothing(fake, argv):
    assert tp(*argv).code == 2 and fake.calls == []


@pytest.mark.parametrize("exc, code", [(Misconfigured("missing configuration: X"), 3),
                                       (Refused("no"), 4), (Unreachable("down"), 5)])
def test_a_failed_list_is_non_zero_and_prints_nothing(fake, exc, code):
    fake.raises["list_entries"] = exc
    r = tp("list", "2026-08-12")
    assert r.code == code and r.out == ""


# ---------------------------------------------------------------- § 3.5 refresh

def test_refresh_says_how_many_projects(fake):
    r = tp("refresh")
    assert r.out == "OK 3 projects\n" and fake.calls == [("refresh", None, 20, 15)]


def test_refresh_wait_passes_its_knobs_and_prints_the_code(fake):
    r = tp("refresh", "--wait", "ACM-1", "--attempts", "4", "--delay", "0.5")
    assert r.out == "OK ACM-1\n"
    assert fake.calls == [("refresh", "ACM-1", 4, 0.5)]


def test_refresh_wait_that_never_appears_is_exit_6(fake):
    fake.raises["refresh"] = NoMatch("ACM-1 did not appear after 4 attempts")
    r = tp("refresh", "--wait", "ACM-1")
    assert r.code == 6 and r.err.startswith("ERR ACM-1 did not appear after 4 attempts")


def test_refresh_age_touches_nothing_else(fake):
    fake.age = 8.9
    r = tp("refresh", "--age")
    assert r.out == "AGE 8\n" and fake.calls == [("catalog_age",)]
    fake.age = None
    assert tp("refresh", "--age").out == "ABSENT\n"


@pytest.mark.parametrize("argv", [["refresh", "--age", "--wait", "X"], ["refresh", "--attempts", "3"],
                                  ["refresh", "--delay", "3"], ["refresh", "--wait", "X", "--wait", "Y"],
                                  ["refresh", "--wait", "X", "--attempts", "0"],
                                  ["refresh", "--harvest-only"], ["refresh", "--dataverse-only"],
                                  ["refresh", "extra"]])
def test_refresh_usage_errors(fake, argv):
    assert tp(*argv).code == 2 and fake.calls == []


@pytest.mark.parametrize("exc, code", [(Misconfigured("missing configuration: X"), 3),
                                       (Refused("no"), 4), (Unreachable("down"), 5)])
def test_refresh_failures_map_to_their_class(fake, exc, code):
    fake.raises["refresh"] = exc
    assert tp("refresh").code == code


# ---------------------------------------------------------------- § 5 / the shape of ERR

def test_every_failure_starts_err_and_a_missing_configuration_never_prints_a_value(fake):
    fake.raises["list_entries"] = Misconfigured(
        "missing configuration: PROVIDER_TOKEN\n  Set it with:  /plugin configure billables")
    r = tp("list", "2026-08-12")
    assert r.err.splitlines()[0] == "ERR missing configuration: PROVIDER_TOKEN"
    assert r.code == 3


def test_the_gate_is_called_for_exactly_the_two_writes(fake):
    """`lookup`, `list` and `refresh` carry no gate: none of them reaches an adapter write."""
    fake.matches = MATCHES
    tp("lookup", "acm")
    tp("list", "2026-08-12")
    tp("refresh")
    assert fake.writes() == []

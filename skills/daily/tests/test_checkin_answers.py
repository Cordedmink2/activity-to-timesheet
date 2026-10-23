"""`checkin_answers.py`: the read-only reader of what the user said they were doing.

An answer is context, never a block (ADR-0009). This file pins the reader against fixtures
copied from the real watchers' event shapes: `aw-watcher-ask-away_<host>` (type `afktask`,
one event over the away gap, `data.message`) and `aw-watcher-ask_<host>` (point events,
`data.success`).
"""
from __future__ import annotations

import datetime as dt

import pytest

import checkin_answers as ca
from support import day, run_cli

DATE = dt.date(2026, 5, 28)


def run(d, *args):
    return run_cli(ca, [d.date_str(), "--utc-offset", d.offset, *args])


def worked(d):
    """A workday with one 40-minute break, the shape a work answer lands in."""
    return d.active("09:00", "12:00").afk("12:00", "12:40").active("12:40", "17:00")


def test_the_activity_source_unreachable_is_a_plain_refusal():
    r = run_cli(ca, ["2026-05-28", "--utc-offset", "12"])
    assert r.code == 1 and r.out == ""
    assert r.err.startswith("ERR") and "ActivityWatch unreachable" in r.err


def test_a_day_with_no_checkin_bucket_is_absent_not_a_failure(live_aw):
    d = worked(day())
    live_aw(d)
    r = run(d)
    assert r.code == 0, r.err
    out = r.json()
    assert out["status"] == "absent"
    assert out["questions"] == [] and out["hints"] == []


def test_the_fixture_matches_the_real_watcher_shape():
    """Copied from aw-watcher-ask-away 0.0.6 core.py: bucket `aw-watcher-ask-away_<host>`,
    event type `afktask`, one event over the gap, `data` = {"message": ...}."""
    d = worked(day(host="laptop.example")).checkin("12:00", "12:40", "call with ACME")
    assert "aw-watcher-ask-away_laptop.example" in d.buckets()
    [ev] = d.checkin_events()
    assert ev["data"] == {"message": "call with ACME"} and ev["duration"] == 40 * 60


def test_only_this_hosts_checkin_events_are_read(live_aw):
    d = worked(day(host="here.example")).checkin("12:00", "12:40", "call with ACME")
    buckets = d.buckets()
    other = day(host="old.example").checkin("12:00", "12:40", "call with BETA").buckets()
    buckets["aw-watcher-ask-away_old.example"] = other["aw-watcher-ask-away_old.example"]
    d.buckets = lambda: buckets  # type: ignore[method-assign]
    live_aw(d)
    out = run(d).json()
    assert out["host"] == "here.example"
    assert [e["words"] for e in out["answers"]] == ["call with ACME"]


def test_the_ask_reader_never_returns_a_checkin_event(live_aw):
    """`aw-watcher-ask` is a prefix of `aw-watcher-ask-away` (D4)."""
    d = worked(day()).checkin("12:00", "12:40", "call with ACME")
    live_aw(d)
    out = run(d).json()
    assert [e["source"] for e in out["answers"]] == ["checkin"]


def test_an_unanswered_ask_event_is_dropped(live_aw):
    d = worked(day()).ask("10:00", "", success=False).ask("11:00", "writing the ACME spec")
    live_aw(d)
    out = run(d).json()
    assert [e["words"] for e in out["answers"]] == ["writing the ACME spec"]
    assert out["answers"][0]["source"] == "ask"


def test_an_answer_across_local_midnight_is_clipped_to_the_day(live_aw):
    d = day(DATE, zone="Pacific/Auckland").active("20:00", "22:00").checkin("23:30", "24:30", "late call")
    live_aw(d)
    out = run_cli(ca, [d.date_str()]).json()
    [a] = out["answers"]
    assert (a["start"], a["end"]) == ("23:30:00", "00:00:00")

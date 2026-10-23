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


# --------------------------------------------------------------------------------------
# T4 - classify: personal, one client, several clients, no client
# --------------------------------------------------------------------------------------

TERMS = {"clients": [{"client": "ACME", "terms": ["acme"]},
                     {"client": "BETA", "terms": ["beta", "beta corp"]}],
         "exclusions": ["physio"]}


@pytest.mark.parametrize("words,cls,clients", [
    ("lunch", "personal", []),
    ("school run", "personal", []),
    ("physio appointment", "personal", []),          # the user's own exclusion
    ("", "personal", []),                            # dismissed
    ("   ", "personal", []),
    ("call with ACME", "work", ["ACME"]),
    ("call with ACME and BETA", "work", ["ACME", "BETA"]),   # E4
    ("meeting", "work", []),                         # work, no client
    ("lunch with ACME", "personal", []),             # D6: personal wins
    ("Lunch", "personal", []),                       # case-insensitive
    ("launch planning", "work", []),                 # whole words: not "lunch"
])
def test_classify(words, cls, clients):
    got = ca.classify(words, TERMS)
    assert (got["class"], got["clients"]) == (cls, clients)


def test_the_shipped_personal_list_names_no_client_or_person():
    assert "acme" not in " ".join(ca.PERSONAL_WORDS).lower()
    assert {"lunch", "school run", "coffee", "gym"} <= set(ca.PERSONAL_WORDS)


# --------------------------------------------------------------------------------------
# T5 / T6 / T8 - place each answer, rulings bind, off is settled
# --------------------------------------------------------------------------------------
import json  # noqa: E402

import afk_blocks as ab  # noqa: E402


def files(tmp_path, d, terms=TERMS, calendar=None, rulings=None):
    """The three inputs the agent hands the script, written as the skill's steps write them."""
    sk = ab.day_skeleton(d.afk_events(), d.window_events(), d.date, d.tz,
                         afk_bucket=f"aw-watcher-afk_{d.host}")
    paths = {"--skeleton": sk, "--terms": terms, "--calendar": calendar, "--rulings": rulings}
    args = []
    for flag, payload in paths.items():
        if payload is None:
            continue
        f = tmp_path / (flag.strip("-") + ".json")
        f.write_text(json.dumps(payload), encoding="utf-8")
        args += [flag, str(f)]
    return args


def cal(*events):
    return {"date": "2026-05-28", "events": [
        {"id": f"evt-{s}", "subject": subj, "start": f"{s}:00", "end": f"{e}:00",
         "corroborated": corr, "block": ({"start": f"{s}:00", "end": f"{e}:00"} if corr else None)}
        for s, e, subj, corr in events], "dropped": []}


def test_a_work_answer_over_a_break_is_one_question_and_never_a_block(live_aw, tmp_path):
    d = worked(day()).checkin("12:00", "12:40", "call with ACME")
    live_aw(d)
    out = run(d, *files(tmp_path, d)).json()
    assert out["questions"] == [{"start": "12:00:00", "end": "12:40:00", "words": "call with ACME",
                                 "clients": ["ACME"], "calendar": None}]
    assert out["hints"] == []
    assert "blocks" not in out and "block" not in json.dumps(out["questions"])


def test_one_question_cites_the_answer_and_an_uncorroborated_calendar_event(live_aw, tmp_path):
    """E1: the stretch overlaps a calendar event the machine could not corroborate."""
    d = worked(day()).checkin("12:00", "12:40", "meeting")
    live_aw(d)
    c = cal(("12:10", "12:30", "ACME sync", False))
    out = run(d, *files(tmp_path, d, calendar=c)).json()
    [q] = out["questions"]
    assert q["words"] == "meeting" and q["calendar"]["subject"] == "ACME sync"
    assert q["clients"] == []


def test_an_answer_inside_a_corroborated_calendar_block_is_context_only(live_aw, tmp_path):
    """E2: the calendar path already asks about it."""
    d = worked(day()).checkin("12:05", "12:35", "meeting")
    live_aw(d)
    c = cal(("12:00", "12:40", "ACME sync", True))
    out = run(d, *files(tmp_path, d, calendar=c)).json()
    assert out["questions"] == [] and out["hints"] == []
    assert out["answers"][0]["placement"] == "context"


def test_a_gap_shorter_than_the_break_threshold_is_a_hint_not_a_question(live_aw, tmp_path):
    """E3: a 10-minute away is no break, so the answer cannot explain one."""
    d = worked(day()).checkin("14:00", "14:10", "call with ACME")
    live_aw(d)
    out = run(d, *files(tmp_path, d)).json()
    assert out["questions"] == []
    assert [(h["words"], h["clients"]) for h in out["hints"]] == [("call with ACME", ["ACME"])]


def test_an_ask_answer_over_a_break_is_a_hint_only(live_aw, tmp_path):
    """D7: a point in time cannot explain a gap."""
    d = worked(day()).ask("12:20", "writing the ACME spec")
    live_aw(d)
    out = run(d, *files(tmp_path, d)).json()
    assert out["questions"] == []
    assert [h["source"] for h in out["hints"]] == ["ask"]


def test_an_answer_about_client_b_does_not_touch_the_skeleton_for_client_a(live_aw, tmp_path):
    d = worked(day()).checkin("14:00", "14:12", "BETA call")
    live_aw(d)
    out = run(d, *files(tmp_path, d)).json()
    assert out["questions"] == [] and out["hints"][0]["clients"] == ["BETA"]


def test_a_personal_answer_stays_a_break_with_no_question(live_aw, tmp_path):
    d = worked(day()).checkin("12:00", "12:40", "lunch with ACME")
    live_aw(d)
    out = run(d, *files(tmp_path, d)).json()
    assert out["questions"] == [] and out["hints"] == []
    assert out["answers"][0]["class"] == "personal"


def test_a_ruled_question_is_not_asked_again_even_if_the_words_changed(live_aw, tmp_path):
    d = (worked(day()).checkin("12:00", "12:40", "call with ACME"))
    live_aw(d)
    ruled = {"checkin_questions": [{"start": "12:00:00", "end": "12:40:00", "ruling": "yes",
                                    "words": "an older wording"}]}
    out = run(d, *files(tmp_path, d, rulings=ruled)).json()
    assert out["questions"] == []
    assert [(r["start"], r["end"], r["ruled"]) for r in out["ruled"]] == [("12:00:00", "12:40:00", "yes")]


def test_a_rulings_file_without_the_list_reads_without_error(live_aw, tmp_path):
    d = worked(day()).checkin("12:00", "12:40", "call with ACME")
    live_aw(d)
    out = run(d, *files(tmp_path, d, rulings={"blocks": []})).json()
    assert len(out["questions"]) == 1 and out["ruled"] == []


def test_the_script_writes_no_file(live_aw, tmp_path, monkeypatch):
    d = worked(day()).checkin("12:00", "12:40", "call with ACME")
    live_aw(d)
    args = files(tmp_path, d)
    before = sorted(p.name for p in tmp_path.iterdir())
    run(d, *args)
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_a_watcher_turned_off_is_settled_and_nothing_is_read(live_aw, tmp_path):
    d = worked(day()).checkin("12:00", "12:40", "call with ACME")
    srv = live_aw(d)
    off = {**TERMS, "off": ["checkin", "ask"]}
    r = run(d, *files(tmp_path, d, terms=off))
    assert r.code == 0 and r.json()["status"] == "off" and r.json()["questions"] == []
    assert not [q for q in srv.sent("GET", "/events")]


def test_an_empty_bucket_is_a_plain_empty_status(live_aw, tmp_path):
    d = worked(day())
    b = d.buckets()
    b[f"aw-watcher-ask-away_{d.host}"] = []
    d.buckets = lambda: b  # type: ignore[method-assign]
    live_aw(d)
    r = run(d, *files(tmp_path, d))
    assert r.code == 0 and r.json()["status"] == "empty"

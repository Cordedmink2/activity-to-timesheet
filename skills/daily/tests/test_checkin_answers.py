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


# --------------------------------------------------------------------------------------
# T7 - the skeleton cannot move
# --------------------------------------------------------------------------------------
import activity_timeline as at  # noqa: E402
import calendar_day as cdy  # noqa: E402


def test_the_skeleton_and_timeline_are_byte_identical_with_and_without_the_watchers(live_aw):
    plain = worked(day())
    with_answers = worked(day()).checkin("12:00", "12:40", "call with ACME").ask("10:00", "ACME spec")
    outputs = []
    for d in (plain, with_answers):
        with_srv = live_aw(d)
        outputs.append((run_cli(ab, [d.date_str(), "--utc-offset", d.offset]).out,
                        run_cli(ab, [d.date_str(), "--utc-offset", d.offset, "--json"]).out,
                        run_cli(at, [d.date_str(), "--utc-offset", d.offset]).out))
        del with_srv
    assert outputs[0] == outputs[1]


# --------------------------------------------------------------------------------------
# T9 - probe and diagnose, for setup
# --------------------------------------------------------------------------------------

def probe(*extra):
    return run_cli(ca, [*extra])


def test_probe_finds_this_hosts_checkin_bucket_and_its_newest_event(live_aw):
    d = worked(day()).checkin("12:00", "12:40", "call with ACME")
    srv = live_aw(d)
    r = probe("--probe", "checkin")
    assert r.code == 0, r.err
    out = r.json()
    assert out["found"] is True and out["bucket"] == "aw-watcher-ask-away_TESTHOST"
    assert out["newest_event"].startswith("2026-05-28T00:00")   # 12:00 at +12 is 00:00 UTC
    assert not srv.sent("POST") and not srv.sent("DELETE")


def test_probe_says_not_found_plainly(live_aw):
    live_aw(worked(day()))
    out = probe("--probe", "checkin").json()
    assert out["found"] is False and out["bucket"] is None


def test_probe_never_offers_the_checkin_bucket_for_the_ask_watcher(live_aw):
    live_aw(worked(day()).checkin("12:00", "12:40", "x"))
    assert probe("--probe", "ask").json()["found"] is False


def two_hosts(live_aw):
    a = worked(day(host="new.example"))
    b = worked(day(host="old.example"))
    buckets = {**b.buckets(), **a.buckets()}
    a.buckets = lambda: buckets  # type: ignore[method-assign]
    return live_aw(a, last_updated={"aw-watcher-afk_old.example": "2025-01-01T00:00:00+00:00",
                                    "aw-watcher-afk_new.example": "2026-05-28T04:00:00+00:00"})


def test_diagnose_names_the_two_host_afk_condition_and_the_stale_bucket(live_aw):
    srv = two_hosts(live_aw)
    out = probe("--diagnose").json()
    assert out["clean"] is False
    assert out["condition"] == "two-afk-buckets"
    assert out["buckets"] == ["aw-watcher-afk_new.example", "aw-watcher-afk_old.example"]
    assert out["stale"] == "aw-watcher-afk_old.example"
    assert any("export" in f.lower() for f in out["fixes"])
    assert not srv.sent("POST") and not srv.sent("DELETE")


def test_diagnose_over_one_host_is_clean(live_aw):
    live_aw(worked(day()))
    out = probe("--diagnose").json()
    assert out["clean"] is True and out["condition"] is None


# --------------------------------------------------------------------------------------
# T12 - answers stay on the machine and out of bug reports
# --------------------------------------------------------------------------------------
import ast  # noqa: E402
from pathlib import Path  # noqa: E402

SCRIPT_SRC = Path(ca.__file__).read_text(encoding="utf-8")


def test_the_report_redaction_list_names_check_in_answers():
    ref = (Path(ca.__file__).parents[1] / "references" / "reporting-issues.md").read_text(encoding="utf-8")
    assert "check-in answers" in ref.lower()


def test_the_reader_opens_no_file_for_writing_and_has_no_network_of_its_own():
    tree = ast.parse(SCRIPT_SRC)
    imported = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    imported |= {n.module.split(".")[0] for n in ast.walk(tree)
                 if isinstance(n, ast.ImportFrom) and n.module and n.level == 0}
    assert not imported & {"urllib", "socket", "http", "requests", "subprocess", "shutil"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "open":
            mode = node.args[1].value if len(node.args) > 1 and isinstance(node.args[1], ast.Constant) else "r"
            assert not set(str(mode)) & set("wax+"), "the reader must never write"

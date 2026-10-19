"""A category rule that used to match and now matches nothing (#99).

`category_rules.py --dormant <date>` asks the activity source's own `categorize`, over the
day and the days before it, which of the rules it holds labelled something lately and
labels nothing today. A renamed Edge profile, a site that changed its title or a code that
stopped being typed all look like this, and none of them errors: the client just stops
being recognised. The check reports and never rewrites — `.context.md` is the source of
truth and the rules are derived from it (ADR-0007).

The history is written on the target day's own clock with negative offsets (`-72:00` is
three days before midnight), so one `Day` carries a fortnight and the suite's real-server
mode serves it unchanged.
"""
from __future__ import annotations

import os
import sys

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS)
import category_rules as cr
from support import day, run_cli

ACME = ("msedge.exe", "Portal - [ACME] - Microsoft Edge")
BETA = ("Code.exe", "order.py - BetaShop - Visual Studio Code")
OTHER = ("explorer.exe", "Downloads")


def ruled():
    """A day whose activity source holds rules for Acme and Beta."""
    return (day(offset=0)
            .classify("Acme", r"\[ACME\]")
            .classify("Beta", "BetaShop"))


def at(d, start, end, window):
    return d.window(start, end, *window)


def dormant(date="2026-05-28", *extra):
    return run_cli(cr, ["--dormant", date, "--utc-offset", "0", *extra])


def test_a_rule_that_matched_days_ago_and_matches_nothing_today_is_flagged(live_aw):
    d = ruled()
    at(d, "-72:00", "-71:00", ACME)          # 2026-05-25
    at(d, "-71:00", "-70:00", BETA)
    at(d, "09:00", "10:00", BETA)            # today: Beta only
    at(d, "10:00", "11:00", OTHER)
    live_aw(d)
    result = dormant()
    assert result.code == 0, result.err
    lines = [l for l in result.out.splitlines() if l.startswith("DORMANT")]
    assert len(lines) == 1, result.out
    assert "Acme" in lines[0] and "2026-05-25" in lines[0]


def test_a_rule_that_matches_today_is_not_flagged(live_aw):
    d = ruled()
    at(d, "-72:00", "-71:00", ACME)
    at(d, "09:00", "10:00", ACME)
    at(d, "10:00", "11:00", BETA)
    live_aw(d)
    result = dormant()
    assert result.code == 0, result.err
    assert "DORMANT" not in result.out
    assert result.out.startswith("OK"), result.out


def test_the_last_day_named_is_the_most_recent_one_it_matched(live_aw):
    d = ruled()
    at(d, "-240:00", "-239:00", ACME)        # 2026-05-18
    at(d, "-48:00", "-47:00", ACME)          # 2026-05-26
    at(d, "09:00", "10:00", OTHER)
    live_aw(d)
    line = next(l for l in dormant().out.splitlines() if "Acme" in l)
    assert "2026-05-26" in line and "2026-05-18" not in line


def test_a_rule_that_never_matched_in_the_window_is_not_this_checks_to_report(live_aw):
    """A rule that matched nothing at all is the gate's `unverified` case at setup, not a
    rule that went quiet — flagging it every morning would be noise about a known state."""
    d = ruled()
    at(d, "-72:00", "-71:00", BETA)
    at(d, "09:00", "10:00", BETA)
    live_aw(d)
    assert "DORMANT" not in dormant().out


def test_a_match_older_than_the_lookback_is_not_counted(live_aw):
    d = ruled()
    at(d, "-480:00", "-479:00", ACME)        # 20 days back
    at(d, "09:00", "10:00", OTHER)
    live_aw(d)
    assert "DORMANT" not in dormant("2026-05-28", "--lookback", "14").out
    assert "DORMANT Acme" in dormant("2026-05-28", "--lookback", "21").out


def test_a_day_with_no_activity_flags_nothing_and_says_why(live_aw):
    """Every rule matches nothing on a day nobody worked; that is not every rule going dead."""
    d = ruled()
    at(d, "-72:00", "-71:00", ACME)
    live_aw(d)
    result = dormant()
    assert result.code == 0, result.err
    assert "DORMANT" not in result.out
    assert result.out.startswith("SKIP"), result.out


def test_a_nested_category_is_named_by_its_whole_path(live_aw):
    d = (day(offset=0).classify("Work", "WORKONLYNEVER")
         .classify("Work>Acme", r"\[ACME\]"))
    at(d, "-24:00", "-23:00", ACME)
    at(d, "09:00", "10:00", OTHER)
    live_aw(d)
    assert "DORMANT Work>Acme" in dormant().out


def test_it_writes_nothing(live_aw):
    d = ruled()
    at(d, "-72:00", "-71:00", ACME)
    at(d, "09:00", "10:00", OTHER)
    server = live_aw(d)
    dormant()
    assert not [r for r in server.requests if r["method"] == "POST"
                and r["path"] != "/api/0/query/"]


def test_a_bad_date_is_a_usage_error(live_aw):
    live_aw(ruled())
    result = dormant("28/05/2026")
    assert result.code == 2
    assert "YYYY-MM-DD" in result.err

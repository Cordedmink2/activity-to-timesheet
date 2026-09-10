"""The rule compiler, driven end to end through its command line (#71).

Every assertion here is about what crossed a boundary: what reached the fake activity
source, what the gate refused, what the verify reported, what landed in the workspace.
Nothing asserts on the shape of a rule object in flight — the point of splitting
composition from enforcement is that the enforcement is observable, and a test that read
the internals would go on passing after the write stopped happening.

The sample is read over a rolling window ending *now*, so a day built on the suite's usual
fixed date would fall outside it and every rule would be refused for matching nothing.
`SAMPLE_DAY` is two days back instead: comfortably inside the seven-day window at any hour
the suite runs, and comfortably in the past, which the fake's own range filter requires.
"""
from __future__ import annotations

import datetime as dt
import io
import json
import os
import sys
from pathlib import Path
from typing import Sequence

import pytest

SCRIPTS = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS)
import category_rules as cr
from support import CliResult, Day, day, run_cli

SAMPLE_DAY = dt.date.today() - dt.timedelta(days=2)

# A day of browser and editor windows, written in UTC because the sample is a rolling
# window in UTC and an offset would only put a conversion between the fixture and the range.
ACME_ITEM = ("msedge.exe", "ACM1234S Acme portal - acme.crm6.dynamics.com - [ACME]")
ACME_EDITOR = ("Code.exe", "compile.py - AcmePortal - Visual Studio Code")
BETA_TAG = ("msedge.exe", "Fabric order form - beta.example.com - [BETA]")
PERSONAL = ("msedge.exe", "Weather for Wellington - metservice.com")
TEAMS = ("Teams.exe", "Chat | Ana Client | Microsoft Teams")

# Every sample day carries these as well as whatever the test names, because a share is a
# fraction and a two-title day makes one match 50% — every good rule would be refused as
# over-broad, and the suite would be measuring its own fixture. Seven is enough that a rule
# matching one title lands well under the ceiling. They share the word `filler`, which is
# what the over-broad tests below match deliberately rather than by accident.
FILLER = [("explorer.exe", f"Downloads filler {n}") for n in range(7)]
BROAD = r"filler"


def sample_day(rows: list[tuple[str, str]],
               classes: Sequence[tuple[str, str]] = ()) -> Day:
    """A day whose window events are `rows` plus `FILLER`, one minute each, and whatever
    category rules the activity source already holds."""
    built = day(date=SAMPLE_DAY, offset=0)
    for index, (app, title) in enumerate(rows + FILLER):
        built.window(f"09:{index:02d}", f"09:{index + 1:02d}", app, title)
    for label, regex in classes:
        built.classify(label, regex)
    return built


def sampled(rows: list[tuple[str, str]]) -> int:
    """How many distinct titles a run over `rows` gates against."""
    return len(rows) + len(FILLER)


def candidate(client: str, signal: str, pattern: str) -> dict:
    return {"client": client, "signal": signal, "pattern": pattern}


def compile_run(tmp_path: Path, candidates: list[dict], *args) -> CliResult:
    """Run the compile mode with `candidates`, and return the CLI result."""
    path = tmp_path / "candidates.json"
    path.write_text(json.dumps(candidates), encoding="utf-8")
    return run_cli(cr, ["--candidates", str(path), *args])


def posted(server) -> list[dict]:
    """The `classes` list of the one settings write, or [] if there was none."""
    writes = server.sent("POST", "/settings/classes")
    assert len(writes) <= 1, "a run wrote the rule set more than once"
    return writes[0]["body"] if writes else []


def names(classes: list[dict]) -> list[str]:
    return [">".join(entry["name"]) for entry in classes]


# --------------------------------------------------------------------------------------
# The clean run
# --------------------------------------------------------------------------------------

def test_a_clean_run_writes_one_rule_per_candidate(live_aw, workspace, tmp_path):
    server = live_aw(sample_day([ACME_ITEM, ACME_EDITOR, BETA_TAG, PERSONAL]))
    result = compile_run(tmp_path, [
        candidate("Acme", "work_item_prefix", r"ACM\d{3,}S?"),
        candidate("Beta", "profile_tag", r"\[BETA\]"),
    ])
    assert result.code == 0, result.err
    assert names(posted(server)) == ["Acme", "Beta"]


def test_the_rule_written_for_a_scoped_signal_is_confined_to_that_application(
        live_aw, workspace, tmp_path):
    """#69 story 11. The timeline matches a rule against the window's app name *and* its
    title, so a signal that only means something in a browser is anchored on one — a
    client's name in an editor's window title is about the code, not about the page."""
    server = live_aw(sample_day([ACME_ITEM, PERSONAL]))
    result = compile_run(tmp_path, [candidate("Acme", "url_host", r"acme\.crm6\.dynamics\.com")])
    assert result.code == 0, result.err
    (written,) = posted(server)
    assert written["rule"]["regex"].startswith("^(?:msedge|microsoft edge|chrome")
    assert r"acme\.crm6\.dynamics\.com" in written["rule"]["regex"]
    assert written["rule"]["ignore_case"] is True


def test_the_run_reports_the_sample_it_gated_against(live_aw, workspace, tmp_path):
    """A run that refused a rule and never said what it was judged against leaves the user
    arguing with a number they cannot see."""
    live_aw(sample_day([ACME_ITEM, PERSONAL, TEAMS]))
    result = compile_run(tmp_path, [candidate("Acme", "work_item_prefix", r"ACM\d{3,}S?")])
    assert f"SAMPLE {sampled([ACME_ITEM, PERSONAL, TEAMS])} titles" in result.out


# --------------------------------------------------------------------------------------
# The gate
# --------------------------------------------------------------------------------------

def test_a_pattern_that_does_not_compile_is_refused_and_nothing_is_written(
        live_aw, workspace, tmp_path):
    server = live_aw(sample_day([ACME_ITEM, PERSONAL]))
    result = compile_run(tmp_path, [
        candidate("Acme", "work_item_prefix", r"ACM\d{3,}S?"),
        candidate("Beta", "title_token", "Fabric(order"),
    ])
    assert result.code == 1
    assert "does not compile" in result.out
    assert posted(server) == [], "a refusal anywhere has to write nothing at all"


def test_a_pattern_matching_none_of_the_sample_is_refused(live_aw, workspace, tmp_path):
    """A rule that matches nothing leaves that client's whole day uncategorized, and does
    it silently — which is the failure the whole gate exists for."""
    server = live_aw(sample_day([ACME_ITEM, PERSONAL]))
    result = compile_run(tmp_path, [candidate("Gamma", "profile_tag", r"\[GAMMA\]")])
    assert result.code == 1
    assert f"matches none of the {sampled([ACME_ITEM, PERSONAL])} sampled titles" in result.out
    assert posted(server) == []


def test_a_pattern_matching_an_implausible_share_is_refused(live_aw, workspace, tmp_path):
    """The measured case: a bare-word rule matching 256 of 552 browser titles in a day.
    First-match-wins makes that worse than noise — it takes the label off a correct rule."""
    server = live_aw(sample_day([ACME_ITEM, BETA_TAG, PERSONAL, TEAMS]))
    result = compile_run(tmp_path, [candidate("Acme", "title_token", BROAD)])
    assert result.code == 1
    assert "over the 35% ceiling" in result.out
    assert posted(server) == []


def test_the_ceiling_is_a_flag_because_it_is_a_judgement(live_aw, workspace, tmp_path):
    """A one-client consultant legitimately runs hotter than a five-client one, so the
    share that is implausible is theirs to say — the gate stays, the number moves."""
    server = live_aw(sample_day([ACME_ITEM, BETA_TAG, PERSONAL, TEAMS]))
    result = compile_run(tmp_path, [candidate("Acme", "title_token", BROAD)],
                         "--max-share", "0.99")
    assert result.code == 0, result.err
    assert names(posted(server)) == ["Acme"]


def test_a_rule_that_is_only_the_clients_name_is_refused(live_aw, workspace, tmp_path):
    """#69: "a rule that is only the client's name is never produced". Enforced here rather
    than asked for in prose, because composition is the varying part of this feature."""
    server = live_aw(sample_day([ACME_ITEM, PERSONAL]))
    result = compile_run(tmp_path, [candidate("Acme", "title_token", r"\bAcme\b")])
    assert result.code == 1
    assert "only the client's name" in result.out
    assert posted(server) == []


def test_an_unknown_signal_type_is_refused_by_name(live_aw, workspace, tmp_path):
    live_aw(sample_day([ACME_ITEM, PERSONAL]))
    result = compile_run(tmp_path, [candidate("Acme", "vibes", r"ACM\d{3,}")])
    assert result.code == 1
    assert "unknown signal type 'vibes'" in result.out


def test_a_signal_that_cannot_reach_a_window_title_is_skipped_not_refused(
        live_aw, workspace, tmp_path):
    """A repo path is a real signal and a legitimate `.context.md` entry; it just never
    reaches a title. Refusing it would send a run back to rewrite something that is right,
    so it is dropped with the reason said out loud — and the client's other rule still
    lands."""
    server = live_aw(sample_day([ACME_ITEM, ACME_EDITOR, PERSONAL]))
    result = compile_run(tmp_path, [
        candidate("Acme", "repo_path", r"C:\\src\\acme-portal"),
        candidate("Acme", "editor_workspace", r"AcmePortal"),
    ])
    assert result.code == 0, result.err
    assert "SKIP Acme repo_path" in result.out
    assert len(posted(server)) == 1, "only the title-visible signal compiles"


# --------------------------------------------------------------------------------------
# The order
# --------------------------------------------------------------------------------------

def test_rules_are_written_in_signal_rank_order_however_the_candidates_arrive(
        live_aw, workspace, tmp_path):
    """The profile tag is deliberately last: it is the fallback for browser time carrying
    no other evidence, and the first matching rule wins."""
    server = live_aw(sample_day([ACME_ITEM, ACME_EDITOR, BETA_TAG, PERSONAL]))
    result = compile_run(tmp_path, [
        candidate("Acme", "profile_tag", r"\[ACME\]"),
        candidate("Beta", "editor_workspace", r"AcmePortal"),
        candidate("Gamma", "work_item_prefix", r"ACM\d{3,}S?"),
    ])
    assert result.code == 0, result.err
    assert names(posted(server)) == ["Gamma", "Beta", "Acme"]


# --------------------------------------------------------------------------------------
# What the write does to what was already there
# --------------------------------------------------------------------------------------

def test_rules_the_plugin_did_not_author_survive_a_write(live_aw, workspace, tmp_path):
    """Trusting the plugin with configuration it did not create is the whole of #69's
    story 7. A user's own category is kept verbatim, and after the rules this run wrote —
    so the specific evidence still outranks it."""
    server = live_aw(sample_day([ACME_ITEM, PERSONAL],
                                classes=[("Personal", r"metservice"),
                                         ("Grouping", r"")]))
    result = compile_run(tmp_path, [candidate("Acme", "work_item_prefix", r"ACM\d{3,}S?")])
    assert result.code == 0, result.err
    assert names(posted(server)) == ["Acme", "Personal", "Grouping"]
    assert "2 rules left as they were" in result.out


def test_a_rebuild_replaces_this_plugins_own_rule_rather_than_adding_a_second(
        live_aw, workspace, tmp_path):
    """The context file is the source of truth and the rules are a derived copy, so writing
    them twice has to leave one copy — otherwise every rebuild doubles the rule set."""
    server = live_aw(sample_day([ACME_ITEM, PERSONAL],
                                classes=[("Acme", r"\[ACME\]")]))
    result = compile_run(tmp_path, [candidate("Acme", "work_item_prefix", r"ACM\d{3,}S?")])
    assert result.code == 0, result.err
    assert names(posted(server)) == ["Acme"]


# --------------------------------------------------------------------------------------
# The backup
# --------------------------------------------------------------------------------------

def backups(workspace: Path) -> list[Path]:
    return sorted((workspace / ".mcp").glob("aw-categories-*.json"))


def test_the_previous_rule_set_is_copied_into_the_workspace_before_the_write(
        live_aw, workspace, tmp_path):
    """The recovery path, and what makes the write safe to perform without showing the user
    a diff. It holds what was there *before*, which is the only version worth having."""
    live_aw(sample_day([ACME_ITEM, PERSONAL], classes=[("Personal", r"metservice")]))
    result = compile_run(tmp_path, [candidate("Acme", "work_item_prefix", r"ACM\d{3,}S?")])
    assert result.code == 0, result.err
    (backup,) = backups(workspace)
    assert names(json.loads(backup.read_text(encoding="utf-8"))["classes"]) == ["Personal"]
    assert str(backup) in result.out, "a run that does not print where the backup went "\
                                      "leaves the user to find it at recovery time"


def test_a_refused_run_leaves_no_backup_because_it_never_reached_a_write(
        live_aw, workspace, tmp_path):
    live_aw(sample_day([ACME_ITEM, PERSONAL]))
    compile_run(tmp_path, [candidate("Gamma", "profile_tag", r"\[GAMMA\]")])
    assert backups(workspace) == []


# --------------------------------------------------------------------------------------
# The endpoint that is not there, and the one that says no
# --------------------------------------------------------------------------------------

def test_an_absent_settings_endpoint_is_refused_in_words_rather_than_a_traceback(
        live_aw, workspace, tmp_path):
    """The older build the `setup` skill has a manual fallback for. A traceback here sends
    a run debugging the script instead of taking the route that works."""
    live_aw(sample_day([ACME_ITEM, PERSONAL]), settings_status=404)
    result = compile_run(tmp_path, [candidate("Acme", "work_item_prefix", r"ACM\d{3,}S?")])
    assert result.code == 1
    assert "ERR" in result.err and "by hand" in result.err
    assert "Traceback" not in result.err


def test_an_error_on_the_write_is_reported_and_names_the_backup(
        live_aw, workspace, tmp_path):
    """Swallowed, this is the worst outcome in the feature: a run that reports the rules
    configured when nothing landed."""
    live_aw(sample_day([ACME_ITEM, PERSONAL]), write_status=500)
    result = compile_run(tmp_path, [candidate("Acme", "work_item_prefix", r"ACM\d{3,}S?")])
    assert result.code == 1
    assert "refused the write" in result.err
    (backup,) = backups(workspace)
    assert str(backup) in result.err


# --------------------------------------------------------------------------------------
# The verify
# --------------------------------------------------------------------------------------

def test_the_run_reads_the_rules_back_and_says_what_each_matched(
        live_aw, workspace, tmp_path):
    server = live_aw(sample_day([ACME_ITEM, ACME_EDITOR, BETA_TAG, PERSONAL]))
    result = compile_run(tmp_path, [
        candidate("Acme", "work_item_prefix", r"ACM\d{3,}S?"),
        candidate("Beta", "profile_tag", r"\[BETA\]"),
    ])
    assert result.code == 0, result.err
    total = sampled([ACME_ITEM, ACME_EDITOR, BETA_TAG, PERSONAL])
    assert f"VERIFY Acme work_item_prefix — 1 of {total} sampled titles" in result.out
    assert f"VERIFY Beta profile_tag — 1 of {total} sampled titles" in result.out
    assert len(server.sent("GET", "/settings")) >= 2, (
        "the rules have to be read *back* after the write, not assumed from what was sent")


def test_a_write_the_server_accepted_and_did_not_keep_fails_the_verify(
        live_aw, workspace, tmp_path, monkeypatch):
    """The gate has already refused a rule that matches nothing, so a rule missing at this
    point is a write that did not land — which is the difference between a configured
    install and one that only looks configured."""
    live_aw(sample_day([ACME_ITEM, PERSONAL]))
    monkeypatch.setattr(cr, "post_setting", lambda key, value: None)
    result = compile_run(tmp_path, [candidate("Acme", "work_item_prefix", r"ACM\d{3,}S?")])
    assert result.code == 1
    assert "did not land" in result.err


# --------------------------------------------------------------------------------------
# Reading what is there: the inspect mode adoption is built on
# --------------------------------------------------------------------------------------

def test_inspect_reports_every_rule_with_the_share_it_matches(live_aw, workspace):
    server = live_aw(sample_day([ACME_ITEM, BETA_TAG, PERSONAL, TEAMS],
                                classes=[("Acme", r"\[ACME\]"), ("Everything", BROAD)]))
    result = run_cli(cr, ["--inspect"])
    assert result.code == 0, result.err
    total = sampled([ACME_ITEM, BETA_TAG, PERSONAL, TEAMS])
    assert f"RULE Acme [unmanaged] — 1 of {total} titles" in result.out
    assert "OVER the 35% ceiling" in result.out
    assert posted(server) == [], "--inspect writes nothing"


def test_inspect_shows_an_example_of_what_a_rule_matched(live_aw, workspace):
    """What makes a rule mappable to a client by a reader: the name usually says it, and
    where it does not, the titles it caught do."""
    live_aw(sample_day([ACME_ITEM, PERSONAL], classes=[("Legacy", r"\[ACME\]")]))
    result = run_cli(cr, ["--inspect"])
    assert "e.g. msedge.exe ACM1234S Acme portal" in result.out


def test_inspect_names_a_grouping_category_rather_than_erroring_on_it(live_aw, workspace):
    """A parent category carries `{"type": "none"}` and no regex at all — reaching for a
    field that is not there is what turns a healthy configuration into an error."""
    built = sample_day([ACME_ITEM, PERSONAL])
    built.classes.append({"name": ["Work"], "rule": {"type": "none"}})
    live_aw(built)
    result = run_cli(cr, ["--inspect"])
    assert result.code == 0, result.err
    assert "RULE Work [unmanaged] — no regex" in result.out


# --------------------------------------------------------------------------------------
# Adopting the rules a user already had (#73)
# --------------------------------------------------------------------------------------

def test_a_rule_this_plugin_wrote_reads_back_as_managed_and_the_users_own_does_not(
        live_aw, workspace, tmp_path):
    """Which rules are up for adoption is a mechanical question, not a judgement — the run
    that writes a rule records the client it wrote it for, and everything else the activity
    source holds is the user's own."""
    live_aw(sample_day([ACME_ITEM, PERSONAL], classes=[("Personal", r"metservice")]))
    assert compile_run(tmp_path, [
        candidate("Acme", "work_item_prefix", r"ACM\d{3,}S?")]).code == 0
    result = run_cli(cr, ["--inspect"])
    assert "RULE Acme [managed]" in result.out
    assert "RULE Personal [unmanaged]" in result.out


def test_adopting_a_rule_makes_it_managed_and_leaves_one_copy(live_aw, workspace, tmp_path):
    """The user accepts the mapping, the rule is compiled from the signals behind it like
    any other, and from then on a rebuild regenerates it rather than leaving it beside the
    managed set."""
    server = live_aw(sample_day([ACME_ITEM, PERSONAL],
                                classes=[("Acme", r"acme"), ("Personal", r"metservice")]))
    result = compile_run(tmp_path, [candidate("Acme", "work_item_prefix", r"ACM\d{3,}S?")])
    assert result.code == 0, result.err
    assert names(posted(server)) == ["Acme", "Personal"], "one Acme rule, not two"
    assert "RULE Acme [managed]" in run_cli(cr, ["--inspect"]).out


def test_skipping_adoption_leaves_an_unmanaged_rule_byte_for_byte(
        live_aw, workspace, tmp_path):
    """#69 story 7: nothing of the user's is silently overwritten. Asserted on the whole
    entry rather than its name, because an `id` quietly renumbered is the same breach — the
    settings dialog they made it in is keyed on that."""
    theirs = {"id": 12, "name": ["Personal"],
              "rule": {"type": "regex", "regex": "metservice", "ignore_case": False}}
    built = sample_day([ACME_ITEM, PERSONAL])
    built.classes.append(theirs)
    server = live_aw(built)
    result = compile_run(tmp_path, [candidate("Acme", "work_item_prefix", r"ACM\d{3,}S?")])
    assert result.code == 0, result.err
    assert theirs in posted(server)


def test_a_new_rule_does_not_take_an_id_an_unmanaged_rule_is_already_using(
        live_aw, workspace, tmp_path):
    built = sample_day([ACME_ITEM, PERSONAL])
    built.classes.append({"id": 12, "name": ["Personal"],
                          "rule": {"type": "regex", "regex": "metservice"}})
    server = live_aw(built)
    compile_run(tmp_path, [candidate("Acme", "work_item_prefix", r"ACM\d{3,}S?")])
    written = posted(server)
    assert len({entry["id"] for entry in written}) == len(written)


def test_an_over_broad_rule_of_the_users_own_is_surfaced_for_correction(
        live_aw, workspace):
    """Adoption is where an over-broad rule gets fixed rather than merely reported: the
    measured case takes the label off a correct rule, so it is worth the one question."""
    live_aw(sample_day([ACME_ITEM, PERSONAL], classes=[("Everything", BROAD)]))
    result = run_cli(cr, ["--inspect"])
    assert "RULE Everything [unmanaged]" in result.out
    assert "OVER the 35% ceiling" in result.out


# --------------------------------------------------------------------------------------
# Staleness: the rules are a derived copy, so the copy is rebuilt when the source moves (#74)
# --------------------------------------------------------------------------------------

def context_file(workspace: Path, text: str = "### Acme\n- `ACM` in a title\n") -> Path:
    path = workspace / "Timesheets" / ".context.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_status_is_stale_before_this_plugin_has_ever_written_the_rules(workspace):
    context_file(workspace)
    result = run_cli(cr, ["--status"])
    assert result.code == 0
    assert result.out.startswith("STALE")


def test_status_is_current_straight_after_a_write(live_aw, workspace, tmp_path):
    context_file(workspace)
    live_aw(sample_day([ACME_ITEM, PERSONAL]))
    assert compile_run(tmp_path, [
        candidate("Acme", "work_item_prefix", r"ACM\d{3,}S?")]).code == 0
    assert run_cli(cr, ["--status"]).out.startswith("CURRENT")


def test_a_hand_edit_to_the_context_file_makes_the_rules_stale(
        live_aw, workspace, tmp_path):
    """The edit made outside a run is the one nothing else would notice: the user adds a
    client on Friday and Monday's timesheet is drafted against rules that never heard of
    them."""
    context_file(workspace)
    live_aw(sample_day([ACME_ITEM, PERSONAL]))
    compile_run(tmp_path, [candidate("Acme", "work_item_prefix", r"ACM\d{3,}S?")])
    context_file(workspace, "### Acme\n- `ACM` in a title\n\n### Beta\n- `BET` in a title\n")
    result = run_cli(cr, ["--status"])
    assert result.out.startswith("STALE")
    assert "has changed since the rules were written" in result.out


def test_status_reads_no_activity_source_at_all(live_aw, workspace, tmp_path):
    """A run pays for this at the start of every day, so it has to be two local file reads.
    It is also what keeps the rule "a run whose context file has not changed does not write"
    true without anything having to remember it."""
    context_file(workspace)
    server = live_aw(sample_day([ACME_ITEM, PERSONAL]))
    compile_run(tmp_path, [candidate("Acme", "work_item_prefix", r"ACM\d{3,}S?")])
    before = len(server.requests)
    assert run_cli(cr, ["--status"]).out.startswith("CURRENT")
    assert len(server.requests) == before, "--status touched the activity source"


def test_a_workspace_with_no_context_file_is_stale_rather_than_current(workspace):
    """There is nothing to build rules from, which is a state to act on — the `daily`
    skill's first run scaffolds that file — and not a run to report as up to date."""
    result = run_cli(cr, ["--status"])
    assert result.code == 0
    assert result.out.startswith("STALE")


def test_a_rebuild_is_gated_exactly_as_the_first_write_was(live_aw, workspace, tmp_path):
    """The rebuild rides inside an approval the user has already given, so the only thing
    standing between a mistyped signal and their timesheet is this gate."""
    context_file(workspace)
    server = live_aw(sample_day([ACME_ITEM, PERSONAL]))
    compile_run(tmp_path, [candidate("Acme", "work_item_prefix", r"ACM\d{3,}S?")])
    result = compile_run(tmp_path, [
        candidate("Acme", "work_item_prefix", r"ACM\d{3,}S?"),
        candidate("Beta", "profile_tag", r"\[NOPE\]"),
    ])
    assert result.code == 1
    assert len(server.sent("POST", "/settings/classes")) == 1, (
        "the refused rebuild wrote anyway — the first write is the only one that landed")


# --------------------------------------------------------------------------------------
# The command line itself
# --------------------------------------------------------------------------------------

def test_the_candidates_can_arrive_on_stdin(live_aw, workspace, monkeypatch):
    """A run composing candidates has them in hand, not in a file; making it write one
    first is a step that can fail on a read-only or unexpected working directory."""
    server = live_aw(sample_day([ACME_ITEM, PERSONAL]))
    monkeypatch.setattr(
        sys, "stdin",
        io.StringIO(json.dumps([candidate("Acme", "work_item_prefix", r"ACM\d{3,}S?")])))
    result = run_cli(cr, ["--candidates", "-"])
    assert result.code == 0, result.err
    assert names(posted(server)) == ["Acme"]


@pytest.mark.parametrize("args", [[], ["--inspect", "--status"],
                                  ["--candidates", "x.json", "--inspect"]])
def test_exactly_one_mode_has_to_be_asked_for(args):
    result = run_cli(cr, args)
    assert result.code == 2
    assert "exactly one" in result.err


def test_a_workspace_that_cannot_hold_the_backup_is_refused_as_itself(live_aw, tmp_path):
    """Not as "ActivityWatch unreachable", which is what a `URLError`-shaped catch of every
    `OSError` would have called it — sending whoever read it to restart a service that was
    never the problem. The backup is the recovery path, so a run that cannot write one
    writes nothing at all."""
    root = tmp_path / "ws"
    root.mkdir()
    (root / ".mcp").write_text("a file where the state directory goes", encoding="utf-8")
    server = live_aw(sample_day([ACME_ITEM, PERSONAL]))
    result = compile_run(tmp_path, [candidate("Acme", "work_item_prefix", r"ACM\d{3,}S?")],
                         "--workspace", str(root))
    assert result.code == 1
    assert "cannot keep the backup" in result.err
    assert "unreachable" not in result.err
    assert posted(server) == []


def test_a_sample_with_nothing_in_it_refuses_rather_than_writing_unjudged_rules(
        live_aw, workspace, tmp_path):
    """A day with no window events is not a day on which every rule is fine."""
    live_aw(day(date=SAMPLE_DAY, offset=0).window("09:00", "09:01", "x", "y"))
    result = compile_run(tmp_path, [candidate("Acme", "work_item_prefix", r"ACM\d{3,}S?")],
                         "--days", "0")
    assert result.code == 1
    assert "nothing to test a category rule against" in result.err

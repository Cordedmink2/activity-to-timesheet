"""The rule compiler, driven end to end through its command line (#71).

Every assertion here is about what crossed a boundary: what reached the fake activity
source, what the gate refused, what the verify reported, what landed in the workspace.
Nothing asserts on the shape of a rule object in flight — the point of splitting
the choice of terms from enforcement is that the enforcement is observable, and a test that
read the internals would go on passing after the write stopped happening.

Whether a written rule labels anything is asked of the fake's `/query/`, which matches the
way ActivityWatch does — each field on its own (`support.aw_rule_matches`). The compiler's
own matcher once agreed with itself about rules the real server never matched, so no test
here takes the compiler's word for it.

The sample is read over a rolling window ending *now*, so a day built on the suite's usual
fixed date would fall outside it and every rule would match nothing. `SAMPLE_DAY` is two
days back instead: comfortably inside the seven-day window at any hour the suite runs, and
comfortably in the past, which the fake's own range filter requires.
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
from support import CliResult, Day, aw_rule_matches, day, run_cli

SAMPLE_DAY = dt.date.today() - dt.timedelta(days=2)

# A day of browser, editor and Teams windows, written in UTC because the sample is a rolling
# window in UTC and an offset would only put a conversion between the fixture and the range.
EDGE = " - Microsoft​ Edge"
ACME_PAGE = ("msedge.exe", f"Acme portal-acme.crm6.dynamics.com/main - [ACME] - Acme - Dana{EDGE}")
ACME_EDITOR = ("Code.exe", "compile.py - AcmePortal - Visual Studio Code")
BETA_PAGE = ("msedge.exe", f"Fabric order form-beta.example.com - [BETA] - Work{EDGE}")
PERSONAL = ("msedge.exe", f"Weather for Wellington-metservice.com - Personal{EDGE}")
TEAMS = ("ms-teams.exe", "Chat | Ana Client | Microsoft Teams")

# Every sample day carries these as well as whatever the test names, because a share is a
# fraction and a two-title day makes one match 50% — every good term would be refused as
# over-broad, and the suite would be measuring its own fixture. They share the word
# `filler`, which is what the over-broad tests below match deliberately.
FILLER = ([("msedge.exe", f"Downloads filler {n}{EDGE}") for n in range(7)]
          + [("Code.exe", f"filler{n}.py - Scratch - Visual Studio Code") for n in range(3)])
BROAD = "filler"


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


def candidate(client: str, *terms: str) -> dict:
    return {"client": client, "terms": list(terms)}


ACME = candidate("Acme", "ACME", "AcmePortal")
BETA = candidate("Beta", "BETA")


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


def labels(entry: dict, window: tuple[str, str]) -> bool:
    """Whether ActivityWatch would put this window under this class."""
    return aw_rule_matches(entry["rule"], {"app": window[0], "title": window[1]})


# --------------------------------------------------------------------------------------
# The clean run
# --------------------------------------------------------------------------------------

def test_a_clean_run_writes_one_rule_per_client(live_aw, workspace, tmp_path):
    server = live_aw(sample_day([ACME_PAGE, ACME_EDITOR, BETA_PAGE, PERSONAL]))
    result = compile_run(tmp_path, [ACME, BETA])
    assert result.code == 0, result.err
    assert names(posted(server)) == ["Acme", "Beta"]


def test_a_written_rule_labels_its_windows_the_way_activitywatch_matches_them(
        live_aw, workspace, tmp_path):
    """The regression. Rules anchored on the app name and matching a term in the title were
    gated and verified against the two fields joined, so every check passed — and
    ActivityWatch, which matches each field on its own, labelled 0.01h of 12.23h with them."""
    server = live_aw(sample_day([ACME_PAGE, ACME_EDITOR, TEAMS, PERSONAL]))
    result = compile_run(tmp_path, [candidate("Acme", "ACME", "AcmePortal", "Ana Client")])
    assert result.code == 0, result.err
    (written,) = posted(server)
    assert all(labels(written, window) for window in (ACME_PAGE, ACME_EDITOR, TEAMS))
    assert not labels(written, PERSONAL)
    assert written["rule"]["ignore_case"] is True


def test_the_clients_own_name_is_a_term_and_is_written(live_aw, workspace, tmp_path):
    """The client code is the best evidence there is: the profile tag carries it, a profile
    named for the client carries it, and so does the workspace the user opened for them.
    Refusing it forced the run to invent weaker evidence instead."""
    server = live_aw(sample_day([ACME_PAGE, PERSONAL]))
    result = compile_run(tmp_path, [candidate("Acme", "Acme")])
    assert result.code == 0, result.err
    assert names(posted(server)) == ["Acme"]


def test_a_term_is_literal_so_its_punctuation_matches_itself(live_aw, workspace, tmp_path):
    """A term is a word the user uses, not a pattern: `acme.crm6` must not match `acmeXcrm6`."""
    lookalike = ("msedge.exe", f"acmeXcrm6 notes - Work{EDGE}")
    server = live_aw(sample_day([ACME_PAGE, lookalike, PERSONAL]))
    assert compile_run(tmp_path, [candidate("Acme", "acme.crm6")]).code == 0
    (written,) = posted(server)
    assert labels(written, ACME_PAGE) and not labels(written, lookalike)


def test_the_run_reports_the_sample_it_gated_against(live_aw, workspace, tmp_path):
    """A run that refused a rule and never said what it was judged against leaves the user
    arguing with a number they cannot see."""
    live_aw(sample_day([ACME_PAGE, PERSONAL, TEAMS]))
    result = compile_run(tmp_path, [ACME])
    assert f"SAMPLE {sampled([ACME_PAGE, PERSONAL, TEAMS])} titles" in result.out


# --------------------------------------------------------------------------------------
# The gate
# --------------------------------------------------------------------------------------

def test_a_client_with_more_terms_than_a_curated_list_is_refused(live_aw, workspace, tmp_path):
    server = live_aw(sample_day([ACME_PAGE, PERSONAL]))
    result = compile_run(tmp_path, [candidate("Acme", *[f"acme{n}" for n in range(6)])])
    assert result.code == 1
    assert "over the 5 a client's rule takes" in result.out
    assert posted(server) == [], "a refusal anywhere has to write nothing at all"


@pytest.mark.parametrize("bad", [{"client": "Acme"}, {"client": "Acme", "terms": []},
                                 {"client": "Acme", "terms": ["ACME", " "]},
                                 {"client": "Acme", "terms": "ACME"},
                                 {"client": "", "terms": ["ACME"]}])
def test_a_candidate_without_usable_terms_is_refused(live_aw, workspace, tmp_path, bad):
    server = live_aw(sample_day([ACME_PAGE, PERSONAL]))
    result = compile_run(tmp_path, [bad])
    assert result.code == 1
    assert "REFUSE" in result.out
    assert posted(server) == []


def test_a_client_named_twice_is_refused_because_its_terms_are_one_rule(
        live_aw, workspace, tmp_path):
    live_aw(sample_day([ACME_PAGE, PERSONAL]))
    result = compile_run(tmp_path, [candidate("Acme", "ACME"), candidate("Acme", "AcmePortal")])
    assert result.code == 1
    assert "one candidate per client" in result.err


def test_a_client_not_worked_on_in_the_window_does_not_block_the_rest(
        live_aw, workspace, tmp_path):
    """Every declared client is passed on a rebuild, and one with no work in the window
    matches nothing however right its terms are. Refused, it vetoed every rebuild until its
    work happened to come back; written, it mislabels nothing, since it matches nothing."""
    server = live_aw(sample_day([ACME_PAGE, PERSONAL]))
    result = compile_run(tmp_path, [ACME, candidate("Gamma", "GAMMA")])
    assert result.code == 0, result.err
    assert names(posted(server)) == ["Acme", "Gamma"]
    assert "UNVERIFIED Gamma 'GAMMA' — dormant" in result.out


def test_a_silent_term_of_a_client_that_was_worked_on_is_called_suspect(
        live_aw, workspace, tmp_path):
    """The case the zero-match refusal was for — a mistyped code, a product never opened —
    shows as a client whose other terms matched and this one did not. Written rather than
    refused, and named so a run can send the user to fix it, with the tags really seen."""
    server = live_aw(sample_day([ACME_PAGE, PERSONAL]))
    result = compile_run(tmp_path, [candidate("Acme", "ACME", "ACMEE-X")])
    assert result.code == 0, result.err
    assert names(posted(server)) == ["Acme"]
    assert "UNVERIFIED Acme 'ACMEE-X' — suspect" in result.out
    assert "SEEN [ACME]" in result.out


def test_a_run_whose_terms_all_matched_lists_no_profile_tags(live_aw, workspace, tmp_path):
    live_aw(sample_day([ACME_PAGE, PERSONAL]))
    result = compile_run(tmp_path, [candidate("Acme", "ACME")])
    assert result.code == 0, result.err
    assert "SEEN" not in result.out


def test_a_term_matching_an_implausible_share_is_refused(live_aw, workspace, tmp_path):
    """The measured case: a bare-word rule matching 256 of 552 browser titles in a day.
    First-match-wins makes that worse than noise — it takes the label off a correct rule."""
    server = live_aw(sample_day([ACME_PAGE, BETA_PAGE, PERSONAL, TEAMS]))
    result = compile_run(tmp_path, [candidate("Acme", "ACME", BROAD)])
    assert result.code == 1
    assert f"'{BROAD}' matches" in result.out and "over the 35% ceiling" in result.out
    assert posted(server) == []


def test_the_ceiling_is_a_flag_because_it_is_a_judgement(live_aw, workspace, tmp_path):
    """A one-client consultant legitimately runs hotter than a five-client one, so the
    share that is implausible is theirs to say — the gate stays, the number moves."""
    server = live_aw(sample_day([ACME_PAGE, BETA_PAGE, PERSONAL, TEAMS]))
    result = compile_run(tmp_path, [candidate("Acme", BROAD)], "--max-share", "0.99")
    assert result.code == 0, result.err
    assert names(posted(server)) == ["Acme"]


def test_two_clients_matching_the_same_titles_are_reported_and_the_first_takes_them(
        live_aw, workspace, tmp_path):
    """A term two clients share gives one client's time to the other. Named so a run can
    drop it; written, because one title mentioning both must not veto every rebuild."""
    server = live_aw(sample_day([ACME_PAGE, BETA_PAGE, PERSONAL]))
    result = compile_run(tmp_path, [candidate("Acme", "ACME", "Fabric"), BETA])
    assert result.code == 0, result.err
    assert "OVERLAP Acme and Beta — both match 1 title, which go to Acme" in result.out
    assert names(posted(server)) == ["Acme", "Beta"]


# --------------------------------------------------------------------------------------
# What the write does to what was already there
# --------------------------------------------------------------------------------------

def test_rules_the_plugin_did_not_author_survive_a_write_below_the_clients(
        live_aw, workspace, tmp_path):
    """Trusting the plugin with configuration it did not create is the whole of #69's
    story 7. A user's own category is kept verbatim, after the clients' curated rules."""
    server = live_aw(sample_day([ACME_PAGE, PERSONAL],
                                classes=[("Personal", r"metservice"),
                                         ("Grouping", r"")]))
    result = compile_run(tmp_path, [ACME])
    assert result.code == 0, result.err
    assert names(posted(server)) == ["Acme", "Personal", "Grouping"]
    assert "2 rules left as they were" in result.out


def test_a_rebuild_replaces_this_plugins_own_rule_rather_than_adding_a_second(
        live_aw, workspace, tmp_path):
    """The context file is the source of truth and the rules are a derived copy, so writing
    them twice has to leave one copy — otherwise every rebuild doubles the rule set."""
    server = live_aw(sample_day([ACME_PAGE, PERSONAL], classes=[("Acme", r"\[ACME\]")]))
    result = compile_run(tmp_path, [ACME])
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
    live_aw(sample_day([ACME_PAGE, PERSONAL], classes=[("Personal", r"metservice")]))
    result = compile_run(tmp_path, [ACME])
    assert result.code == 0, result.err
    (backup,) = backups(workspace)
    assert names(json.loads(backup.read_text(encoding="utf-8"))["classes"]) == ["Personal"]
    assert str(backup) in result.out, "a run that does not print where the backup went "\
                                      "leaves the user to find it at recovery time"


def test_a_refused_run_leaves_no_backup_because_it_never_reached_a_write(
        live_aw, workspace, tmp_path):
    live_aw(sample_day([ACME_PAGE, PERSONAL]))
    compile_run(tmp_path, [candidate("Beta")])
    assert backups(workspace) == []


# --------------------------------------------------------------------------------------
# The endpoint that is not there, and the one that says no
# --------------------------------------------------------------------------------------

def test_an_absent_settings_endpoint_is_refused_in_words_rather_than_a_traceback(
        live_aw, workspace, tmp_path):
    """The older build the `setup` skill has a manual fallback for. A traceback here sends
    a run debugging the script instead of taking the route that works."""
    live_aw(sample_day([ACME_PAGE, PERSONAL]), settings_status=404)
    result = compile_run(tmp_path, [ACME])
    assert result.code == 1
    assert "ERR" in result.err and "by hand" in result.err
    assert "Traceback" not in result.err


def test_an_error_on_the_write_is_reported_and_names_the_backup(
        live_aw, workspace, tmp_path):
    """Swallowed, this is the worst outcome in the feature: a run that reports the rules
    configured when nothing landed."""
    live_aw(sample_day([ACME_PAGE, PERSONAL]), write_status=500)
    result = compile_run(tmp_path, [ACME])
    assert result.code == 1
    assert "refused the write" in result.err
    (backup,) = backups(workspace)
    assert str(backup) in result.err


# --------------------------------------------------------------------------------------
# The verify
# --------------------------------------------------------------------------------------

def test_the_run_asks_the_activity_source_what_each_rule_labels(
        live_aw, workspace, tmp_path):
    server = live_aw(sample_day([ACME_PAGE, ACME_EDITOR, BETA_PAGE, PERSONAL]))
    result = compile_run(tmp_path, [ACME, BETA])
    assert result.code == 0, result.err
    assert "VERIFY Acme — 2 sampled titles; the activity source labels 0.0h" in result.out
    assert "VERIFY Beta — 1 sampled titles" in result.out
    assert len(server.sent("GET", "/settings")) >= 2, (
        "the rules have to be read *back* after the write, not assumed from what was sent")
    assert len(server.sent("POST", "/query/")) == 2, "one question per rule, each alone"


def test_a_rule_the_activity_source_does_not_match_fails_the_run(
        live_aw, workspace, tmp_path, monkeypatch):
    """What the verify exists for: the gate and the activity source disagreeing. Recreated
    as 0.10 had it — rules anchored on the app name, gated against the app and the title
    joined — which is a gate that passes a rule ActivityWatch never matches."""
    import re
    context_file(workspace)
    live_aw(sample_day([ACME_PAGE, PERSONAL]))
    real = cr.rule_for
    monkeypatch.setattr(cr, "rule_for", lambda terms: "^(?:msedge).*" + real(terms))
    monkeypatch.setattr(cr, "matching", lambda regex, sample: [
        w for w in sample if re.search(regex, f"{w[0]} {w[1]}", re.IGNORECASE)])
    result = compile_run(tmp_path, [candidate("Acme", "ACME")])
    assert result.code == 1
    assert "labels none of them" in result.err
    assert run_cli(cr, ["--status"]).out.startswith("STALE"), "no stamp for a failed verify"


def test_a_query_endpoint_that_does_not_answer_leaves_the_write_unconfirmed(
        live_aw, workspace, tmp_path):
    context_file(workspace)
    live_aw(sample_day([ACME_PAGE, PERSONAL]), query_status=404)
    result = compile_run(tmp_path, [ACME])
    assert result.code == 1
    assert "unconfirmed" in result.err
    assert run_cli(cr, ["--status"]).out.startswith("STALE")


def test_a_failed_verify_leaves_the_rules_stale_rather_than_recording_a_write(
        live_aw, workspace, tmp_path, monkeypatch):
    """The stamp is what tomorrow's staleness check believes. Written before the verify, a
    write that did not land is recorded as current: the next day reports `CURRENT`, skips
    the rebuild, and labels the whole day against rules the activity source does not hold —
    which is the exact failure the verify exists to catch, one day later and silent."""
    context_file(workspace)
    live_aw(sample_day([ACME_PAGE, PERSONAL]))
    monkeypatch.setattr(cr, "post_setting", lambda key, value: None)
    assert compile_run(tmp_path, [ACME]).code == 1
    assert run_cli(cr, ["--status"]).out.startswith("STALE")


def test_a_write_the_server_accepted_and_did_not_keep_fails_the_verify(
        live_aw, workspace, tmp_path, monkeypatch):
    """A rule missing at this point is a write that did not land — which is the difference
    between a configured install and one that only looks configured."""
    live_aw(sample_day([ACME_PAGE, PERSONAL]))
    monkeypatch.setattr(cr, "post_setting", lambda key, value: None)
    result = compile_run(tmp_path, [ACME])
    assert result.code == 1
    assert "did not land" in result.err


# --------------------------------------------------------------------------------------
# Reading what is there: the inspect mode adoption is built on
# --------------------------------------------------------------------------------------

def test_inspect_reports_every_rule_with_the_share_it_matches(live_aw, workspace):
    server = live_aw(sample_day([ACME_PAGE, BETA_PAGE, PERSONAL, TEAMS],
                                classes=[("Acme", r"\[ACME\]"), ("Everything", BROAD)]))
    result = run_cli(cr, ["--inspect"])
    assert result.code == 0, result.err
    total = sampled([ACME_PAGE, BETA_PAGE, PERSONAL, TEAMS])
    assert f"RULE Acme [unmanaged] — 1 of {total} titles" in result.out
    assert "OVER the 35% ceiling" in result.out
    assert posted(server) == [], "--inspect writes nothing"


def test_inspect_matches_each_field_on_its_own_as_the_activity_source_does(
        live_aw, workspace):
    """A rule spanning the app and the title matches nothing in ActivityWatch, so inspect
    must not report it matching — that report is what adoption is decided on."""
    live_aw(sample_day([ACME_PAGE, PERSONAL], classes=[("Old", r"^(?:msedge).*\[ACME\]")]))
    assert "RULE Old [unmanaged] — 0 of" in run_cli(cr, ["--inspect"]).out


def test_inspect_shows_an_example_of_what_a_rule_matched(live_aw, workspace):
    """What makes a rule mappable to a client by a reader: the name usually says it, and
    where it does not, the titles it caught do."""
    live_aw(sample_day([ACME_PAGE, PERSONAL], classes=[("Legacy", r"\[ACME\]")]))
    result = run_cli(cr, ["--inspect"])
    assert "e.g. msedge.exe Acme portal-acme.crm6" in result.out


def test_inspect_names_a_grouping_category_rather_than_erroring_on_it(live_aw, workspace):
    """A parent category carries `{"type": "none"}` and no regex at all — reaching for a
    field that is not there is what turns a healthy configuration into an error."""
    built = sample_day([ACME_PAGE, PERSONAL])
    built.classes.append({"name": ["Work"], "rule": {"type": "none"}})
    live_aw(built)
    result = run_cli(cr, ["--inspect"])
    assert result.code == 0, result.err
    assert "RULE Work [unmanaged] — no regex" in result.out


# --------------------------------------------------------------------------------------
# The profile tags the titles actually carry
# --------------------------------------------------------------------------------------

# Where the extension puts a profile tag: the end of the page part, before Edge's own
# ` and N more pages` and the profile slot. Chrome prints no profile after it.
ACME_TAGGED = ("msedge.exe",
               f"Acme portal-acme.example.com/home - [ACME] and 12 more pages - Acme - Dana{EDGE}")
ACME_TAGGED_ALONE = ("msedge.exe", f"Acme board-acme.example.com/board - [ACME] - Acme - Dana{EDGE}")
ACME_TAG_IN_WORK = ("msedge.exe", f"Acme notes-notes.example.com - [ACME] - Work{EDGE}")
BETA_TAGGED_CHROME = ("chrome.exe", "Beta orders-beta.example.com/orders - [BETA] - Google Chrome")
DRAFT_PAGE = ("msedge.exe", f"[Draft] Plan-plans.example.com/x - Work{EDGE}")


def test_inspect_lists_each_profile_tag_with_the_edge_profile_it_was_seen_in(
        live_aw, workspace):
    """Which client codes the titles really carry, so the terms are chosen from what is
    there. Printed before the rules are read, so it shows on an install with no categories."""
    live_aw(sample_day([ACME_TAGGED, ACME_TAGGED_ALONE, PERSONAL]))
    result = run_cli(cr, ["--inspect"])
    assert result.code == 0, result.err
    assert 'SEEN [ACME] — 2 titles, in Edge profile "Acme - Dana"' in result.out
    assert "RULES none" in result.out


def test_a_profile_tag_seen_in_several_profiles_lists_each_of_them(live_aw, workspace):
    """A tag on a second profile — the general one, usually — is the silent failure setup's
    step 3 exists to prevent; which profile is general is the user's to say."""
    live_aw(sample_day([ACME_TAGGED, ACME_TAG_IN_WORK, PERSONAL]))
    result = run_cli(cr, ["--inspect"])
    assert 'SEEN [ACME] — 2 titles, in several profiles: "Acme - Dana" (1), "Work" (1)' \
        in result.out


def test_a_profile_tag_in_chrome_is_listed_without_a_profile(live_aw, workspace):
    live_aw(sample_day([BETA_TAGGED_CHROME, PERSONAL]))
    result = run_cli(cr, ["--inspect"])
    assert "SEEN [BETA] — 1 title, no profile in the title" in result.out


def test_a_bracket_in_a_page_title_is_not_read_as_a_profile_tag(live_aw, workspace):
    live_aw(sample_day([DRAFT_PAGE, PERSONAL]))
    result = run_cli(cr, ["--inspect"])
    assert "SEEN no profile tag in the sampled titles" in result.out
    assert "[Draft]" not in result.out


def test_a_bracket_inside_the_page_part_does_not_hide_the_tag_after_it(live_aw, workspace):
    """The first ` - [X]` is the page's own; the extension's is the last one."""
    sprint_tagged = ("msedge.exe",
                     f"Sprint - [Q3] - Board-acme.example.com/b - [ACME] - Acme - Dana{EDGE}")
    sprint_untagged = ("msedge.exe", f"Sprint - [Q3] - Board-acme.example.com/b - Work{EDGE}")
    live_aw(sample_day([sprint_tagged, sprint_untagged, PERSONAL]))
    result = run_cli(cr, ["--inspect"])
    assert 'SEEN [ACME] — 1 title, in Edge profile "Acme - Dana"' in result.out
    assert "[Q3]" not in result.out


def test_the_profile_tags_are_listed_where_the_rules_cannot_be_read(live_aw, workspace):
    live_aw(sample_day([ACME_TAGGED, PERSONAL]), settings_status=404)
    result = run_cli(cr, ["--inspect"])
    assert result.code == 1
    assert "SEEN [ACME]" in result.out


# --------------------------------------------------------------------------------------
# Adopting the rules a user already had (#73)
# --------------------------------------------------------------------------------------

def test_a_rule_this_plugin_wrote_reads_back_as_managed_and_the_users_own_does_not(
        live_aw, workspace, tmp_path):
    """Which rules are up for adoption is a mechanical question, not a judgement — the run
    that writes a rule records the client it wrote it for, and everything else the activity
    source holds is the user's own."""
    live_aw(sample_day([ACME_PAGE, PERSONAL], classes=[("Personal", r"metservice")]))
    assert compile_run(tmp_path, [ACME]).code == 0
    result = run_cli(cr, ["--inspect"])
    assert "RULE Acme [managed]" in result.out
    assert "RULE Personal [unmanaged]" in result.out


def test_adopting_a_rule_makes_it_managed_and_leaves_one_copy(live_aw, workspace, tmp_path):
    """The user accepts the mapping, the rule is rebuilt from the terms behind it like any
    other, and from then on a rebuild regenerates it rather than leaving it beside the
    managed set."""
    server = live_aw(sample_day([ACME_PAGE, PERSONAL],
                                classes=[("Acme", r"acme"), ("Personal", r"metservice")]))
    result = compile_run(tmp_path, [ACME])
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
    built = sample_day([ACME_PAGE, PERSONAL])
    built.classes.append(theirs)
    server = live_aw(built)
    result = compile_run(tmp_path, [ACME])
    assert result.code == 0, result.err
    assert theirs in posted(server)


def test_a_new_rule_does_not_take_an_id_an_unmanaged_rule_is_already_using(
        live_aw, workspace, tmp_path):
    built = sample_day([ACME_PAGE, PERSONAL])
    built.classes.append({"id": 12, "name": ["Personal"],
                          "rule": {"type": "regex", "regex": "metservice"}})
    server = live_aw(built)
    compile_run(tmp_path, [ACME])
    written = posted(server)
    assert len({entry["id"] for entry in written}) == len(written)


def test_adopting_a_rule_whose_name_is_not_the_clients_leaves_one_copy(
        live_aw, workspace, tmp_path):
    """The README told users to make `Work > Acme` for years, so the rule being adopted
    usually is not named for the client alone. Replacing on the client's name only would
    write a second flat `Acme` and leave the nested one beside it forever — "adopted" in
    words, doubled in fact. The candidate names what it takes over."""
    server = live_aw(sample_day([ACME_PAGE, PERSONAL], classes=[("Work>Acme", r"\[ACME\]")]))
    result = compile_run(tmp_path, [dict(ACME, adopts="Work>Acme")])
    assert result.code == 0, result.err
    assert names(posted(server)) == ["Acme"]


def test_a_client_no_longer_declared_loses_its_rule_rather_than_being_orphaned(
        live_aw, workspace, tmp_path):
    """The rules are a derived copy, so the managed set is regenerated whole. Left behind,
    a dropped client's rule goes on labelling spans *and* reads back as the user's own at
    the next inspect — so adoption would offer them their own leftover as something they
    made."""
    server = live_aw(sample_day([ACME_PAGE, BETA_PAGE, PERSONAL]))
    assert compile_run(tmp_path, [ACME, BETA]).code == 0
    # The same server, so the second run reads back what the first one wrote — which is the
    # whole scenario. A second fake would start empty and the assertion would pass on a run
    # that had nothing to drop.
    result = compile_run(tmp_path, [ACME])
    assert result.code == 0, result.err
    writes = server.sent("POST", "/settings/classes")
    assert len(writes) == 2
    assert names(writes[-1]["body"]) == ["Acme"], "Beta's rule outlived Beta"
    assert "DROPPED Beta" in result.out


def test_a_managed_rule_edited_in_the_settings_dialog_is_reported_by_inspect(
        live_aw, workspace, tmp_path):
    """#69 story 5: a rule damaged by hand is recoverable. The staleness check cannot see
    it — two local file reads — so this is where it surfaces, and a recompile is the fix."""
    live_aw(sample_day([ACME_PAGE, PERSONAL]))
    assert compile_run(tmp_path, [ACME]).code == 0
    live_aw(sample_day([ACME_PAGE, PERSONAL], classes=[("Acme", r"something else")]))
    assert "EDITED since it was written" in run_cli(cr, ["--inspect"]).out


def test_an_over_broad_rule_of_the_users_own_is_surfaced_for_correction(
        live_aw, workspace):
    """Adoption is where an over-broad rule gets fixed rather than merely reported: the
    measured case takes the label off a correct rule, so it is worth the one question."""
    live_aw(sample_day([ACME_PAGE, PERSONAL], classes=[("Everything", BROAD)]))
    result = run_cli(cr, ["--inspect"])
    assert "RULE Everything [unmanaged]" in result.out
    assert "OVER the 35% ceiling" in result.out


# --------------------------------------------------------------------------------------
# Staleness: the rules are a derived copy, so the copy is rebuilt when the source moves (#74)
# --------------------------------------------------------------------------------------

def context_file(workspace: Path, text: str = "### Acme\n- `ACME`\n") -> Path:
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
    live_aw(sample_day([ACME_PAGE, PERSONAL]))
    assert compile_run(tmp_path, [ACME]).code == 0
    assert run_cli(cr, ["--status"]).out.startswith("CURRENT")


def test_rules_written_before_terms_are_broken_and_send_the_user_to_setup(workspace):
    """Every stamp from before 0.11.0 records rules anchored on the app name, which the
    activity source never matches — however current the context file. A quiet recompile
    from `.context.md` would compose the same signals again; choosing terms is setup's."""
    path = context_file(workspace)
    state = workspace / ".mcp"
    state.mkdir(exist_ok=True)
    (state / cr.STAMP).write_text(json.dumps({
        "written": "2026-09-28T04:38:26+00:00",
        "context_sha256": cr.context_fingerprint(path.parent.parent)[0],
        "rules": [{"client": "Acme", "signal": "url_host",
                   "regex": r"^(?:msedge|chrome).*(?:acme\.crm6)"}],
    }), encoding="utf-8")
    result = run_cli(cr, ["--status"])
    assert result.code == 0
    assert result.out.startswith("BROKEN")
    assert "`setup` skill's category step" in result.out


def test_a_hand_edit_to_the_context_file_makes_the_rules_stale(
        live_aw, workspace, tmp_path):
    """The edit made outside a run is the one nothing else would notice: the user adds a
    client on Friday and Monday's timesheet is drafted against rules that never heard of
    them."""
    context_file(workspace)
    live_aw(sample_day([ACME_PAGE, PERSONAL]))
    compile_run(tmp_path, [ACME])
    context_file(workspace, "### Acme\n- `ACME`\n\n### Beta\n- `BETA`\n")
    result = run_cli(cr, ["--status"])
    assert result.out.startswith("STALE")
    assert "has changed since the rules were written" in result.out


def test_status_reads_no_activity_source_at_all(live_aw, workspace, tmp_path):
    """A run pays for this at the start of every day, so it has to be two local file reads.
    It is also what keeps the rule "a run whose context file has not changed does not write"
    true without anything having to remember it."""
    context_file(workspace)
    server = live_aw(sample_day([ACME_PAGE, PERSONAL]))
    compile_run(tmp_path, [ACME])
    before = len(server.requests)
    assert run_cli(cr, ["--status"]).out.startswith("CURRENT")
    assert len(server.requests) == before, "--status touched the activity source"


def test_status_leaves_no_directory_behind_where_no_workspace_resolves(tmp_path, monkeypatch):
    """Step 2 runs this at the start of every day. A read that mints a `.mcp/` in whatever
    folder the session happened to start in does it every day, and — since the state
    directory became a refusal when it cannot be created — could fail a check the workflow
    describes as costing a run nothing."""
    monkeypatch.chdir(tmp_path)
    result = run_cli(cr, ["--status"])
    assert result.code == 0, result.err
    assert not (tmp_path / ".mcp").exists()


def test_a_workspace_with_no_context_file_is_stale_rather_than_current(workspace):
    """There is nothing to build rules from, which is a state to act on — the `daily`
    skill's first run scaffolds that file — and not a run to report as up to date."""
    result = run_cli(cr, ["--status"])
    assert result.code == 0
    assert result.out.startswith("STALE")


def test_a_rebuild_is_gated_exactly_as_the_first_write_was(live_aw, workspace, tmp_path):
    """The rebuild rides inside an approval the user has already given, so the only thing
    standing between a mistyped term and their timesheet is this gate."""
    context_file(workspace)
    server = live_aw(sample_day([ACME_PAGE, PERSONAL]))
    compile_run(tmp_path, [ACME])
    result = compile_run(tmp_path, [ACME, candidate("Beta", BROAD)])
    assert result.code == 1
    assert len(server.sent("POST", "/settings/classes")) == 1, (
        "the refused rebuild wrote anyway — the first write is the only one that landed")


# --------------------------------------------------------------------------------------
# The command line itself
# --------------------------------------------------------------------------------------

def test_the_candidates_can_arrive_on_stdin(live_aw, workspace, monkeypatch):
    """A run composing candidates has them in hand, not in a file; making it write one
    first is a step that can fail on a read-only or unexpected working directory."""
    server = live_aw(sample_day([ACME_PAGE, PERSONAL]))
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps([ACME])))
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
    server = live_aw(sample_day([ACME_PAGE, PERSONAL]))
    result = compile_run(tmp_path, [ACME], "--workspace", str(root))
    assert result.code == 1
    assert "cannot keep the backup" in result.err
    assert "unreachable" not in result.err
    assert posted(server) == []


def test_a_sample_with_nothing_in_it_refuses_rather_than_writing_unjudged_rules(
        live_aw, workspace, tmp_path):
    """A day with no window events is not a day on which every rule is fine."""
    live_aw(day(date=SAMPLE_DAY, offset=0).window("09:00", "09:01", "x", "y"))
    result = compile_run(tmp_path, [ACME], "--days", "0")
    assert result.code == 1
    assert "nothing to test a category rule against" in result.err

"""Edge cases in the Harvest adapter's catalog write path (`refresh`) and read path
(`lookup`), driven through the dispatcher or at the adapter's own functions.

The two tests at the top guard promises the source makes in comments and nothing
else checks: a refresh fetches every page before it deletes anything, and it clears
page files a shorter run left behind. Both failures are silent — the user sees a
successful-looking lookup against a catalog that is half gone or half stale.
"""
from __future__ import annotations

import json
import time
import os
from pathlib import Path

import pytest

import refresh_catalogs as rc
import skill_config
from provider import dispatcher as tp
from provider.errors import NoMatch, Refused
from provider.harvest import catalog
from support import assignments_page, paged_assignments, project, run_cli, write_catalog


def _snapshot(directory: Path):
    return {p.name: p.read_bytes() for p in sorted(directory.iterdir())}


def _write(directory: Path, name: str, text: str):
    """A file that is not a catalog page — an unrelated neighbour, or a truncated one."""
    (directory / name).write_text(text, encoding="utf-8")


# --------------------------------------------------------------------------------------
# refresh: the two invariants the comments promise
# --------------------------------------------------------------------------------------

def test_a_failure_on_page_two_leaves_every_existing_catalog_file_byte_for_byte_intact(workspace, live_harvest):
    """A refresh that dies halfway must not have started deleting.

    If it deletes first and fetches second, a Harvest outage mid-refresh leaves the user
    with a catalog missing whole pages — every project on them then looks archived, and
    the next lookup silently bills through the time-entries fallback or not at all. A
    stale catalog is recoverable; a half-deleted one is not.
    """
    mcp = workspace / ".mcp"
    write_catalog(mcp, {
        "harvest_assignments.json": assignments_page(1, 2, [project(1, "OLD-1", "Kept page one")]),
        "harvest_assignments_p2.json": assignments_page(2, 2, [project(2, "OLD-2", "Kept page two")]),
    })
    _write(mcp, "dv_active_incidents.txt", "unrelated catalog\n")
    before = _snapshot(mcp)

    live_harvest(paged_assignments([assignments_page(1, 2, [project(9, "NEW-9")]),
                         assignments_page(2, 2, [project(10, "NEW-10")])], fail_on=2))
    r = run_cli(tp, ["refresh"])

    assert r.code == 4, "an answer of any status is a refusal, and the reason is on stderr"
    assert "existing catalog left untouched" in r.err
    assert r.out == ""
    # Contents *and* the filename set: a half-written page would slip past a
    # contents-only check on the seeded files.
    assert _snapshot(mcp) == before


def test_a_refresh_returning_fewer_pages_deletes_the_leftover_page_files(workspace, live_harvest):
    """Consumers glob `harvest_assignments*.json`, so a page file the shorter run did not
    overwrite is read as current data. The user sees projects that no longer exist, or
    task ids that have since moved, presented exactly like live ones.
    """
    mcp = workspace / ".mcp"
    write_catalog(mcp, {
        "harvest_assignments.json": assignments_page(1, 3, [project(1, "OLD-1")]),
        "harvest_assignments_p2.json": assignments_page(2, 3, [project(2, "OLD-2")]),
        "harvest_assignments_p3.json": assignments_page(3, 3, [project(3, "OLD-3")]),
    })

    live_harvest(paged_assignments([assignments_page(1, 1, [project(9, "NEW-9")])]))
    r = run_cli(tp, ["refresh"])

    assert r.code == 0 and r.out == "OK 1 projects\n"
    assert sorted(p.name for p in mcp.iterdir()) == ["harvest_assignments.json"]
    kept = json.loads((mcp / "harvest_assignments.json").read_text(encoding="utf-8"))
    assert [pa["project"]["code"] for pa in kept["project_assignments"]] == ["NEW-9"]
    assert [pa["project"]["code"] for pa in catalog._assignments(mcp)] == ["NEW-9"]


def test_page_one_is_unsuffixed_and_later_pages_each_hold_their_own_payload(workspace, live_harvest):
    """The reader globs for `harvest_assignments*.json` and the docs name the files
    explicitly. Renaming or duplicating a page here means a lookup either misses every
    project after the first hundred, or reports page one's tasks for all of them.
    """
    mcp = workspace / ".mcp"
    pages = [assignments_page(1, 3, [project(1, "P1-A"), project(2, "P1-B")]),
             assignments_page(2, 3, [project(3, "P2-A")]),
             assignments_page(3, 3, [project(4, "P3-A")])]

    live_harvest(paged_assignments(pages))
    r = run_cli(tp, ["refresh"])

    assert r.code == 0 and r.out == "OK 4 projects\n"
    assert "page 3" in r.err, "per-page progress is stderr, never stdout"
    names = ["harvest_assignments.json", "harvest_assignments_p2.json",
             "harvest_assignments_p3.json"]
    assert sorted(p.name for p in mcp.iterdir()) == sorted(names)
    for name, expected in zip(names, pages):
        assert json.loads((mcp / name).read_text(encoding="utf-8")) == expected


def test_the_dataverse_refresh_reports_a_skip_when_the_org_is_not_configured(workspace):
    """Dataverse is optional. If the unconfigured guard stops working, `refresh_dataverse`
    reaches the `pac` CLI with a None environment — a user who never opted in gets an
    error, and their active `pac` auth profile gets switched out from under them.
    """
    r = run_cli(rc, ["--dataverse-only"])
    assert r.code == 0
    assert "Skipping Dataverse refresh" in r.out


def test_refresh_catalogs_no_longer_touches_the_provider(workspace):
    """The provider's catalog is `timesheet-provider refresh`; the two flags the contract
    retires do not exist on this script, and it asks for no provider credential."""
    assert run_cli(rc, ["--harvest-only"]).code == 2
    assert run_cli(rc, []).code == 2


def test_a_catalog_that_comes_back_empty_is_a_failure_not_an_empty_catalog(workspace, live_harvest):
    """Written empty it would make every later lookup fall through to the live fallback
    unannounced (contract section 3.5). The existing catalog is left as it was."""
    mcp = workspace / ".mcp"
    write_catalog(mcp, {"harvest_assignments.json": assignments_page(1, 1, [project(1, "OLD-1")])})
    before = _snapshot(mcp)
    live_harvest(paged_assignments([assignments_page(1, 1, [])]))
    r = run_cli(tp, ["refresh"])
    assert r.code == 4 and "existing catalog left untouched" in r.err
    assert _snapshot(mcp) == before


# --------------------------------------------------------------------------------------
# refresh --wait: the pre-billing poll for an eventually-consistent row
# --------------------------------------------------------------------------------------

def test_wait_finds_the_code_on_whichever_page_holds_it_and_writes_what_it_found(workspace, live_harvest, monkeypatch):
    """This is what a user runs before billing a freshly-created project. If it only
    looked at page one, anyone with more than a hundred assignments would be told their
    new project does not exist yet and would wait out the whole poll for nothing.
    """
    slept = []
    monkeypatch.setattr(time, "sleep", slept.append)
    live_harvest(paged_assignments([assignments_page(1, 2, [project(1, "OTHER-1")]),
                         assignments_page(2, 2, [project(2, "ACM-CR900", "Brand new case")])]))

    r = run_cli(tp, ["refresh", "--wait", "ACM-CR900", "--attempts", "3", "--delay", "15"])

    assert r.code == 0 and r.out == "OK ACM-CR900\n"
    assert slept == []          # found on the first attempt, so it never waits
    written = [pa["project"]["code"] for pa in catalog._assignments(workspace / ".mcp")]
    assert written == ["OTHER-1", "ACM-CR900"], "it writes the catalog it found"


def test_wait_that_never_appears_is_exit_6_and_leaves_the_catalog(workspace, live_harvest, monkeypatch):
    """A code that never appears has to come back as a *no match* so the caller can say "not
    visible yet" - not as success, and not as a hang."""
    slept = []
    monkeypatch.setattr(time, "sleep", slept.append)
    mcp = workspace / ".mcp"
    write_catalog(mcp, {"harvest_assignments.json": assignments_page(1, 1, [project(1, "OLD-1")])})
    before = _snapshot(mcp)
    live_harvest(paged_assignments([assignments_page(1, 1, [project(1, "OTHER-1")])]))

    r = run_cli(tp, ["refresh", "--wait", "NEVER-1", "--attempts", "3", "--delay", "15"])

    assert r.code == 6
    assert r.err.startswith("ERR NEVER-1 did not appear after 3 attempts")
    assert slept == [15, 15]    # waits between attempts, not after the last one
    assert _snapshot(mcp) == before


def test_wait_never_posts_anything(workspace, live_harvest, monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda s: None)
    srv = live_harvest(paged_assignments([assignments_page(1, 1, [project(1, "ACM-1")])]))
    run_cli(tp, ["refresh", "--wait", "ACM-1"])
    assert [r["method"] for r in srv.requests] == ["GET"]


def test_age_is_whole_days_rounded_down_and_needs_no_credential(workspace):
    """`--age` is how a caller decides whether to refresh without reading the adapter's
    storage; the hermetic fixture blanks every credential, so success is the proof."""
    mcp = workspace / ".mcp"
    assert run_cli(tp, ["refresh", "--age"]).out == "ABSENT\n"
    write_catalog(mcp, {"harvest_assignments.json": assignments_page(1, 1, [project(1, "A-1")])})
    old = time.time() - 8.9 * 86400
    os.utime(mcp / "harvest_assignments.json", (old, old))
    r = run_cli(tp, ["refresh", "--age"])
    assert r.code == 0 and r.out == "AGE 8\n"


def test_age_is_the_newest_page_not_the_oldest(workspace):
    """A refresh rewrites every page together, so the catalog is as fresh as its newest."""
    mcp = workspace / ".mcp"
    write_catalog(mcp, {"harvest_assignments.json": assignments_page(1, 2, [project(1, "A-1")]),
                        "harvest_assignments_p2.json": assignments_page(2, 2, [project(2, "B-2")])})
    old = time.time() - 40 * 86400
    os.utime(mcp / "harvest_assignments.json", (old, old))
    assert run_cli(tp, ["refresh", "--age"]).out == "AGE 0\n"


# --------------------------------------------------------------------------------------
# the adapter's catalog reader: reading a catalog someone else wrote
# --------------------------------------------------------------------------------------

def test_a_page_of_unparseable_json_is_skipped_instead_of_aborting_the_whole_lookup(tmp_path):
    """A refresh killed mid-write leaves one truncated page. Every *other* page is still
    good, so the lookup should degrade to "that project is missing" rather than failing
    outright and sending the user off to debug the tool.
    """
    _write(tmp_path, "harvest_assignments.json", '{"project_assignments": [{"proj')
    write_catalog(tmp_path, {"harvest_assignments_p2.json":
                            assignments_page(2, 2, [project(2, "GOOD-2", "Survivor")])})

    rows = list(catalog._assignments(tmp_path))

    assert [pa["project"]["code"] for pa in rows] == ["GOOD-2"]


def test_a_page_stored_as_a_bare_json_list_is_read_like_a_wrapped_one(tmp_path):
    """Hand-maintained and hand-trimmed catalogs get saved as a plain list of
    assignments. Ignoring that shape reports "no project matching" for a catalog the
    user can see the project sitting in.
    """
    write_catalog(tmp_path, {"harvest_assignments.json":
                            [project(1, "BARE-1", "Written as a list")]})

    rows = list(catalog._assignments(tmp_path))

    assert [pa["project"]["code"] for pa in rows] == ["BARE-1"]


def test_a_page_keyed_on_assignments_is_read_like_one_keyed_on_project_assignments(tmp_path):
    """Both spellings exist in the wild. Accepting only Harvest's own key makes a
    perfectly valid catalog look empty.
    """
    write_catalog(tmp_path, {"harvest_assignments.json":
                            {"assignments": [project(1, "ALT-1", "Short key")]}})

    rows = list(catalog._assignments(tmp_path))

    assert [pa["project"]["code"] for pa in rows] == ["ALT-1"]


def test_a_project_appearing_on_several_pages_is_yielded_once_from_the_first_page(tmp_path):
    """Paging is not a snapshot: a project can be captured twice while the pages are
    being fetched. Yielding both makes the same project appear twice in a lookup, and
    the model picks whichever copy it read last — possibly the one with no tasks.
    """
    write_catalog(tmp_path, {
        "harvest_assignments.json": assignments_page(1, 2, [
            project(48084036, "ACM-CR202", "Full row, with tasks",
                     [{"billable": True, "task": {"id": 7, "name": "Gen - Development"}}])]),
        "harvest_assignments_p2.json": assignments_page(2, 2, [
            project(48084036, "ACM-CR202", "Duplicate row, no tasks"),
            project(37122824, "NWC-001", "Admin")]),
    })

    rows = list(catalog._assignments(tmp_path))

    assert [pa["project"]["id"] for pa in rows] == [48084036, 37122824]
    dupe = rows[0]
    assert dupe["project"]["name"] == "Full row, with tasks"
    assert dupe["task_assignments"] != []


# --------------------------------------------------------------------------------------
# lookup: choosing between the matches
# --------------------------------------------------------------------------------------

def test_an_exact_code_match_sorts_ahead_of_the_substring_matches(tmp_path):
    """The model bills against the first row printed. With plain alphabetical order a
    code that merely *contains* the query can outrank the code the user typed verbatim,
    which puts the hours on the wrong project.
    """
    write_catalog(tmp_path, {"harvest_assignments.json": assignments_page(1, 1, [
        # "ACON-1" sorts before "CON" alphabetically, so this only passes if the
        # exact-match key is doing the work.
        project(1, "ACON-1", "Alpha consulting"),
        project(2, "CON-2", "Consulting, part two"),
        project(3, "CON", "Consulting"),
        project(4, "ZZZ-9", "Nothing to do with the query"),
    ])})

    matches = catalog.from_catalog("CON", tmp_path, None)

    assert [m["code"] for m in matches] == ["CON", "ACON-1", "CON-2"]


def test_the_task_filter_is_a_case_insensitive_substring_of_the_task_name(tmp_path):
    """`--task development` is how the model narrows a project with a dozen task rows.
    Case- or prefix-sensitivity here shows an empty task list for a project that plainly
    has the task, and the entry gets posted against the wrong task id.
    """
    write_catalog(tmp_path, {"harvest_assignments.json": assignments_page(1, 1, [
        project(1, "CON-1", "Consulting", [
            {"billable": True, "task": {"id": 10, "name": "Gen - Development/Configuration"}},
            {"billable": False, "task": {"id": 11, "name": "Meeting - Standup Meetings"}}])])})

    matches = catalog.from_catalog("CON-1", tmp_path, "development")

    assert [t["id"] for t in matches[0]["tasks"]] == [10]


def test_billable_comes_from_the_task_assignments_own_flag_not_from_the_task_name(tmp_path):
    """The "(NB)" naming convention is a human hint, not the source of truth — the
    assignment carries the real flag. Reading the name instead misreports billability,
    and billability is the field an invoice is built from.
    """
    write_catalog(tmp_path, {"harvest_assignments.json": assignments_page(1, 1, [
        project(1, "CON-1", "Consulting", [
            # Name says non-billable, flag says billable — and the reverse.
            {"billable": True, "task": {"id": 10, "name": "Gen - Development (NB)"}},
            {"billable": False, "task": {"id": 11, "name": "Billable Development"}}])])})

    tasks = {t["id"]: t["billable"] for t in catalog.from_catalog("CON-1", tmp_path, None)[0]["tasks"]}

    assert tasks == {10: True, 11: False}


def test_a_project_with_no_task_assignments_returns_an_empty_task_list(tmp_path):
    """A project can legitimately carry no assigned tasks (a duplicate paging row, or an
    assignment being set up). The lookup has to still report the project and its id — a
    crash here takes out every other match in the same run.
    """
    write_catalog(tmp_path, {"harvest_assignments.json": assignments_page(1, 1, [
        {"project": {"id": 1, "code": "BARE-1", "name": "No tasks yet"}}])})

    matches = catalog.from_catalog("BARE-1", tmp_path, None)

    assert len(matches) == 1
    assert matches[0]["project_id"] == 1
    assert matches[0]["tasks"] == []


# --------------------------------------------------------------------------------------
# catalog_dir(): where to read when nothing is configured
# --------------------------------------------------------------------------------------

def test_with_no_workspace_a_lookup_says_so_and_still_asks_the_provider(tmp_path, monkeypatch, live_harvest):
    """With no workspace configured the catalog cannot be found, which is not fatal while the
    history fallback can answer (contract section 3.3): it says so on stderr and recovers.
    Failing instead would turn "no catalog here" into a dead end.
    """
    # SKILL_ROOT must be repointed too, not just the cwd: `find_workspace()` also walks the
    # directories the skill is installed under, so this test's result depended on where the
    # checkout happened to sit. docs/skills/daily/decision-log.md has the entry.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(skill_config, "SKILL_ROOT", tmp_path / "skills" / "daily")
    assert skill_config.find_workspace() is None, "the fallback branch is only reachable unresolved"
    live_harvest({
        ("GET", "/users/me"): (200, {"id": 1}),
        ("GET", "/time_entries"): (200, {"time_entries": [{
            "project": {"id": 5, "code": "ARCH-1", "name": "Archived"},
            "task": {"id": 6, "name": "Dev"}, "billable": True}], "next_page": None}),
    })

    r = run_cli(tp, ["lookup", "ARCH-1", "--json"])

    assert r.code == 0 and r.json()[0]["source"] == "history"
    assert "WARN no workspace" in r.err


def test_a_catalog_dir_that_does_not_exist_is_said_and_not_fatal(tmp_path, live_harvest):
    live_harvest({("GET", "/users/me"): (200, {"id": 1}),
                  ("GET", "/time_entries"): (200, {"time_entries": [], "next_page": None})})
    r = run_cli(tp, ["lookup", "NOPE", "--catalog-dir", str(tmp_path / "absent")])
    assert r.code == 6 and "WARN no catalog in" in r.err

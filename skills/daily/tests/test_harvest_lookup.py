"""The Harvest adapter's catalog lookup, read through the adapter's own function."""
from pathlib import Path

import pytest

import skill_config
from provider import dispatcher
from provider.errors import Misconfigured
from provider.harvest import catalog
from support import assignments_page, project, run_cli, task, write_catalog


def _write_catalog(mcp_dir):
    """Page 1 holds ACM-CR202; a later page holds a different project and a duplicate of
    ACM-CR202, which the reader must yield once."""
    write_catalog(mcp_dir, {
        "harvest_assignments.json": assignments_page(1, 7, [
            project(48084036, "ACM-CR202", "Case Backlog Requirements Implementation Phase 2", [
                task(20753151, "Gen - Development/Configuration", billable=True),
                task(20878969, "Gen - Development/Configuration (NB)", billable=False)])]),
        "harvest_assignments_p7.json": assignments_page(7, 7, [
            project(37122824, "NWC-001", "Admin", [
                task(20759111, "Meeting - Standup Meetings", billable=False)]),
            project(48084036, "ACM-CR202", "Case Backlog Phase 2")]),   # duplicate project id
    })


def test_finds_project_on_first_page_across_pages(tmp_path):
    _write_catalog(str(tmp_path))
    rows = list(catalog._assignments(tmp_path))
    ids = [r["project"]["id"] for r in rows]
    assert ids.count(48084036) == 1          # de-duped across pages
    assert 37122824 in ids


def test_lookup_returns_billable_task(tmp_path):
    _write_catalog(str(tmp_path))
    matches = catalog.from_catalog("ACM-CR202", tmp_path, None)
    assert len(matches) == 1
    m = matches[0]
    assert m["project_id"] == 48084036
    dev = [t for t in m["tasks"] if t["id"] == 20753151][0]
    assert dev["billable"] is True


def _write_client_named_catalog(mcp_dir):
    """One client, two projects: a dead presales shell named for the *client*, and the
    live delivery project named for the *work*. Searching the client's name has to find
    the second one - its name shares no substring with the query."""
    write_catalog(mcp_dir, {"harvest_assignments.json": assignments_page(1, 1, [
        project(1001, "PSO-1000", "Contoso - D365 CRM Foundation",
                [task(2001, "Presales - Meetings", billable=False)], client="Contoso Pty Ltd"),
        project(1002, "CTO2000",
                "Check app access still enabled after the security group migration",
                [task(2002, "Gen - Investigation", billable=True)], client="Contoso Pty Ltd"),
    ])})


def test_lookup_matches_on_client_name(tmp_path):
    """A project findable only by its client used to be invisible. Match on client too, and
    rank code/name hits above client-only hits."""
    _write_client_named_catalog(str(tmp_path))
    matches = catalog.from_catalog("Contoso", tmp_path, None)
    by_code = {m["code"]: m for m in matches}
    assert by_code["CTO2000"]["matched_on"] == "client"
    assert by_code["CTO2000"]["tasks"][0]["billable"] is True
    assert matches[0]["code"] == "PSO-1000"          # name match outranks client-only
    assert by_code["PSO-1000"]["matched_on"] == "code/name"


def test_lookup_tolerates_a_catalog_without_client_names(tmp_path):
    _write_catalog(str(tmp_path))
    assert catalog.from_catalog("ACM-CR202", tmp_path, None)[0]["client"] == ""


def test_cli_exit_6_on_no_match_cache_only(tmp_path):
    """`--cache-only` is what makes this a test rather than a live query, and a miss in a
    catalog that *was* read is the contract's exit 6."""
    _write_catalog(str(tmp_path))
    r = run_cli(dispatcher, ["lookup", "NOPE", "--catalog-dir", str(tmp_path), "--cache-only"])
    assert r.code == 6
    assert "no project matching" in r.err


def test_cli_falls_back_to_history_when_the_catalog_misses(tmp_path, live_harvest):
    """An archived assignment drops out of the catalog while its entries remain. The
    fallback is the only way to recover the project id, so it gets a real exercise against a
    fake API rather than being left to the live one."""
    _write_catalog(str(tmp_path))
    live_harvest({
        ("GET", "/users/me"): (200, {"id": 4242}),
        ("GET", "/time_entries"): (200, {"time_entries": [{
            "project": {"id": 111, "code": "ARCH-9", "name": "Archived project"},
            "task": {"id": 222, "name": "Gen - Development/Configuration"},
            "billable": True,
        }], "next_page": None}),
    })
    r = run_cli(dispatcher, ["lookup", "ARCH-9", "--catalog-dir", str(tmp_path), "--json"])
    assert r.code == 0
    assert r.json()[0]["project_id"] == "111" and r.json()[0]["source"] == "history"
    assert "recovered from own entries" in r.err


def test_a_failed_history_fallback_is_never_reported_as_no_match(tmp_path, live_harvest):
    """ADR-0007: a read that could not finish must not read as "no such project". The
    revoked token on the fallback is a refusal (4), and the warning is on stderr."""
    _write_catalog(str(tmp_path))
    live_harvest({("GET", "/users/me"): (401, {"error": "revoked"})})
    r = run_cli(dispatcher, ["lookup", "ARCH-9", "--catalog-dir", str(tmp_path)])
    assert r.code == 4
    assert "WARN history fallback failed" in r.err


def test_a_catalog_hit_needs_no_credentials(tmp_path):
    """Contract section 5: a command that can be answered without the provider does not
    ask for credentials. The hermetic fixture blanks them, so success here is the proof."""
    _write_catalog(str(tmp_path))
    r = run_cli(dispatcher, ["lookup", "ACM-CR202", "--catalog-dir", str(tmp_path)])
    assert r.code == 0 and r.out.startswith("ACM-CR202  48084036  ")


def test_catalog_dir_honours_workspace_from_env_file(tmp_path, monkeypatch):
    """The reader must read TIMESHEET_WORKSPACE the way the writer does: through the one
    resolver, so a refresh and a lookup cannot disagree about where the catalog lives."""
    ws = tmp_path / "ws"
    (ws / ".mcp").mkdir(parents=True)
    env = tmp_path / ".env"
    env.write_text(f"TIMESHEET_WORKSPACE={ws}\n", encoding="utf-8")
    monkeypatch.setattr(skill_config, "ENV_PATH", env)
    monkeypatch.delenv("TIMESHEET_WORKSPACE", raising=False)

    assert catalog.catalog_dir(None) == ws / ".mcp"


def test_explicit_catalog_dir_wins_over_configured_workspace(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(f"TIMESHEET_WORKSPACE={tmp_path / 'ws'}\n", encoding="utf-8")
    monkeypatch.setattr(skill_config, "ENV_PATH", env)
    assert catalog.catalog_dir("/explicit") == Path("/explicit")   # not str(): Windows spells it \\explicit


def test_a_blank_catalog_dir_does_not_beat_the_configured_workspace(tmp_path, monkeypatch):
    """`--catalog-dir ""` is an omitted flag, not a directory named "". The seam's
    `has_value()` keeps this flag on the same rule as every other one."""
    ws = tmp_path / "ws"
    (ws / ".mcp").mkdir(parents=True)
    env = tmp_path / ".env"
    env.write_text(f"TIMESHEET_WORKSPACE={ws}\n", encoding="utf-8")
    monkeypatch.setattr(skill_config, "ENV_PATH", env)

    assert catalog.catalog_dir("  ") == ws / ".mcp"


def test_reader_and_writer_share_the_one_resolver():
    """A private copy of the resolution logic reappearing here is what caused the bug the
    tests above guard: the two copies drifting apart."""
    import inspect
    assert "skill_config.find_workspace()" in inspect.getsource(catalog.catalog_dir)


def test_no_workspace_and_cache_only_is_missing_configuration(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(skill_config, "SKILL_ROOT", tmp_path / "skills" / "daily")
    with pytest.raises(Misconfigured):
        catalog.lookup("x", None, None, True, 180)

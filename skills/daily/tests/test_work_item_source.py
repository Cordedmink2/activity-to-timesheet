"""The work-item source boundary (#37, ADR-0007): a read boundary — no gate, no credentials.

What these hold, in the order a user meets it:

* **Nothing configured is said, not hidden.** A user whose work items live somewhere with no
  adapter gets a run that says no source is configured, and no catalog file appears. The
  alternative — an empty catalog written and reported healthy — is the bug that opened #37.
* **The old settings shape is named.** `DATAVERSE_URL` / `PAC_AUTH_PROFILE` used to be the
  configuration. They moved into `.context.md`; a run that finds them says where each went.
* **The account's facts come from `.context.md`.** The adapter ships no environment URL, no
  entity and no column names, so a missing one is refused by name rather than defaulted.
* **The adapter is one of a kind.** The seam finds adapters by directory and names none.

Nothing here shells out: the adapter's launcher and `which` are injected, `pac` is never
run, and the hermetic fixture has already pointed the skill `.env` at nothing.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

import refresh_catalogs as rc
from support import run_cli
from work_items import source
from work_items.errors import Misconfigured, Refused

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
PACKAGE = SCRIPTS / "work_items"

CONFIGURED = """\
# Context

## Work-item source

- Adapter: dataverse
- Environment URL: https://example.invalid/
- Auth profile: timesheets
- Entity: widget
- Number column: widgetnumber
- Title column: title
- Modified column: modifiedon
- State column: statecode

### Case creation

Ask Dana to open one.

## Preferences
- Something: else
"""


def write_context(ws: Path, text: str) -> None:
    (ws / "Timesheets" / ".context.md").write_text(text, encoding="utf-8")


class FakePac:
    """Stands in for `subprocess.run` and `shutil.which` — pac is never started."""

    def __init__(self, fetch_stdout="widgetnumber\ttitle\nW1\tOne\nW2\tTwo\n",
                 auth_list="[1]   *  one\n[2]      timesheets\n", fetch_code=0):
        self.calls: list[list[str]] = []
        self.fetch_stdout, self.auth_list, self.fetch_code = fetch_stdout, auth_list, fetch_code
        self.fetch_xml = ""

    def which(self, name):
        return "pac"

    def run(self, argv, **kw):
        self.calls.append(list(argv))
        out, code = "", 0
        if argv[1:3] == ["auth", "list"]:
            out = self.auth_list
        if argv[1:3] == ["env", "fetch"]:
            out, code = self.fetch_stdout, self.fetch_code
            self.fetch_xml = Path(argv[argv.index("--xmlFile") + 1]).read_text(encoding="utf-8")

        class R:
            returncode, stdout, stderr = code, out, ""
        return R()


def refresh(ws, fake=None, **kw):
    fake = fake or FakePac()
    return source.refresh(ws, run=fake.run, which=fake.which, **kw), fake


# --- nothing configured ------------------------------------------------------------------

def test_no_context_file_says_no_source_is_configured_and_writes_no_catalog(workspace):
    outcome, fake = refresh(workspace)
    assert outcome.kind == "not-configured"
    assert "no work-item source" in outcome.message.lower()
    assert "Work-item source" in outcome.message, "it must say where to configure one"
    assert list((workspace / ".mcp").iterdir()) == []
    assert fake.calls == []


def test_a_context_without_the_section_is_the_same_statement(workspace):
    write_context(workspace, "## Preferences\n- Something: else\n")
    outcome, _ = refresh(workspace)
    assert outcome.kind == "not-configured"
    assert list((workspace / ".mcp").iterdir()) == []


def test_the_starter_templates_placeholders_are_not_a_configured_source(workspace):
    write_context(workspace, "## Work-item source\n- Adapter: <adapter name>\n"
                             "- Environment URL: <url>\n")
    outcome, fake = refresh(workspace)
    assert outcome.kind == "not-configured"
    assert fake.calls == []


def test_the_cli_exits_zero_and_says_so_on_stdout(workspace):
    r = run_cli(rc, [])
    assert r.code == 0
    assert "no work-item source" in r.out.lower()
    assert list((workspace / ".mcp").iterdir()) == []


# --- the old settings shape --------------------------------------------------------------

@pytest.mark.parametrize("key,where", [("DATAVERSE_URL", "Environment URL"),
                                       ("PAC_AUTH_PROFILE", "Auth profile")])
def test_an_old_setting_with_nothing_in_context_md_is_named_and_refused(
        workspace, monkeypatch, key, where):
    monkeypatch.setenv(key, "value")
    with pytest.raises(Misconfigured) as exc:
        refresh(workspace)
    msg = str(exc.value)
    assert key in msg and where in msg and ".context.md" in msg
    assert list((workspace / ".mcp").iterdir()) == []


def test_the_old_shape_is_found_in_the_skill_env_file_too(workspace, env_file):
    env_file.write_text(f"TIMESHEET_WORKSPACE={workspace}\nDATAVERSE_URL=https://x.invalid/\n",
                        encoding="utf-8")
    with pytest.raises(Misconfigured, match="DATAVERSE_URL"):
        refresh(workspace)


def test_the_cli_exits_three_for_the_old_shape(workspace, monkeypatch):
    monkeypatch.setenv("DATAVERSE_URL", "https://x.invalid/")
    r = run_cli(rc, [])
    assert r.code == 3
    assert "DATAVERSE_URL" in r.err


def test_a_configured_source_with_old_settings_left_behind_warns_they_are_ignored(
        workspace, monkeypatch):
    write_context(workspace, CONFIGURED)
    monkeypatch.setenv("PAC_AUTH_PROFILE", "old")
    outcome, fake = refresh(workspace)
    assert outcome.kind == "refreshed"
    assert "PAC_AUTH_PROFILE" in outcome.message and "ignored" in outcome.message
    assert "old" not in " ".join(" ".join(c) for c in fake.calls), "the old value was used"


# --- a configured source -----------------------------------------------------------------

def test_a_configured_source_writes_the_catalog_and_reports_the_count(workspace):
    write_context(workspace, CONFIGURED)
    outcome, fake = refresh(workspace)
    assert outcome.kind == "refreshed" and outcome.count == 2
    catalog = workspace / ".mcp" / "work_item_catalog.txt"
    assert catalog.read_text(encoding="utf-8") == "widgetnumber\ttitle\nW1\tOne\nW2\tTwo\n"
    assert "2 work items" in outcome.message


def test_the_query_is_built_from_context_md_not_from_the_adapter(workspace):
    write_context(workspace, CONFIGURED)
    _, fake = refresh(workspace)
    xml = fake.fetch_xml
    assert 'name="widget"' in xml
    for column in ("widgetnumber", "title", "modifiedon", "statecode"):
        assert column in xml
    assert any(c[1:3] == ["env", "fetch"] for c in fake.calls)
    assert "https://example.invalid/" in " ".join(c for call in fake.calls for c in call)


@pytest.mark.parametrize("missing", ["Environment URL", "Auth profile", "Entity",
                                     "Number column", "Title column", "Modified column",
                                     "State column"])
def test_a_missing_account_fact_is_refused_by_name_never_defaulted(workspace, missing):
    write_context(workspace, "\n".join(
        line for line in CONFIGURED.splitlines() if not line.startswith(f"- {missing}:")))
    with pytest.raises(Misconfigured) as exc:
        refresh(workspace)
    assert missing in str(exc.value)


def test_an_unknown_adapter_is_refused_and_lists_the_ones_that_exist(workspace):
    write_context(workspace, "## Work-item source\n- Adapter: nonesuch\n")
    with pytest.raises(Misconfigured) as exc:
        refresh(workspace)
    assert "nonesuch" in str(exc.value)
    assert all(name in str(exc.value) for name in source.adapter_names())


def test_adapters_are_discovered_from_the_directory_and_the_seam_names_none():
    assert source.adapter_names(), "no adapter found: discovery matched nothing"
    tree = ast.parse((PACKAGE / "source.py").read_text(encoding="utf-8"))
    strings = {n.value.lower() for n in ast.walk(tree)
               if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    for name in source.adapter_names():
        assert not any(name in s for s in strings), f"source.py names the adapter {name!r}"


def test_the_users_active_profile_is_restored_after_a_refresh(workspace):
    write_context(workspace, CONFIGURED)
    _, fake = refresh(workspace)
    selects = [c for c in fake.calls if c[1:3] == ["auth", "select"]]
    assert selects[0][3:] == ["--name", "timesheets"]
    assert selects[-1][3:] == ["--index", "1"]


def test_an_unreadable_profile_list_warns_instead_of_silently_switching(workspace):
    write_context(workspace, CONFIGURED)
    outcome, _ = refresh(workspace, FakePac(auth_list="garbled\n"))
    assert "WARN" in outcome.message and "timesheets" in outcome.message


def test_pac_missing_is_a_misconfiguration(workspace):
    write_context(workspace, CONFIGURED)
    fake = FakePac()
    with pytest.raises(Misconfigured, match="pac"):
        source.refresh(workspace, run=fake.run, which=lambda name: None)


def test_a_failed_fetch_is_a_refusal_and_leaves_the_catalog_as_it_was(workspace):
    write_context(workspace, CONFIGURED)
    catalog = workspace / ".mcp" / "work_item_catalog.txt"
    catalog.write_text("old\n", encoding="utf-8")
    with pytest.raises(Refused):
        refresh(workspace, FakePac(fetch_code=1))
    assert catalog.read_text(encoding="utf-8") == "old\n"


@pytest.mark.parametrize("stdout", ["", "widgetnumber\ttitle\n", "\n\n"])
def test_a_catalog_that_comes_back_empty_is_a_failure_not_a_healthy_empty_one(
        workspace, stdout):
    write_context(workspace, CONFIGURED)
    catalog = workspace / ".mcp" / "work_item_catalog.txt"
    catalog.write_text("old\n", encoding="utf-8")
    with pytest.raises(Refused, match="no work items"):
        refresh(workspace, FakePac(fetch_stdout=stdout))
    assert catalog.read_text(encoding="utf-8") == "old\n"


def test_the_cli_maps_a_refusal_to_exit_four(workspace, monkeypatch):
    write_context(workspace, CONFIGURED)
    fake = FakePac(fetch_code=1)
    monkeypatch.setattr(source, "_default_run", fake.run)
    monkeypatch.setattr(source, "_default_which", fake.which)
    r = run_cli(rc, [])
    assert r.code == 4 and r.err.startswith("ERR")


# --- the boundary's own rules (ADR-0007) -------------------------------------------------

def package_sources():
    return sorted(PACKAGE.rglob("*.py"))


def test_the_package_is_not_empty():
    assert len(package_sources()) >= 4


def test_a_read_boundary_carries_no_gate_and_no_credential():
    """ADR-0007: credentials and the confirmation gate belong at the write boundary only.
    Read from the code's string literals and imports, so prose explaining the rule is free
    to say the word."""
    for path in package_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        literals = [n.value for n in ast.walk(tree)
                    if isinstance(n, ast.Constant) and isinstance(n.value, str)
                    and not n.value.strip().startswith(("The ", "A ", "Read", "One"))]
        for forbidden in ("--confirm", "HARVEST_", "API_KEY", "PASSWORD", "TOKEN"):
            assert not any(forbidden in lit.upper() for lit in literals), (
                f"{path.name} carries {forbidden!r}")
        assert "provider_config" not in imported_modules(path), path.name


def imported_modules(path: Path) -> set[str]:
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
    return found


def test_neither_half_imports_the_other():
    for path in package_sources():
        assert not imported_modules(path) & {"provider", "aw_client"}, path.name
    for path in sorted((SCRIPTS / "provider").rglob("*.py")):
        assert "work_items" not in imported_modules(path), path.name

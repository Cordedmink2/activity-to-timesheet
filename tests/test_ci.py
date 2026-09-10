"""Guards on the two workflows in `.github/workflows/` (#45).

Read as text rather than parsed — the suite carries no YAML dependency and these are shape
checks, not a schema. What each holds is pinned to something written elsewhere in the repo:
the verification commands to `AGENTS.md`, which is where a maintainer is told what to run,
and the release trigger to the tag form `docs/CONTRIBUTING.md` § Releasing prescribes. A
workflow that drifted from either would report green on a check nobody asked for.
"""

import re

from shipped import REPO

WORKFLOWS = REPO / ".github" / "workflows"
CHECKS = WORKFLOWS / "checks.yml"
RELEASE = WORKFLOWS / "release.yml"
AGENTS = REPO / "AGENTS.md"


def agents_section(title: str) -> str:
    text = AGENTS.read_text(encoding="utf-8")
    found = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert found, f"AGENTS.md has no `## {title}` section"
    return found.group(1)


def verification_commands() -> list[str]:
    """The commands AGENTS.md tells a maintainer to run before reporting a change complete —
    the fenced block in that section, one command per line."""
    block = re.search(r"```\n(.*?)```", agents_section("Before reporting a change complete"),
                      re.S)
    assert block, "AGENTS.md's verification section has no fenced command block"
    commands = [line.strip() for line in block.group(1).splitlines() if line.strip()]
    assert commands, "the fenced block is empty"
    return commands


def test_both_workflows_exist():
    assert CHECKS.is_file(), "no checks workflow — nothing gates a push or a pull request"
    assert RELEASE.is_file(), "no release workflow — a tag publishes nothing"


def test_the_checks_workflow_runs_exactly_the_commands_agents_md_prescribes():
    """One list of what "verified" means, and the workflow runs it verbatim. The command's
    two test paths are the point: a run started inside `skills/daily/` is scoped by that
    folder's `pytest.ini` to the skill's own suite and skips every repo-level guard."""
    text = CHECKS.read_text(encoding="utf-8")
    for command in verification_commands():
        assert command in text, (
            f"AGENTS.md says to run `{command}` and the checks workflow does not:\n{text}")
    assert "working-directory" not in text, (
        "the checks workflow changes directory; the commands are written for the repo root")


def test_the_checks_workflow_runs_on_both_platforms():
    """Not optional: the installers are PowerShell, the screenshot pipeline is Windows-only,
    and the session hook is `sh`. A single platform leaves the other half unexercised."""
    text = CHECKS.read_text(encoding="utf-8")
    for runner in ("windows-latest", "ubuntu-latest"):
        assert runner in text, f"the checks workflow never runs on {runner}"


def test_the_checks_workflow_gates_pushes_to_main_and_pull_requests():
    text = CHECKS.read_text(encoding="utf-8")
    assert re.search(r"^\s+pull_request:", text, re.M), "pull requests are not checked"
    assert re.search(r"^\s+branches:\s*\[?\s*main", text, re.M), "pushes to main are not checked"


def test_the_release_workflow_publishes_the_changelog_section_for_a_version_tag():
    """The tag form is CONTRIBUTING's `vX.Y.Z`, and the body is the heading
    `test_every_version_marker_agrees` already holds equal to the manifest — so the release
    notes are written once, in the changelog, and a tag without a section fails here."""
    text = RELEASE.read_text(encoding="utf-8")
    assert re.search(r"tags:\s*\[\s*[\"']v\*[\"']\s*\]", text), (
        "the release workflow is not triggered by `v*` tags")
    assert "CHANGELOG.md" in text, "the release body is not taken from CHANGELOG.md"
    assert "gh release create" in text, "nothing in the workflow creates a release"
    assert "contents: write" in text, "the workflow lacks the permission to create a release"


def test_agents_md_names_who_cuts_a_tag_and_when():
    """The step lost its owner when the release skill was retired; the ticket puts one back
    here, beside the workflow that reacts to it."""
    releasing = agents_section("Releasing")
    assert "release.yml" in releasing, (
        "AGENTS.md § Releasing does not name the workflow a tag triggers")
    assert re.search(r"\bmaintainer\b", releasing), (
        "AGENTS.md § Releasing does not say who cuts the tag")
    assert re.search(r"green|passed|Checks", releasing), (
        "AGENTS.md § Releasing does not say when — which checks have to pass first")

"""The install checks live once (guided-setup T6, US-6/AC-2, US-5/AC-1).

Setup's steps, `troubleshoot` and `onboard-client` all need the same checks. If each kept
its own copy the copies would drift, so every check is one entry in
`skills/setup/references/checks.md`, in setup order, and the skills cite it by id.
"""
import re

import pytest

import shipped
from shipped import REPO, SKILLS

SETUP = SKILLS / "setup"
CHECKS = SETUP / "references" / "checks.md"
INSTALL_COMMANDS = SETUP / "references" / "install-commands.md"
CHECK_IDS = ["activity-source", "browser-extensions", "profile-tags", "category-rules",
             "screenshot-task", "calendar", "checkin-watchers"]


def checks_text() -> str:
    return CHECKS.read_text(encoding="utf-8") if CHECKS.is_file() else ""


def entries() -> dict[str, str]:
    """Each `## Check <id>` entry of checks.md as {id: body}."""
    found = re.split(r"^## Check ([a-z-]+)\b.*$", checks_text(), flags=re.M)[1:]
    return dict(zip(found[0::2], found[1::2]))


def shipped_markdown() -> dict[str, str]:
    return {p.relative_to(REPO).as_posix(): p.read_text(encoding="utf-8")
            for skill in shipped.skill_dirs() for p in sorted(skill.rglob("*.md"))}


def test_checks_reference_ships_with_one_entry_per_check_in_setup_order():
    assert CHECKS.is_file(), "there is no skills/setup/references/checks.md"
    assert list(entries()) == CHECK_IDS


@pytest.mark.parametrize("check", CHECK_IDS)
def test_every_check_has_a_probe_and_a_failure_answer(check):
    body = entries().get(check, "")
    assert "**Verify**" in body, f"check {check} has no verify"
    assert "**If it fails**" in body, f"check {check} has no failure answer"


def test_each_setup_step_cites_its_check_by_id_in_order():
    text = shipped.skill_md_text(SETUP)
    cited = re.findall(r"\*\*Verify\*\* and \*\*If it fails\*\* — run `references/checks\.md` "
                       r"\(check `([a-z-]+)`\)", text)
    assert cited == CHECK_IDS


def test_setup_skill_no_longer_carries_the_verify_text():
    """The probe prose is moved, not copied: SKILL.md keeps only the citation."""
    text = shipped.skill_md_text(SETUP)
    assert "Get-ScheduledTaskInfo" not in text
    assert "/api/0/buckets/" not in text
    assert "Unregister-ScheduledTask" not in text


# Files that name a probe for another purpose, on purpose: the daily skill's API reference
# says how to read the activity source at all, first-run.md and reconcile read a task that
# has already stopped, a different job from installing it. They are not install checks.
OTHER_PURPOSE = {
    "skills/daily/references/activitywatch.md",
    "skills/daily/references/first-run.md",
    "skills/reconcile/SKILL.md",
}


def probes() -> list[str]:
    """Every command-shaped inline span in checks.md."""
    spans = re.findall(r"`([^`\n]+)`", checks_text())
    return sorted({s for s in spans if re.match(
        r"(GET |Get-ScheduledTask|Unregister-|python |py )", s)})


def test_checks_reference_has_probes_to_guard():
    assert len(probes()) >= 5


@pytest.mark.parametrize("probe", probes() or ["<none>"])
def test_a_probe_appears_in_one_shipped_file_only(probe):
    """An exact inline span, so prose that merely mentions an endpoint is not a copy."""
    holders = [name for name, text in shipped_markdown().items()
               if f"`{probe}`" in text and name not in OTHER_PURPOSE]
    assert holders == [CHECKS.relative_to(REPO).as_posix()], (
        f"probe `{probe}` is written in {holders}; a check lives once, in checks.md")


def test_the_package_manager_table_lives_in_install_commands_only():
    assert INSTALL_COMMANDS.is_file()
    assert "winget install -e --id ActivityWatch.ActivityWatch" in INSTALL_COMMANDS.read_text(
        encoding="utf-8")
    holders = [name for name, text in shipped_markdown().items()
               if "winget install -e --id ActivityWatch.ActivityWatch" in text]
    assert holders == [INSTALL_COMMANDS.relative_to(REPO).as_posix()]

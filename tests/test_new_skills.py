"""The two small skills the menu routes to: `onboard-client` and `troubleshoot`
(guided-setup T10, T11, T14; US-1/AC-2, US-4, US-5/AC-1, US-6/AC-2, US-6/AC-3)."""
import re

import pytest

import shipped
from shipped import SKILLS

ONBOARD = SKILLS / "onboard-client"
TROUBLE = SKILLS / "troubleshoot"
SETUP = SKILLS / "setup"
NEW = pytest.mark.parametrize("skill", [ONBOARD, TROUBLE], ids=lambda p: p.name)
CEILING = 5000


def text(skill):
    return shipped.skill_md_text(skill)


@NEW
def test_the_skill_ships_with_frontmatter_that_names_it(skill):
    assert (skill / "SKILL.md").is_file()
    meta = shipped.frontmatter(text(skill))
    assert meta.get("name") == skill.name and meta.get("description")


@NEW
def test_the_skill_can_be_reached_by_what_the_user_says(skill):
    """No `disable-model-invocation`: "I've got a new client" has to reach it directly."""
    assert "disable-model-invocation" not in text(skill).split("---", 2)[1]


def test_the_descriptions_open_with_the_phrases_a_user_says():
    assert shipped.frontmatter(text(ONBOARD))["description"].lower().startswith(
        "use when the user says they have a new client")
    assert shipped.frontmatter(text(TROUBLE))["description"].lower().startswith(
        "use when something stopped working")


@NEW
def test_the_skill_stays_under_the_size_ceiling(skill):
    assert len(text(skill).split()) < CEILING


@NEW
@pytest.mark.parametrize("sibling", ["daily", "billables-daily"])
def test_the_skill_finds_its_siblings_on_either_install_shape(skill, sibling):
    assert re.search(rf"(?<![\w-]){re.escape(sibling)}(?![\w-])", shipped.shipped_text(skill))
    assert re.search(r"(?<![\w-])(setup|billables-setup)(?![\w-])", text(skill))


# -- onboard-client -----------------------------------------------------------------------

def test_onboarding_asks_only_for_decisions_and_finds_facts_itself():
    body = text(ONBOARD)
    assert re.search(r"only for decisions|only the decisions", body, re.I)
    assert "--inspect" in body and "`HOST`" in body


def test_onboarding_shows_the_diff_and_writes_file_and_rules_in_the_same_step():
    body = text(ONBOARD)
    assert re.search(r"\bdiff\b", body, re.I) and re.search(r"\byes\b", body, re.I)
    assert body.index("diff") < body.index("--from-context")
    assert re.search(r"same step|in one step|together", body, re.I)


def test_onboarding_keeps_no_second_list_of_terms_and_cites_the_one_home():
    body = text(ONBOARD)
    assert "references/choosing-terms.md" in body and "references/checks.md" in body
    assert "--candidates" not in body and '"terms"' not in body
    assert "no separate list" in body.lower() or "no other list" in body.lower()


def test_an_unrecorded_client_is_reported_as_not_yet_seen_and_not_a_failure():
    body = text(ONBOARD)
    assert "not yet seen" in body
    assert re.search(r"not a failure", body, re.I)


def test_onboarding_never_writes_over_the_context_file_without_a_yes():
    assert re.search(r"never (write|overwrite)[^.]*without|only after a yes", text(ONBOARD), re.I)


# -- troubleshoot -------------------------------------------------------------------------

def test_troubleshooting_runs_the_checks_in_order_and_stops_at_the_first_failure():
    body = text(TROUBLE)
    assert "references/checks.md" in body
    assert re.search(r"in (setup )?order", body, re.I)
    assert re.search(r"stop(s)? at the first", body, re.I)


def test_troubleshooting_cites_the_existing_references_rather_than_copying_them():
    body = text(TROUBLE)
    assert "references/endpoint-security.md" in body
    assert "first-run.md" in body
    assert "Unregister-ScheduledTask" not in body and "/api/0/" not in body


def test_troubleshooting_names_the_missing_interpreter_fault_and_gives_the_documented_fix():
    body = text(TROUBLE)
    assert re.search(r"missing interpreter|interpreter .* (is )?(gone|missing)", body, re.I)
    assert "0x80070002" in shipped.shipped_text(SETUP)
    assert "check `screenshot-task`" in body


def test_troubleshooting_handles_a_screenshots_stopped_start_with_the_screenshot_check():
    body = text(TROUBLE)
    assert re.search(r"screenshots? stopped", body, re.I)
    assert re.search(r"starts? (at|with) (the )?(screenshot|that check)", body, re.I)


# -- both ---------------------------------------------------------------------------------

@NEW
def test_the_new_skills_carry_no_probe_or_install_command_text(skill):
    body = shipped.shipped_text(skill)
    for probe in ("winget install", "brew install", "Get-ScheduledTaskInfo"):
        assert probe not in body


def test_no_probe_text_is_copied_into_either_new_skill():
    checks = (SETUP / "references" / "checks.md").read_text(encoding="utf-8")
    probes = {s for s in re.findall(r"`([^`\n]+)`", checks)
              if re.match(r"(GET |Get-ScheduledTask|Unregister-)", s)}
    for skill in (ONBOARD, TROUBLE):
        body = shipped.shipped_text(skill)
        assert not [p for p in probes if p in body]

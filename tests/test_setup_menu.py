"""Setup's front door: the menu, the human-only list, the existing-machine path and the
hand-over-only feedback (guided-setup T8, T9, T12; US-1, US-2/AC-1, US-5/AC-2, US-7/AC-1)."""
import re

import shipped
from shipped import SKILLS

SETUP = SKILLS / "setup"
REPORTING = SKILLS / "daily" / "references" / "reporting-issues.md"
CHECKS = SETUP / "references" / "checks.md"


def text() -> str:
    return shipped.skill_md_text(SETUP)


def section(heading: str) -> str:
    found = shipped.section(text(), heading)
    assert found, f"setup has no '## {heading}' section"
    return found


MENU = "What do you want to do?"
HUMAN = "What only a person does"
EXISTING = "A machine that already has some of it"


def test_the_menu_comes_before_any_install_step():
    body = text()
    assert body.index(f"## {MENU}") < body.index("## Before you start") < body.index("## Steps")


def test_the_menu_offers_the_five_choices_in_plain_words():
    menu = section(MENU)
    choices = re.findall(r"^\d\. \*\*(.+?)\*\*", menu, re.M)
    assert len(choices) == 5, choices
    low = " ".join(choices).lower()
    for phrase in ("new machine", "already has some", "new client", "stopped working",
                   "problem"):
        assert phrase in low, f"the menu never offers {phrase!r}: {choices}"


def test_each_choice_leads_to_a_distinct_path():
    menu = section(MENU)
    targets = [line.split("→", 1)[1].strip()
               for line in menu.splitlines() if re.match(r"^\d\. ", line) and "→" in line]
    assert len(targets) == 5 and len(set(targets)) == 5, targets
    joined = " ".join(targets)
    for needed in ("Before you start", EXISTING, "onboard-client", "troubleshoot",
                   "reporting-issues.md"):
        assert needed in joined, f"no choice leads to {needed}"


def test_a_user_who_names_their_job_is_not_asked_the_menu():
    menu = section(MENU)
    assert re.search(r"already (said|named|told)", menu, re.I)
    assert "new client" in menu and "stopped" in menu
    assert re.search(r"do not ask|never ask|skip the menu|without asking", menu, re.I)


def test_the_human_only_list_is_one_section_that_names_each_human_step():
    human = section(HUMAN).lower()
    for needed in ("add", "administrator", "consent", "credential", "configuration dialog"):
        assert needed in human, f"the human-only list never says {needed!r}"
    assert text().count(f"## {HUMAN}") == 1
    assert "no new install that needs administrator" in human.replace("\n", " ")


def test_other_sections_cite_the_human_only_list_rather_than_restating_it():
    assert text().count(HUMAN) >= 2


def blockquotes() -> list[str]:
    groups, current = [], []
    for line in text().splitlines():
        if line.startswith(">"):
            current.append(line)
        elif current:
            groups.append("\n".join(current))
            current = []
    return groups


COMMAND = re.compile(r"^(python|py|pip|winget|brew|Get-|Start-|Set-|Unregister|powershell|"
                     r"bash|curl|gh |git )|--[a-z]|[A-Za-z]:\\")


def test_no_instruction_to_the_user_asks_them_to_type_a_command_or_a_path():
    for group in blockquotes():
        for span in re.findall(r"`([^`]+)`", group):
            assert not COMMAND.search(span), f"the user is handed a command or path: {span}"


def test_the_one_regular_expression_a_user_types_is_the_named_fallback():
    """Only where this ActivityWatch build refuses the write; the human-only list says so."""
    typed = [g for g in blockquotes() if re.search(r"`[^`]*\|[^`]*`", g)]
    assert len(typed) == 1 and "Add one category for each client" in typed[0]
    assert "refuses the write" in section(HUMAN)


def test_the_existing_machine_path_reads_each_check_skips_what_passes_and_asks_before_a_write():
    path = section(EXISTING)
    assert "references/checks.md" in path
    assert re.search(r"in order|each check", path, re.I)
    assert re.search(r"skip", path, re.I) and re.search(r"only what is missing|only the missing",
                                                       path, re.I)
    assert re.search(r"diff", path, re.I) and re.search(r"\byes\b", path, re.I)
    assert re.search(r"never (write|overwrite)[^.]*(context file|rules)", path, re.I)


def test_the_existing_machine_path_copies_no_probe_text():
    path = section(EXISTING)
    assert "/api/0/" not in path and "Get-ScheduledTask" not in path


def test_the_feedback_choice_hands_a_draft_over_and_never_files():
    menu = section(MENU)
    assert "daily/references/reporting-issues.md" in menu or "reporting-issues.md" in menu
    feedback = [l for l in menu.splitlines() if "reporting-issues" in l][0]
    assert "gh issue create" not in text()
    assert re.search(r"hand|give", menu, re.I) and re.search(r"never (send|file|post)", menu,
                                                              re.I)
    assert feedback


def test_the_reporting_reference_carries_the_menu_entry_and_keeps_the_redaction():
    body = REPORTING.read_text(encoding="utf-8")
    assert "## From the setup menu" in body
    entry = body.split("## From the setup menu", 1)[1].split("\n## ", 1)[0]
    assert re.search(r"never (run|file|post|send)", entry, re.I)
    assert "Timesheets/<date>_skill-issue.md" in entry and "gh issue create" in entry
    assert "client name" in entry.lower() and "host" in entry.lower() and "answer" in entry.lower()
    assert "## Redact before drafting, not after" in body


def test_the_runs_own_filing_route_is_unchanged():
    body = REPORTING.read_text(encoding="utf-8")
    filing = body.split("## Filing", 1)[1].split("\n## ", 1)[0]
    assert "You may file it — after showing the user and getting an explicit yes." in filing

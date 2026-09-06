"""Guards on the `daily` skill's workflow prose, from outside the skill.

The skill's own suite (`skills/daily/tests/`) ships inside the skill and reads only what
ships with it — so it can hold `SKILL.md` against the scripts beside it, and cannot hold it
against `CONTEXT.md`, which stays in the repo. That is what this module is for: the
assertions that need both the skill and the repo's glossary in front of them, in the same
place as the other two per-skill prose guards (`test_setup_skill.py`,
`test_reconcile_skill.py`).

Scoped to the **Workflow** section on purpose. Every fact below is also written in the
"Files in this skill" inventory, and that inventory is where a script lands the day it is
written — before any step runs it. An assertion over the whole file would therefore have
passed while the calendar was shipped and unread, which is precisely the state #53 exists
to end: what these tests measure is that a *run* reaches the wrapper, not that the skill
knows it is there.
"""

import re

import pytest

import shipped
from shipped import CONTEXT_MD, SKILLS

DAILY = SKILLS / "daily"
WRAPPER = DAILY / "scripts" / "calendar_day.py"

# The vocabulary the wrapper's verdict is written in — the two words a rule needs in order
# to say which events become blocks and which do not. Held against the wrapper's own source
# as well as the prose, so renaming the field fails here and names the prose that has to
# move with it.
#
# Matched on word boundaries, because "corroborated" is a substring of "uncorroborated":
# a plain `in` would pass the positive case on a document that only ever says the negative,
# which is the half of the rule that bills nothing.
VERDICT_WORDS = ("corroborated", "uncorroborated")


def says(text: str, term: str) -> bool:
    """Whether `text` uses `term` as a word, case-insensitively."""
    return re.search(rf"\b{re.escape(term)}\b", text, re.I) is not None


def workflow() -> str:
    """The `## Workflow` section of `SKILL.md` — the steps a run actually walks."""
    found = shipped.section(shipped.skill_md_text(DAILY), "Workflow")
    assert found, (
        "no `## Workflow` section in the daily SKILL.md, so these checks have nothing to "
        "read. If the heading was retitled, retitle it here too.")
    return found


def wrapper_source() -> str:
    return WRAPPER.read_text(encoding="utf-8")


def glossary_calendar_terms() -> list[str]:
    """The terms `CONTEXT.md` bolds in its **Calendar** entry.

    Read out of the paragraph rather than listed here, so a term added to the glossary is
    one the rules are held to from that moment. Bolding is how that file marks a word as
    vocabulary; the prose around it is explanation.
    """
    text = CONTEXT_MD.read_text(encoding="utf-8")
    match = re.search(r"^\*\*Calendar\*\* —.*?(?=\n\n)", text, re.M | re.S)
    assert match, (
        "no **Calendar** glossary entry in CONTEXT.md — the check has nothing to read")
    terms = re.findall(r"\*\*([^*]+)\*\*", match.group(0))
    assert terms, "the **Calendar** entry bolds no terms — the check has nothing to read"
    return terms


def test_the_workflow_names_the_calendar_wrapper_it_ships():
    """A source a run never runs is a source the user configured and did not get.

    The command shape matters as much as the name: `SKILL.md` defines
    `python scripts/<name>.py` as skill-relative, and that is the form the skill's own
    `test_references.py` holds against what ships. Step 3 has named the wrapper in passing
    since #52 — as the owner of the meeting-title pattern — so this asserts on the
    invocation, which only a step that runs it can carry.
    """
    assert WRAPPER.is_file(), f"{WRAPPER.name} is the wrapper this asserts on and is not shipped"
    assert f"scripts/{WRAPPER.name}" in workflow(), (
        f"no step of the daily skill's workflow runs `scripts/{WRAPPER.name}`. The calendar "
        "is a fourth source (ADR-0008); a run that never invokes the wrapper reads the day "
        "without it and loses the meetings the toggle exists to catch.")


def test_the_workflow_names_the_toggle_that_gates_the_calendar():
    """Read off the wrapper's own constant, so renaming the setting fails here.

    The toggle is what tells a run that a refusal may be an ordinary state rather than a
    failure — the calendar being off is most installs, and stopping the run on it would
    break every day for every user who never opted in.
    """
    match = re.search(r'^TOGGLE = "([A-Z_]+)"', wrapper_source(), re.M)
    assert match, f"no `TOGGLE = \"...\"` in {WRAPPER.name} — the check has nothing to read"
    key = match.group(1)
    assert key in workflow(), (
        f"the daily skill's workflow does not name {key}, the setting that decides whether "
        f"the calendar is read at all. A run that cannot tell 'off' from 'unreadable' either "
        f"stops on a machine that never opted in or bills a day whose calendar failed.")


@pytest.mark.parametrize("word", VERDICT_WORDS)
def test_the_wrapper_still_uses_the_verdict_word_the_rules_are_written_in(word):
    """The other side of the check below — this one reads the wrapper's source, not its
    output, because what the prose has to keep in step with is the field name a run will
    be looking at in the JSON."""
    assert says(wrapper_source(), word), (
        f"{WRAPPER.name} no longer says {word!r}. The workflow's calendar rules are written "
        f"in that word; move them with it.")


def test_the_workflow_uses_the_glossarys_calendar_vocabulary():
    """The positive half of the vocabulary guard — the denylist in
    `test_provider_neutrality.py` says what the rules stopped saying, not that what they
    say now is the shared word.

    The calendar's terms are the ones most at risk of drift, because every synonym for them
    is idiomatic English: a rule that says "appointment" or "meeting" for the item on the
    calendar reads perfectly and stops being about the same thing as the glossary, the ADR
    and the wrapper's output.
    """
    text = workflow()
    missing_terms = [t for t in glossary_calendar_terms() if not says(text, t)]
    missing_words = [w for w in VERDICT_WORDS if not says(text, w)]
    assert not (missing_terms or missing_words), (
        f"the daily skill's workflow is missing calendar vocabulary.\n"
        f"  terms CONTEXT.md § \"The services\" bolds: {missing_terms or 'all present'}\n"
        f"  verdict words {WRAPPER.name} prints: {missing_words or 'all present'}\n"
        "ADR-0008 depends on the distinction those words carry; the rules that read the "
        "calendar have to be written in the same ones.")

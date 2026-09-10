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
RULE_COMPILER = DAILY / "scripts" / "category_rules.py"

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


def steps() -> list[str]:
    """Every `### Step N — …` subsection of the workflow, body included.

    Enumerated out of the document rather than listed here, so a step added or renumbered
    is one the checks below read from that moment.
    """
    return re.findall(r"^### Step \d+ —.*?(?=^### |\Z)", workflow(), re.M | re.S)


def presentation_step() -> str:
    """The step that shows the user the proposal — keyed on its title, like
    `shipped.section` is keyed on its heading, so renumbering the steps does not silently
    empty the checks that read it."""
    found = [s for s in steps() if s.splitlines()[0].endswith("Present the proposed timesheet")]
    assert len(found) == 1, (
        "no single `### Step N — Present the proposed timesheet` in the daily skill's "
        "workflow, so these checks have nothing to read. If the step was retitled, retitle "
        f"it here too. Step titles found: {[s.splitlines()[0] for s in steps()]}")
    return found[0]


def review_question() -> str:
    """The blockquote the presentation step asks the user, lines joined.

    The quoted question is the part the step puts to the user in so many words, so a fact
    stated in the prose around it and left out of the quote is one they may never be told.
    """
    quoted = [ln for ln in presentation_step().splitlines() if ln.startswith(">")]
    assert quoted, (
        "the presentation step asks the user nothing — no `> ` blockquote in it. The "
        "review question is what the counts below are counted for.")
    return " ".join(quoted)


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


def test_the_workflow_checks_the_category_rules_before_it_reads_the_timeline():
    """#74: the rules are a derived copy of the signals in `.context.md`, and the timeline
    labels every span with them.

    The order is the assertion. A staleness check that runs *after* the timeline reads the
    day is a check whose answer arrives too late to matter: the labels are already wrong,
    every one of them silently, and a rebuild at that point fixes tomorrow. Both commands
    are read as their first occurrence in the workflow, which is where a run meets them.
    """
    assert RULE_COMPILER.is_file(), f"{RULE_COMPILER.name} is what this checks and is not shipped"
    text = workflow()
    check = text.find(f"scripts/{RULE_COMPILER.name}")
    timeline = text.find("scripts/activity_timeline.py")
    assert check >= 0, (
        f"no step of the workflow runs `scripts/{RULE_COMPILER.name}`, so a client added to "
        "`.context.md` never reaches the rules the timeline is labelled by")
    assert "--status" in text, (
        "the workflow never runs the staleness check, so a rebuild either happens on every "
        "run or on none")
    assert timeline >= 0 and check < timeline, (
        "the workflow reads the timeline before it checks whether the category rules are "
        "current, so a run with stale rules mislabels the day it has already read")


def test_step_2_carries_the_two_words_the_staleness_check_answers_with():
    """Both verdicts exit 0, so the exit code separates nothing — the words are the whole
    difference, exactly as the calendar wrapper's two refusals are.

    Read out of `status()`'s own source, so re-wording either one fails here and names the
    step that has to move with it, rather than leaving Step 2 branching on a word no run
    will ever see.
    """
    source = RULE_COMPILER.read_text(encoding="utf-8")
    status = source.split("def status(", 1)[-1].split("\ndef ", 1)[0]
    text = workflow()
    for verdict in ("CURRENT", "STALE"):
        assert f'"{verdict}' in status or f"'{verdict}" in status, (
            f"`status()` no longer answers {verdict} — Step 2 branches on that word")
        assert verdict in text, (
            f"the workflow never says what to do about {verdict}, so a run has nothing to "
            "branch on when the check comes back")


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


def test_the_presentation_step_puts_the_uncorroborated_events_to_the_user():
    """An event nobody is asked about is an event the run read and dropped.

    Step 3 refuses to draft one — the calendar's word alone does not bill — and that
    refusal is the whole rule until the presentation step asks. ADR-0008: an uncorroborated
    event is a question, and becomes a block only when the user says so.
    """
    assert says(presentation_step(), "uncorroborated"), (
        "the daily skill's presentation step says nothing about uncorroborated calendar "
        "events. Step 3 leaves them out of the table by design, so a step that does not "
        "list them as questions loses the client site visit and the call from the car "
        "silently — the half of ADR-0008 the user is the only witness to.")


def test_the_step_that_offers_batch_accept_is_a_step_that_knows_about_them():
    """Weaker than it looks, and deliberately kept: what this holds is that **wherever**
    batch-accept is offered, that step speaks of uncorroborated events at all.

    It does not hold the exclusion itself. Deleting the sentence that says batch-accept
    excludes them leaves this green, as long as the step still mentions them somewhere —
    measured, not assumed. The exclusion is prose with no instrument, and the decision log
    records it as such; what this catches is the offer moving to a step where the questions
    are not in view, which is the arrangement ADR-0008 rejected outright.
    """
    offering = [s for s in steps() if "batch-accept" in s]
    assert offering, (
        "no step of the workflow offers batch-accept — this check has nothing to read. If "
        "the offer was reworded, reword it here too.")
    for step in offering:
        assert says(step, "uncorroborated"), (
            f"`{step.splitlines()[0].strip()}` offers batch-accept and says nothing about "
            "uncorroborated calendar events. A yes meant for the drafted blocks would bill "
            "a meeting the machine saw nothing of, and the step does not have them in view "
            "to exclude.")


def test_the_review_question_states_how_many_calendar_questions_are_pending():
    """The counts in the quoted question are what send the user under the table.

    #49 story 36. The block counts are in it because the user cannot see what to look at
    otherwise; a question listed under the table and absent from the count is one they
    have no reason to scroll to.
    """
    # Singular or plural: the count is a variable, so the question is written for whichever
    # number the day has.
    assert re.search(r"\bcalendar questions?\b", review_question(), re.I), (
        "the daily skill's review question counts blocks and 🔸 flags but not the pending "
        "calendar questions. They sit under the table, unbilled until answered, so a "
        "question nothing counts is a meeting the run reads, lists and never gets an "
        "answer to.")


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

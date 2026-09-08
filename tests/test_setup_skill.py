"""Guards on the `setup` skill — the walkthrough for the parts only a person can do.

Every other skill in this plugin fails loudly: a script exits non-zero and says why. This
one fails *silently*, because what it is walking someone through is a machine the agent
cannot see. A step that is described but never checked reads exactly like a step that
worked, and the cost lands days later as a timesheet with nothing in it.

So the assertions here are about the shape of the walkthrough rather than its prose: that
every step carries a check and a recourse, that the allow-list ask names the strings the
screenshot setup script actually registers, and that the skill can find its sibling
whichever way the plugin was installed. Each one is something that goes stale on an edit
somewhere else in the tree — which is the only kind of prose worth a test.
"""

import re

import pytest

import shipped
from shipped import REPO, SKILLS

# The declared surface, read from the module that owns it rather than re-read here: one
# reader of the manifest, so a key added to it is covered by both files at once.
from test_plugin_config import user_config  # noqa: E402

SETUP = SKILLS / "setup"
SETUP_MD = SETUP / "SKILL.md"
SCREENSHOT_SETUP = SKILLS / "daily" / "scripts" / "setup_screenshot_pipeline.ps1"
CALENDAR_WRAPPER = SKILLS / "daily" / "scripts" / "calendar_day.py"

# `one` to `ten` is every count this walkthrough could plausibly reach; a step count outside
# it should fail the test that reads it rather than be quietly skipped.
NUMBER_WORDS = {word: n for n, word in enumerate(
    "zero one two three four five six seven eight nine ten".split())}

# A Chrome extension ID is 32 letters from `a` to `p`: the hex digits of the key's hash,
# each shifted onto that alphabet.
CHROME_EXTENSION_ID = re.compile(r"\b[a-p]{32}\b")


def skill_text() -> str:
    """This skill's own `SKILL.md`."""
    return shipped.skill_md_text(SETUP)


def shipped_text() -> str:
    """SKILL.md plus every reference, joined — the whole of what a run can read.

    Which file a given sentence lives in is an editorial decision that should stay free to
    change; that it is somewhere in the skill is the promise.
    """
    return shipped.shipped_text(SETUP)


def steps() -> list[tuple[str, str]]:
    """Each `### ` step under `## Steps`, as (heading, body)."""
    text = skill_text()
    if "## Steps" not in text:
        return []
    section = text.split("## Steps", 1)[1].split("\n## ", 1)[0]
    found = re.split(r"^### (.+)$", section, flags=re.M)[1:]
    return list(zip(found[0::2], found[1::2]))


def step_ids() -> list[str]:
    return [h.strip() for h, _ in steps()]


def test_the_setup_skill_ships():
    assert SETUP_MD.is_file(), "there is no setup skill"


def test_it_walks_through_more_than_one_step():
    assert len(steps()) >= 2, "a walkthrough with one step is not a walkthrough"


def test_the_prose_counts_the_steps_the_skill_actually_carries():
    """"Five steps, and then a stated finish" is the run's map of what is ahead of it.

    It is also the one line in the skill that goes stale by *adding* a step somewhere else
    in the file — nothing about writing step 6 forces anyone back up to the sentence that
    promised five, and a run told to expect five that meets six has no way to tell whether
    the sixth is a step or a digression it should skip.
    """
    text = skill_text()
    counted = re.search(r"^(\w+) steps\b", text, re.M | re.I)
    assert counted, "SKILL.md never says how many steps the walkthrough has"
    word = counted.group(1).lower()
    assert word in NUMBER_WORDS, f"'{counted.group(0)}' does not count anything"
    assert NUMBER_WORDS[word] == len(steps()), (
        f"the skill promises {word} steps and carries {len(steps())}")


def calendar_step() -> tuple[str, str]:
    """The step that settles the calendar, as (heading, body)."""
    found = [step for step in steps() if re.search(r"calendar", step[0], re.I)]
    assert len(found) == 1, (
        f"expected exactly one step about the calendar, found {len(found)}: {step_ids()}")
    return found[0]


def test_the_calendar_step_runs_the_wrapper_the_daily_skill_will_run():
    """#49, stories 23–26: the sixth step is entered on every run, and what it does about
    the calendar is to *run* it.

    The check has to be the wrapper rather than a look at the toggle, for two reasons that
    both end in a wrong answer. Reading the setting says whether it is set, which is not the
    question — the question is whether a calendar comes back, and on a machine with new
    Outlook alone the toggle is on and the answer is no. And the toggle is a configured
    value: a command composed to read one is what put a Harvest API key in a transcript in
    0.5.0, which is why the guards below forbid the whole family.
    """
    heading, body = calendar_step()
    assert "calendar_day.py" in body, (
        f"step '{heading.strip()}' never runs the calendar wrapper, so whatever it reports "
        "about the calendar is not evidence")
    assert "Bash" in body, (
        f"step '{heading.strip()}' does not say which tool to run it in — the configuration "
        "reaches Bash tool calls alone, so run in PowerShell the wrapper reports the "
        "calendar off on a machine that has it on")
    assert "classic Outlook" in body, (
        f"step '{heading.strip()}' never names the one calendar the shipped adapter can "
        "read, so a user with new Outlook is told nothing about why it stays off")


@pytest.mark.parametrize("phrase", ["the calendar is off", "the calendar stays off"])
def test_the_calendar_step_tells_the_two_refusals_apart_in_the_wrapper_s_own_words(phrase):
    """Both refusals exit 1, so the exit code separates nothing.

    The words are the whole difference: *is off* is the ordinary state of most installs and
    the cue to offer the feature, *stays off* is a toggle that is on and a machine that
    cannot read a calendar — the one case that has to end with the user turning it back off,
    because the `daily` skill stops on it every run until they do. Pinned against the
    wrapper's source, so re-wording either message fails here rather than leaving the skill
    quoting a line no run will ever see.
    """
    assert phrase in CALENDAR_WRAPPER.read_text(encoding="utf-8"), (
        f"the wrapper no longer refuses with {phrase!r} — the setup step quotes it")
    _, body = calendar_step()
    assert phrase in body, (
        f"the calendar step does not carry {phrase!r}, so the run has to guess which "
        "refusal it got")


@pytest.mark.parametrize("step", steps(), ids=step_ids())
def test_every_step_is_verified_rather_than_assumed(step):
    """The whole reason this skill exists rather than a paragraph in the README.

    A desktop app the user says they installed, an extension they say they added, a
    scheduled task that registered without error — none of those are evidence, and each
    has been observed to fail while looking fine.
    """
    heading, body = step
    assert "**Verify**" in body, (
        f"step '{heading.strip()}' tells the user what to do and never checks that it "
        "took effect")


@pytest.mark.parametrize("step", steps(), ids=step_ids())
def test_every_step_says_what_to_do_when_the_check_fails(step):
    """A check with no recourse hands the failure straight back to the user, which is the
    state this skill was written to replace."""
    heading, body = step
    assert "**If it fails**" in body, (
        f"step '{heading.strip()}' checks itself and says nothing about a check that "
        "comes back bad")


# The two strings a user has to hand their security team. Both are defined in the
# screenshot setup script, not here, so renaming either there is what this catches — the
# skill would go on naming a task that no longer exists, in a request nobody can action.
def screenshot_setup_defaults() -> dict[str, str]:
    """Read off the two defaults the setup script binds, not off its prose.

    The capture script is matched at its `$CaptureScript` default rather than as the first
    `.py` token anywhere in the file — the docstring at the top of that script names it
    too, so a looser match would keep passing after the registered default was renamed,
    which is the whole failure this is here to catch.
    """
    src = SCREENSHOT_SETUP.read_text(encoding="utf-8-sig")
    task = re.search(r"\$TaskName\s*=\s*[\"']([^\"']+)[\"']", src)
    assert task, "no default -TaskName in the screenshot setup script"
    capture = re.search(r"\$CaptureScript\s*=\s*Join-Path[^\r\n]*?[\"']([^\"']+\.py)[\"']", src)
    assert capture, "the screenshot setup script binds no default capture script"
    return {"task": task.group(1), "capture": capture.group(1)}


@pytest.mark.parametrize("field", ["task", "capture"])
def test_the_allow_list_ask_names_what_the_setup_script_actually_registers(field):
    """"Allow-list the skill" is not a request a security team can action; a task name and
    a filename are. Pinned against the script so the ask cannot go stale on a rename."""
    value = screenshot_setup_defaults()[field]
    assert value in shipped_text(), (
        f"the allow-list guidance never names {value!r}, which is what the screenshot "
        "setup script registers")


def test_the_browser_extension_id_is_the_same_wherever_it_is_written():
    """`ExtensionInstallAllowlist` takes the ID and nothing else, so a copy that drifts
    sends an administrator allow-listing an extension nobody ships — and the user's
    browser watcher stays blocked with the ticket marked done. The reference owns the ID;
    the skill's step and the README repeat it for the reader who never opens the reference,
    and until this test nothing read the three together."""
    reference = (SETUP / "references" / "endpoint-security.md").read_text(encoding="utf-8")
    ids = set(CHROME_EXTENSION_ID.findall(reference))
    assert len(ids) == 1, f"the endpoint-security reference names {len(ids)} extension IDs"
    (extension_id,) = ids
    for doc in (SETUP_MD, REPO / "README.md"):
        assert extension_id in doc.read_text(encoding="utf-8"), (
            f"{doc.relative_to(REPO)} does not carry the extension ID the reference names, "
            f"{extension_id}")


def test_a_block_has_to_be_evidenced_before_it_is_escalated():
    """The first coworker install sent its user to IT for an EDR allow-list when the real
    fault was a split Python install that needed no ticket at all.

    Asserted as a section rather than a phrase: the guidance has to be somewhere a run
    lands on its own, and a heading survives the rewording that a grep for prose does not.
    Ordering matters as much as presence — evidence comes before the ask, so the section
    that establishes the block has to precede the section that makes the request.
    """
    reference = SETUP / "references" / "endpoint-security.md"
    assert reference.is_file(), "the allow-list guidance has nowhere to live"
    headings = re.findall(r"^## (.+)$", reference.read_text(encoding="utf-8"), re.M)
    evidence = next((i for i, h in enumerate(headings)
                     if re.search(r"\b(prove|proof|evidence)", h, re.I)), None)
    ask = next((i for i, h in enumerate(headings)
                if re.search(r"what to ask", h, re.I)), None)
    assert evidence is not None, f"no section on establishing the block: {headings}"
    assert ask is not None, f"no section on what to ask for: {headings}"
    assert evidence < ask, (
        "the allow-list request comes before the section that says to prove the block, "
        "which is the order that produced a wrongly-raised ticket")


# Resolving the `daily` sibling on either install shape is guarded in `test_install_shapes.py`.


def test_it_states_when_setup_is_finished():
    """The line between "installed" and "ready to use". Without it the user is left
    guessing whether the silence means done or stuck."""
    text = skill_text()
    assert re.search(r"^## .*\b(done|finished|complete)\b", text, re.M | re.I), (
        "SKILL.md has no section that says setup is over")


def test_the_finish_says_the_calendar_is_among_what_is_now_true():
    """The finish is the only place a user is told what they ended up with.

    A step that ran, passed and is not in that list is a feature they were walked through
    and will not remember having: the calendar is the one of the six whose result is
    invisible until a day is drafted, and "a meeting you sat through is billed rather than
    lost" is the sentence that makes the rest of the plugin's behaviour make sense.
    """
    done = shipped.section(skill_text(), "Done")
    assert done, "SKILL.md has no `## Done` section to state what is now true"
    assert "calendar" in done.lower(), (
        "the finish never mentions the calendar, so a user who just turned it on is not "
        f"told it is on:\n{done}")
    # And the finish's own count of the steps it is declaring finished, which is the second
    # line that goes stale on adding one — a run that stops at "steps 1 to 5" has declared
    # setup over with a step unentered.
    counted = re.search(r"steps 1 to (\d+)", done)
    assert counted, f"the finish never says which steps it is declaring passed:\n{done}"
    assert int(counted.group(1)) == len(steps()), (
        f"the finish declares setup over after {counted.group(1)} steps; there are "
        f"{len(steps())}")


def test_the_description_names_every_part_of_the_install_the_skill_covers():
    """The frontmatter description is what a user reads before invoking this, and the only
    summary of it anywhere in the harness. A step missing from it is a step nobody knows
    they would get — which for the calendar is the difference between an opt-in feature
    discovered at setup and one discovered by reading the manifest."""
    description = shipped.frontmatter(skill_text()).get("description", "")
    assert "calendar" in description.lower(), (
        f"the description does not mention the calendar step:\n{description}")


# The direct-expansion family, in both shells the skill reaches for: `$KEY`, `${KEY}`,
# `$env:KEY`, `${env:KEY}`, `$Env:KEY`. `${KEY:+word}` and `${KEY+word}` are the two forms
# that cannot leak — they substitute the word, so the value never leaves the variable — and
# they are the only exemptions. Anything else this matches is the credential itself.
#
# Named separately from the probe's key list below because the two lists have different
# jobs: printing a timezone is harmless, printing either of these costs the user a
# rotation. Adding a key here is a claim that it is a secret.
CREDENTIAL_KEYS = ("HARVEST_ACCOUNT_ID", "HARVEST_API_KEY")
PROBE_KEYS = CREDENTIAL_KEYS + ("TIMESHEET_TIMEZONE",)


def value_expansion(keys) -> re.Pattern[str]:
    """The direct-expansion family for `keys`, in both shells the skill reaches for.

    One builder rather than a pattern per caller: the exemptions are the subtle part, and a
    second copy written for a second key list is a second chance to leave one out. Which is
    what happened — a hand-written list for the declared surface dropped `${env:KEY}` and
    was case-sensitive about `env:`, so the guard that covered the most keys caught the
    fewest forms.
    """
    return re.compile(r"\$\{?(?i:env:)?!?(" + "|".join(keys) + r")\b(?!:?\+)")


VALUE_EXPANSION = value_expansion(CREDENTIAL_KEYS)

# The name-as-argument forms, which carry no `$` at all and so are invisible to the
# pattern above. Both print the value; neither is anything this skill needs.
NAME_ARGUMENT = re.compile(
    r"\b(?:printenv|Get-Item|Get-ChildItem|Get-Content)\s+(?:env:)?(?i:"
    + "|".join(CREDENTIAL_KEYS) + r")\b")


def every_shipped_skill_text() -> list[tuple[str, str]]:
    """`(label, text)` for every `.md` a run of *any* skill can read.

    Wider than `shipped_text()` on purpose, and only for the credential guard below. The
    leak it exists for was in the `setup` skill because that is the skill that asks about
    configuration — but #28 put "read the configured value in the Bash tool" into `daily`
    and `reconcile` as well, and an improvised read is an improvised read wherever it is
    written. Scoping the guard to where the last leak happened is how the next one gets a
    different postcode.
    """
    return [(str(p.relative_to(REPO)), p.read_text(encoding="utf-8"))
            for p in sorted(SKILLS.rglob("*.md"))]


@pytest.mark.parametrize("skill", ["daily", "reconcile", "setup"])
def test_a_skill_handing_a_configured_path_to_powershell_resolves_it_in_bash(skill):
    """#28: the configuration is published to Bash tool calls alone.

    All three skills read `TIMESHEET_SCREENSHOTS_DIR` and then use it in a PowerShell
    command — a directory listing in two of them, the scheduled task's `-ScreenshotsDir`
    in the third. Read *in* PowerShell it comes back empty on every machine, so the
    listing shows the default folder and the task registers against it: the reader and
    the writer end up pointed at different directories, and nothing fails. A month sweep
    then reports that a month nobody worked.

    `--where` rather than an `echo` of the variable, because the value has four possible
    layers and the environment is only one of them — the exported install keeps it in
    `.env`, where an `echo` finds nothing. The flag runs the same resolution the capture
    script writes by, which is the whole point.
    """
    root = SKILLS / skill
    # What a *run* reads: SKILL.md and the references beside it. `docs/skills/daily/decision-log.md` and
    # `docs/CONTRIBUTING.md` are the maintainer's, and both have to stay free to quote the
    # wrong idiom while explaining why it is wrong — the same allowance the credential
    # guard below makes for naming a key while describing the danger.
    read_on_a_run = [root / "SKILL.md"] + sorted((root / "references").glob("*.md"))
    text = "\n".join(p.read_text(encoding="utf-8") for p in read_on_a_run if p.is_file())
    if "TIMESHEET_SCREENSHOTS_DIR" not in text:
        pytest.skip(f"the {skill} skill does not read the capture directory")
    assert "--where" in text, (
        f"the {skill} skill uses TIMESHEET_SCREENSHOTS_DIR but never says how to resolve "
        "it; anything reading it in PowerShell gets an empty answer and the default folder")
    assert "Bash" in text, (
        f"the {skill} skill does not say which tool to resolve it in, which is the half "
        "that matters")
    # And the wrong way is forbidden outright, because merely offering the right one does
    # not displace it: an `echo` reads the process environment, which is one layer of the
    # four and not the one an exported install keeps this value in.
    wrong = [form for form in ("$TIMESHEET_SCREENSHOTS_DIR",
                               "${TIMESHEET_SCREENSHOTS_DIR",
                               "$env:TIMESHEET_SCREENSHOTS_DIR") if form in text]
    assert not wrong, (
        f"the {skill} skill expands TIMESHEET_SCREENSHOTS_DIR directly ({', '.join(wrong)})"
        " — that reads only the process environment, so a user whose capture directory is"
        " configured in a .env gets an empty answer and the default folder")


@pytest.mark.parametrize("key", CREDENTIAL_KEYS)
def test_no_shipped_skill_text_anywhere_expands_a_credential_to_its_value(key):
    """The same rule as below, across all three skills rather than one.

    `daily/SKILL.md` now tells a run to resolve a configured value in the Bash tool and
    paste the answer into a PowerShell command. That is one sentence away from the
    improvisation that leaked a key in 0.5.0, and the value it names there is a *path* —
    so the instruction is safe and the habit it teaches is the dangerous one. This holds
    the line for the keys where it matters, everywhere a run can read.
    """
    offenders = []
    for label, text in every_shipped_skill_text():
        found = [m.group(0) for m in VALUE_EXPANSION.finditer(text) if m.group(1) == key]
        found += [m.group(0) for m in NAME_ARGUMENT.finditer(text)
                  if key.lower() in m.group(0).lower()]
        offenders += [f"{label}: {f}" for f in found]
    assert not offenders, (
        f"a shipped skill expands {key} to its value ({'; '.join(sorted(set(offenders)))})"
        " — whatever runs it writes that value into the session transcript, which is how"
        " a Harvest API key was leaked in 0.5.0")


@pytest.mark.parametrize("key", CREDENTIAL_KEYS)
def test_no_command_in_the_skill_expands_a_credential_to_its_value(key):
    """Reported against 0.5.0: `/billables:setup` printed the user's Harvest API key into
    the session transcript, from its own "is the configuration set?" pre-check.

    The skill told the run *what* to check and not *how*, so the command was improvised,
    and the improvisation paired `:+` with `:-` on the reading that each supplies a word
    for its own case. Only `:+` does. `:-` substitutes when the variable is empty, so a
    configured key printed the word and then the key. Exit 0, no error, nothing to notice.

    So the assertion is not "don't use that idiom" — the next improvisation will be a
    different one. It is that no direct expansion of a credential survives in the shipped
    text, which is the family the leak came from and the family a copied line falls into.
    The trap is worth stating in prose too, which is why this matches the expansion rather
    than the key name: naming the key while explaining the danger has to stay allowed.

    What it does not reach, so that nobody trusts it further than it goes: a key named
    through a variable, as the prescribed probe itself does with `${!k:-}`. An edit that
    unrolled that loop and echoed the indirection would leak and match nothing here. The
    guard covers the reachable half; prescribing the probe covers the rest, which is why
    the test below holds the block in place.
    """
    text = shipped_text()
    offenders = [m.group(0) for m in VALUE_EXPANSION.finditer(text) if m.group(1) == key]
    offenders += [m.group(0) for m in NAME_ARGUMENT.finditer(text)
                  if key.lower() in m.group(0).lower()]
    assert not offenders, (
        f"the setup skill expands {key} to its value ({', '.join(sorted(set(offenders)))})"
        " — whatever runs it writes that value into the session transcript, which is how"
        " a Harvest API key was leaked in 0.5.0")


@pytest.mark.parametrize("key", sorted(user_config()))
def test_no_step_expands_a_configured_value_to_find_out_whether_it_is_set(key):
    """The same rule as the two above, over the whole declared surface rather than the keys
    that have already cost somebody something.

    A credential is what makes the leak expensive; composing a read of a configured value is
    what makes it happen, and every key in the manifest is a candidate. The sixth step is
    exactly where the next one would have gone in: the obvious way to write "find out
    whether the calendar is on" is to echo the toggle, and a run that improvises one read
    improvises the next. The answer would be wrong as well as costly — the value reaches
    Bash tool calls alone, so a PowerShell read reports every key unset on a machine that
    is configured perfectly well (#28).
    """
    found = sorted({m.group(0) for m in value_expansion([key]).finditer(shipped_text())})
    assert not found, (
        f"the setup skill expands {key} directly ({', '.join(found)}) — whatever runs it "
        "writes that value into the session transcript, and on the shell the configuration "
        "never reached the answer is wrong as well")


def test_the_configuration_probe_is_prescribed_rather_than_left_to_the_run():
    """The fix above only holds while there is a command to use instead of composing one.
    Drop the block and the skill is back to naming three keys and hoping.

    Pinned against `PROBE_KEYS` rather than the credentials alone, because "Done" declares
    setup finished on *three* configured values. A probe that quietly stopped covering the
    timezone would leave the third one asserted in prose and checked by nothing.
    """
    text = skill_text()
    # Indented, because the probe sits inside a numbered list item.
    blocks = re.findall(r"^[ \t]*```[a-z]*\n(.*?)^[ \t]*```", text, re.M | re.S)
    probes = [b for b in blocks if all(k in b for k in PROBE_KEYS)]
    assert probes, (
        "no code block in SKILL.md checks all of "
        f"{', '.join(PROBE_KEYS)}, so the presence check is improvised again on every run")
    assert any("MISSING" in b and "set" in b for b in probes), (
        "the prescribed probe never reports the two states it exists to tell apart")


def test_it_points_at_the_configuration_dialog_rather_than_asking_for_values():
    """Declared configuration already holds the credentials, the timezone and the paths.
    A walkthrough that asks for them again is a second place for them to be wrong, and
    puts a token into a session transcript that gets written to disk."""
    assert "/plugin configure billables" in shipped_text(), (
        "the skill never routes a missing configured value to the dialog that owns it")

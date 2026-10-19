"""A guard that keeps one provider's vocabulary out of the shipped rules.

The rules used to map a block's activity straight onto the literal task names of one
Harvest account — `Gen - Development/Configuration`, `Gen - Meeting`, and the rest. Any
other user's account names its tasks differently, so those strings were never generic:
they were one workspace's facts shipped as everybody's defaults. The rules now decide a
**work kind** instead, and the user's own `.context.md` maps work kind → the task their
provider actually offers.

Unlike the redacted names in `test_redaction.py`, these strings are not sensitive, so
they are spelled out here. The scan covers the shipped instruction surface of **every**
skill — `SKILL.md`, `references/*.md`, `scripts/*.py` under each of them — because a new
skill is exactly where the drift gets back in: it is written against whichever account
its author happened to be looking at, and the rules that were cleaned up don't govern it.
Test fixtures are deliberately out of scope: the provider adapter's tests have to feed it
the provider's real shapes, and a fake API response is not a rule.

The second test is the positive half. A denylist only says what the rules stopped
saying; it cannot tell whether what they say now is the shared vocabulary. So the work
kinds the rules name are checked against the glossary in `CONTEXT.md`, which is what
makes the glossary load-bearing rather than decorative.
"""

from shipped import CONTEXT_MD, REPO, SKILLS, skill_dirs, table_cells

SKILL = SKILLS / "daily"

# The literal task names of the one account the rules used to be written against.
PROVIDER_TASK_NAMES = (
    "Gen - Development/Configuration",
    "Gen - Development",
    "Gen - Meeting",
    "Gen - Documentation",
    "Gen - Project Management",
    "Gen - Testing",
    "Gen - Investigation",
    "Gen - Issue Resolution",
    "Gen - General Consulting",
    "Meeting - Standup Meetings",
    "No Display",
)

FIX = """
Those are one Harvest account's task names. The shipped rules decide a work kind from
`CONTEXT.md`'s glossary; the provider's own string for it comes from the user's
`.context.md` (see its "Work kinds" table) or from declared plugin configuration.
Name the work kind, not the task.
"""


def shipped_rules():
    """The instruction surface a user reads and follows — not the tests behind it.

    Every shipped skill, discovered rather than listed: a skill added to the plugin and
    left out of this walk would be the one place the old vocabulary could come back.

    Narrower than `shipped.shipped_text()`, deliberately. That one joins every markdown
    file under a skill; this one names `SKILL.md`, `references/` and `scripts/` — and
    yields paths rather than text, because an offender has to be reported with a file and
    a line number or nobody can find it.
    """
    for skill in skill_dirs():
        yield skill / "SKILL.md"
        yield from sorted((skill / "references").glob("*.md"))
        yield from sorted((skill / "scripts").glob("*.py"))


def test_no_provider_task_name_appears_in_the_shipped_rules():
    offenders = []
    for path in shipped_rules():
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            for name in PROVIDER_TASK_NAMES:
                if name in line:
                    rel = path.relative_to(REPO).as_posix()
                    offenders.append(f"  {rel}:{lineno}: {name}")
                    break
    assert not offenders, "provider task names in the shipped rules:\n" + "\n".join(
        offenders) + "\n" + FIX


# --- the work kinds the rules name are the ones the glossary defines --------------------

def glossary_work_kinds() -> list[str]:
    return table_cells(CONTEXT_MD.read_text(encoding="utf-8"),
                       "| Work kind | The block was |", 0)


def test_the_rules_only_name_work_kinds_the_glossary_defines():
    rules = table_cells(
        (SKILL / "references" / "classification-rules.md").read_text(encoding="utf-8"),
        "| Dominant block activity | Work kind |", 1)
    unknown = sorted(set(rules) - set(glossary_work_kinds()))
    assert not unknown, (
        f"the classification rules name work kinds the glossary does not define: {unknown}.\n"
        f"Either use the glossary's term or add the new one to CONTEXT.md — the point of "
        f"the table is that both documents mean the same seven things.")


def test_the_workspace_template_spells_the_work_kinds_exactly_as_the_rules_do():
    """The third copy, and the one that decides a real run.

    A run reads its work kind out of the rubric and looks that string up in the user's
    `.context.md` § "Work kinds". If the template's left column drifts by so much as a
    capital — `Project Management` for `Project management` — every lookup misses, every
    block silently falls through to the default task, and nothing else in this repo
    notices. The two documents the previous test compares would still agree.
    """
    template = table_cells(
        (SKILL / "references" / "context.md.example").read_text(encoding="utf-8"),
        "| Work kind | Your task |", 0)
    assert template == glossary_work_kinds(), (
        "the .context.md template's work kinds have drifted from CONTEXT.md.\n"
        f"  template: {template}\n"
        f"  glossary: {glossary_work_kinds()}\n"
        "A run looks the rubric's string up in this table verbatim, so these have to match "
        "exactly — same spelling, same order, same seven.")


def test_every_work_kind_the_glossary_defines_is_reachable_from_the_rules():
    """The other direction: a glossary term no rule ever produces is vocabulary nobody
    speaks, and the next writer will invent a synonym for it instead."""
    rules = (SKILL / "references" / "classification-rules.md").read_text(encoding="utf-8")
    unused = sorted(kind for kind in glossary_work_kinds() if f"`{kind}`" not in rules)
    assert not unused, f"work kinds defined but never assigned by any rule: {unused}"


# --- the provider boundary (#35) -------------------------------------------------------

PROVIDER = SKILL / "scripts" / "provider"

# Harvest's own wire format: its endpoints and the field names of its requests and replies.
HARVEST_WIRE = ("spent_date", "started_time", "ended_time", "time_entries",
                "project_assignments", "task_assignments", "hourly_rate",
                "HARVEST_ACCOUNT_ID", "HARVEST_API_KEY", "api.harvestapp.com")


def test_the_neutral_side_of_the_provider_boundary_speaks_no_harvest_wire_format():
    """The dispatcher, the error classes and the config helper serve every adapter. A Harvest
    field reaching them would be one provider's shape leaking into the contract, which is the
    drift #35 moved the scripts to stop. Only `provider/harvest/` may speak Harvest."""
    offenders = []
    for path in sorted(PROVIDER.glob("*.py")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            hit = next((w for w in HARVEST_WIRE if w in line), None)
            if hit:
                offenders.append(f"  {path.relative_to(REPO).as_posix()}:{lineno}: {hit}")
    assert not offenders, ("Harvest wire format above the adapter:\n" + "\n".join(offenders)
                           + "\nMove it into provider/harvest/; the neutral modules pass the "
                           "contract's own names (docs/provider-contract.md).")


# --- the work-item source: the same line, drawn for the read seam (#37) ------------------
#
# Dataverse is shipped, as one adapter of the work-item source. What may not ship is one
# *account's* Dataverse: its environment, its table and column names, its case-creation
# convention. Those are the user's facts and live in their `.context.md`.

import re  # noqa: E402

WORK_ITEM_SOURCE = SKILLS / "daily" / "scripts" / "work_items"
ADAPTERS = WORK_ITEM_SOURCE / "adapters"

# The settings the work-item source used to be configured by. They are retired: only the
# adapter may name them (to recognise the old shape), and nothing else ships them.
RETIRED_SETTINGS = ("DATAVERSE_URL", "PAC_AUTH_PROFILE")

# What names the system rather than the adapter's own code: the CLI it shells out to,
# its host, its query language and the account-shaped words of its schema.
DATAVERSE_IDENTIFIERS = (
    re.compile(r"\bpac\b"),
    re.compile(r"\.crm\d*\.dynamics\.com", re.I),
    re.compile(r"\bdataverse\b", re.I),
    re.compile(r"\bfetchxml\b", re.I),
    re.compile(r"\bincidents?\b", re.I),
    re.compile(r"\bticketnumber\b|\bstatecode\b|\bmodifiedon\b|\bcasetypecode\b"),
)

# Prose that explains the boundary to a user is allowed to name the adapter that ships.
# These are the files where that is the subject, rather than a rule a run follows.
ALLOWED_TO_NAME_THE_SYSTEM = {
    "CONTEXT.md", "README.md", "CHANGELOG.md",
    "docs/provider-contract.md", "docs/CONTRIBUTING.md",
    "skills/daily/references/catalog-refresh.md",   # documents the adapter's own section
    "skills/daily/references/context.md.example",   # the template that adapter reads
    "skills/daily/references/first-run.md",         # the one pac recovery step
}


def shipped_files():
    """Everything a user receives that a run reads: skills' markdown and scripts, the
    template, the env example. Tests, docs/ and the changelog are the project's own."""
    for skill in skill_dirs():
        yield skill / "SKILL.md"
        yield from sorted((skill / "references").glob("*"))
        yield from sorted((skill / "scripts").rglob("*.py"))
        env = skill / ".env.example"
        if env.is_file():
            yield env


def test_no_dataverse_identifier_ships_outside_the_adapter():
    offenders = []
    for path in shipped_files():
        rel = path.relative_to(REPO).as_posix()
        if path.is_relative_to(ADAPTERS) and path.name != "__init__.py":
            continue
        if rel in ALLOWED_TO_NAME_THE_SYSTEM:
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for pattern in DATAVERSE_IDENTIFIERS:
                if pattern.search(line):
                    offenders.append(f"  {rel}:{lineno}: {line.strip()[:90]}")
                    break
    assert not offenders, (
        "Dataverse identifiers outside the work-item adapter:\n" + "\n".join(offenders)
        + "\nThe seam and the rules name the work-item source, not the system behind it; "
          "the system's names belong in `scripts/work_items/adapters/`.")


def test_the_adapter_ships_no_accounts_environment_entity_or_column():
    """The positive half: the adapter must take every account fact from the user's
    `.context.md`, so no literal URL and no schema name may be written into it."""
    for path in sorted(ADAPTERS.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"https?://", text), f"{path.name} writes a URL"
        for name in ("incident", "ticketnumber", "statecode", "modifiedon", "customerid"):
            assert name not in text.lower(), f"{path.name} writes the column/entity {name!r}"


def test_the_retired_settings_are_named_only_by_the_adapter_that_recognises_them():
    offenders = []
    for path in shipped_files():
        rel = path.relative_to(REPO).as_posix()
        if path == ADAPTERS / "dataverse.py" or rel in ALLOWED_TO_NAME_THE_SYSTEM:
            continue
        text = path.read_text(encoding="utf-8")
        offenders += [f"  {rel}: {key}" for key in RETIRED_SETTINGS if key in text]
    assert not offenders, "retired work-item settings shipped as live:\n" + "\n".join(offenders)


def test_the_neutrality_scan_has_something_to_scan():
    """A walk that finds nothing passes everything."""
    assert any(p.name == "source.py" for p in shipped_files())
    assert any(p.name == "dataverse.py" for p in ADAPTERS.glob("*.py"))
    assert (WORK_ITEM_SOURCE / "adapters" / "__init__.py").is_file()

# Contributing

How to change this repo without losing what it knows. Not needed to run a timesheet, and
not the route for a defect found by someone who installed the plugin — that is
`skills/daily/references/reporting-issues.md`. This file covers the plugin as a whole; where a
line below says `SKILL.md`, `references/` or `scripts/` without a prefix, it means the `daily`
skill's, under `skills/daily/`, which is where nearly every rule lives. Test paths and
root-level files are written in full.

The general method lives in the `changing-agent-instructions` skill: reproduce, watch a
fresh agent do it unprompted, baseline against an instrument that fails when the
knowledge is lost, one change at a time, re-check the baseline afterwards. What follows
is what is specific to this repo. `AGENTS.md` routes a finding, a decision and a feature
idea to the file that holds each; this is the file it routes a *change* to, and releasing
one is §Releasing below. Why the maintainer documents sit under `docs/` rather than beside
the skill, and what was rejected on the way, is the decision log's entry "Maintainer documents
moved out of the shipped skill".

## The instrument

`skills/daily/tests/` measures the *scripts*. It stays green while the instructions break, so it is
not the instrument for a wording change — `docs/skills/daily/decision-log.md` § "What the
instruments measure" has the full argument and the fixture design that has been used so far.

Four gates a doc edit can trip; the command that runs them, and where from, is in
`AGENTS.md`:

- `skills/daily/tests/test_references.py` scans `SKILL.md` and every `references/*.md`
  (globbed, so a new reference file is covered automatically) and fails any
  `python scripts/<name>.py` command naming a script the skill does not ship. Write
  workspace-relative commands some other way.
- `tests/test_provider_neutrality.py` fails if a provider's literal task name returns to
  the shipped rules, if the rules name a work kind the glossary doesn't define, or if the
  work kinds in `references/context.md.example` drift from the ones in `CONTEXT.md` — that
  last pair is matched string-for-string at run time.
- `tests/test_daily_skill.py` reads the `## Workflow` section alone and fails if no step
  invokes `scripts/calendar_day.py`, if the section does not name the toggle that gates it
  (read off the wrapper's own `TOGGLE`), or if the calendar rules stop using the glossary's
  terms and the wrapper's verdict words. Scoped to the workflow on purpose: everything it
  asks for is also in "Files in this skill", which is where a script lands before any step
  runs it, so a whole-file scan would have passed through the whole period the calendar
  shipped unread. Three more assertions cover the *other* half of the verdict, the events
  nothing bills unless the user says so (#54): the presentation step — found by its title,
  not its number — has to speak of uncorroborated events; any step that offers batch-accept
  has to speak of them too, which holds the offer beside the questions and *not* the
  sentence excluding them; and the quoted review question has to count them. The quote is
  asserted on separately because it is what the step puts to the user in words. What none of
  the three reaches is anything that happens after a yes.
- A `.context.md` under the Step 11 size budget after any change that proposes writing
  to one.

A code edit has a second gate, `pyright`, run from the same place. The repo root's
`pyrightconfig.json` is what makes it — and an editor's language server — read *this*
repo. Pyright walks up from the working directory looking for that file, so a checkout
nested inside another project inherits that project's root and type-checks the neighbouring
tree instead; the config existed for a while as nothing but a boundary. It also pins
`pythonVersion` to the 3.10 floor `README.md` states as a prerequisite, so a stdlib or
syntax feature added later fails here rather than on a user's machine, and it declares the
`sys.path` entries `skills/daily/tests/conftest.py` adds at run time, which pyright does not
execute. The tree is at zero errors; keep it there rather than relaxing a rule to get back
to it.

## Rules with more than one copy

Duplication here is mostly deliberate — a guard restated in the pre-post checklist
catches what a guard buried in Step 6 does not. The hazard is scope drift: each copy
reads fine alone and the contradiction exists only across them.

Two tables, because the rows need two different things from a maintainer. The first holds
facts the code owns — a flag name, an output shape, a threshold, a declared key, a version
floor — and each names the instrument that fails when the copies disagree. The second holds
judgement, restated on purpose, and one fact no test here can reach.

### Held by an instrument

A row is here because the fact is the code's, and the instrument holds the code's copy.
Some instruments also read the prose copies and fail when one drifts; the others hold the
code alone, and every prose restatement is still yours to find — the "Restated at" column
is where to look. Either way: change the owner, run the suite, fix what fails, then walk
the column.

| Rule | Owner (carries the reasoning) | Instrument | Restated at |
|---|---|---|---|
| The rules name a work kind; the user's workspace names the provider's task. No task name is a shipped default | the repo root's `CONTEXT.md` glossary, and `docs/adr/0002-defer-splitting-the-provider-into-its-own-plugin.md` for why | the repo-level `tests/test_provider_neutrality.py` — a denylist of the one account's task names, scanned over every shipped skill's `SKILL.md`, references and scripts; and the glossary's work-kind table, held against `classification-rules.md` and `context.md.example` | `references/classification-rules.md` §"Work kind and task selection", `references/context.md.example` §"Work kinds", `SKILL.md` "Tunable defaults" + Step 4 |
| Setting precedence: flag, then `.env`, then the process environment, then the script default; blank counts as unset | `scripts/skill_config.py` docstring | `skills/daily/tests/test_config_seam.py` — one test per rung of the ladder, and two for a blank value not winning | `SKILL.md` "What lives where", `references/first-run.md` §"First-run: configuration", the `refresh_catalogs.py` and `screenshot_capture.py` module docstrings |
| The declared configuration surface: which keys exist, which are required, which are sensitive | `.claude-plugin/plugin.json` `userConfig` | the repo-level `tests/test_plugin_config.py`, which holds the manifest against the settings the scripts resolve, against `README.md`'s install block, and against the export's `.env.example` — which has to name exactly the manifest's keys, blank, plus the work-item source's two (#37) | `references/first-run.md` §"First-run: configuration" table, `README.md`'s install table |
| The Python the scripts must run on: 3.10 | `README.md` §Prerequisites | `pyrightconfig.json` `pythonVersion`, which enforces it on the code; the repo-level `tests/test_distribution.py` holds the README's stated floor equal to it | the `compatibility:` line of each shipped skill's `SKILL.md`, the no-Python error in `install/install_skill.{sh,ps1}`, this file's "The instrument" section |
| The import direction inside `scripts/`: a provider script never imports the activity-source client, nothing imports a script, and the shared zone module imports neither half | `docs/adr/0006-keep-the-provider-in-plugin-but-behind-a-command-contract.md` §Consequences, for why an adapter that reaches into the activity source is not behind a boundary | `skills/daily/tests/test_module_boundaries.py` — every edge read out of the scripts' own syntax trees, and the population taken from `scripts/`, so a new script is held the day it lands | the module docstrings of `scripts/timezone.py`, `scripts/aw_client.py` and `scripts/harvest_write.py` ("not a script … everything a write has in common happens here, once"), `docs/skills/daily/decision-log.md` §"Two provider scripts were importing the activity-source client" |
| No assumed timezone: an unconfigured run refuses rather than guessing an offset | `scripts/timezone.py` `resolve_zone()` docstring | `skills/daily/tests/test_declared_configuration.py` — the unconfigured user gets a refusal naming both ways to supply a zone, never an offset | `SKILL.md` "Timezone", `references/activitywatch.md` §"Time zones", `references/first-run.md`'s first-run table (which names which scripts refuse without it), and the module docstring of every script that resolves a zone — `afk_blocks`, `activity_timeline`, `harvest_post` and, since #32, `harvest_patch` |
| A day is bounded by its zone at each end, not by one offset — so the day the clocks change is 23 or 25 hours long | `scripts/timezone.py` `utc_bounds()` docstring | `skills/daily/tests/scenarios.py` `daylight-saving-transition-day`, held byte-for-byte by `test_scenarios.py`; `test_timezone.py` at the function | `references/activitywatch.md` §"Time zones", `SKILL.md` "Timezone" |
| The second pass over the hour a fall-back repeats is suffixed `*`, and reads back as the same instant | `scripts/timezone.py` — `local_clock()` writes the marker, `parse_local_time()` / `to_utc()` read it back and refuse it wherever the clock does not read twice | `skills/daily/tests/support.py` imports `SECOND_PASS_MARK` rather than spelling it, so every fixture is written in the notation its golden returns; `skills/daily/tests/scenarios.py` `fall-back-repeated-hour-day` | `references/activitywatch.md` §"Time zones", `references/output-format.md` §Conventions, `SKILL.md` "Timezone", `skills/daily/tests/README.md` §"Dating a day", `docs/skills/daily/decision-log.md` §"Two instants an hour apart printed the same clock time", `CHANGELOG.md` |
| The transition instant carries two clock readings — `03:00` as you reach it and `02:00` once it has passed — so an entry split there reads as an overlap and is not one. Closing the apparent overlap is what loses the repeated hour | `scripts/harvest_write.py` `refusal_for_a_straddled_change()`, which is the copy a run is shown at the moment it matters — and the only copy: the create and the patch both call it rather than either restating it, so the message a patch is refused with is byte-for-byte the create's. It sits with the write path and not with the zone arithmetic it reads (`timezone.repeated_span()`) because what Harvest does with two clock times is the provider's behaviour, not the zone's | `test_timezone.py` (`transition_clocks()`) and `test_edge_harvest_api.py` (the refusal, the hour it saves, and — for the patch — an assertion that the two messages are equal rather than merely alike) | `scripts/timezone.py` `transition_clocks()` docstring (which states the same pair in the same words and is where the readings are computed), `references/output-format.md` §Conventions (which carries the cases the refusal cannot see, where a block starts or ends inside the span rather than containing it), `SKILL.md` Step 9, `docs/skills/daily/decision-log.md` §"A create straddling the fall-back was billed an hour short", `CHANGELOG.md`. This one has been wrong in prose once already — the first `output-format.md` version split at the break rather than at the transition and lost the exact hour it was written to save — so check the arithmetic sums to the elapsed time before changing any copy |
| The two transition hours are told apart by the *sign* of the offset shift across `fold`, never by the fact that there is one — a repeated hour shifts back, a skipped one forward | `scripts/timezone.py` `clock_reads()` docstring | `test_timezone.py` — the marker is refused inside the skipped hour and accepted inside the repeated one | `to_utc()` and `parse_range()`, which both route through it, `references/activitywatch.md` §"Time zones" last two bullets, `docs/skills/daily/decision-log.md` §"One `fold` guard could not tell the two transition hours apart" |
| The shared-directory export is prefixed `<plugin>-<skill>`, its declared `name:` rewritten to match, and it is generated rather than hand-edited | `docs/adr/0004-generate-the-shared-agent-skills-export.md` | the repo-level `tests/test_distribution.py` — one prefixed directory per shipped skill, each declaring its directory's name, and regenerating changes nothing | `install/export_agent_skills.py` module docstring, `README.md` step 5 |
| The export deletes only what carries its stamp — the prefix says where to look, never who wrote it | `docs/skills/daily/decision-log.md` §"Sharing a prefix is not proof of authorship" | the retirement tests in the repo-level `tests/test_install_scripts.py` — a user's own skill sharing the prefix is spared, what the export did not write is left alone, and a directory that is not its own is refused | `install/export_agent_skills.py` `retire_departed_skills()` / `refuse_unless_ours()` docstrings, `docs/adr/0004-…` §Consequences |
| Every flag a script parses is also named in `SKILL.md`'s "Files in this skill" entry for it — presence only; what the flag *does* is written once, wherever it is best explained | the script's own parser | `skills/daily/tests/test_references.py`, held to equality against the parser; the `reconcile` skill's copy is held to inclusion by the repo-level `tests/test_reconcile_skill.py`, which reads the same parser through `skills/daily/tests/flag_scan.py` (#31) | `SKILL.md` "Files in this skill". The `reconcile` skill's `SKILL.md` is a *third* copy (it invokes `harvest_list.py --by-day` and names `--window` and `--full`); it cites the flags it uses and is not an inventory, so a flag it does not name is not a finding there |
| A toggle is on when it reads `true`, in any case; blank or anything else is off, and it resolves through the same ladder as every other key | `scripts/skill_config.py` `enabled()` docstring | `skills/daily/tests/test_config_seam.py` § "A toggle: the one boolean the seam resolves" | `scripts/calendar_day.py` module docstring item 1 and its off message, `.env.example`'s `TIMESHEET_OUTLOOK_CALENDAR` comment, `references/first-run.md` §"First-run: configuration" table, `SKILL.md` "Files in this skill" and Step 2's load bullet (which names the key and quotes the off message, and is what decides whether a run stops on it), `CHANGELOG.md` |
| The calendar adapter contract: invoked as `<adapter> YYYY-MM-DD`, prints one UTF-8 JSON document of `{"events": [...]}` with the nine fields, exits non-zero with a reason when the calendar cannot be read | `scripts/calendar_day.py` module docstring §"The adapter contract" | `skills/daily/tests/test_calendar_day.py` — the `event()` builder writes the nine fields, the field-missing and not-a-calendar-day tests refuse anything less, and the fake adapter asserts the argv it is handed | `docs/adr/0008-…` §Decision "a narrow adapter", `CHANGELOG.md`; `scripts/outlook_calendar.ps1` is the copy that *produces* it — its header comment restates the shape, and the repo-level `tests/test_outlook_adapter.py` drives its functions under 5.1 with fake `AppointmentItem`s and reads the document back |
| A meeting window is a foreground window titled `Meeting \| …` or `Call with …`; a `Chat \| …` window is not one. It is the soft boundary a Teams meeting starts at, and the evidence that corroborates a calendar event | `scripts/calendar_day.py` `MEETING_TITLE`, the one copy in code, with the verdict it drives in `meeting_spans()` / `verdict()` | `skills/daily/tests/test_calendar_day.py` § "The verdict" — a chat window does not corroborate, a call window does, and the noise floor and gap fold are the timeline's, imported from `aw_client` rather than spelled again | `SKILL.md` Step 3 soft boundaries (which names the wrapper) and Step 2's load bullet (which runs it), `references/classification-rules.md` §3 (the Teams title shape), `docs/adr/0008-…` §Decision "ranked by corroboration", `CHANGELOG.md` |
| Workspace resolution is anchored on the install shape, not a depth; a plugin's own root is never a workspace | `docs/skills/daily/decision-log.md` §"Workspace resolution is anchored on the install shape, not on a depth" | the `find_workspace` install-shape tests in `skills/daily/tests/test_config_seam.py` — the directory the skill is installed under, the shared export, and a plugin install that resolves to no workspace around it | `scripts/skill_config.py` `_install_workspace()` docstring, `CHANGELOG.md` |
| The `scripts/` prefix is resolved from the directory `SKILL.md` was read from, never written down | `SKILL.md` "Running the scripts" | the repo-level `tests/test_install_scripts.py` guards; the repo-level `tests/test_install_shapes.py` for the two skills that resolve a *sibling* the same way (`daily` or `billables-daily` by install shape) | the `setup` skill's "Finding the files this skill needs" |
| An allow-list ask names the task and the interpreter and script paths read back off the registered task — never a folder-wide exclusion — and a block is evidenced before it is escalated | the `setup` skill's `references/endpoint-security.md` | the repo-level `tests/test_setup_skill.py` — the ask names what the setup script registers, and the evidence section comes before the escalation | `README.md`'s endpoint-security note, the `setup` skill's Step 5 "If it fails" |
| The browser extension's ID, which is what a managed browser's `ExtensionInstallAllowlist` takes | the `setup` skill's `references/endpoint-security.md` §"The browser extension" | the repo-level `tests/test_setup_skill.py`, which reads the ID out of the reference and finds the same one in the `setup` skill's `SKILL.md` and in `README.md` | the `setup` skill's Step 2, `README.md` step 2 |
| Which signal types compile into a category rule, and the order a rule made from one outranks another — most specific first, the profile tag last | `scripts/category_rules.py`, `SIGNAL_RANK` and `NOT_IN_A_TITLE` beside it, which carry the reasoning for both halves | `skills/daily/tests/test_category_rules.py` — the ordering is asserted against candidates supplied in the wrong order, and a type that never reaches a window title is asserted to be skipped rather than refused; the repo-level `tests/test_setup_skill.py` reads the two tables out of the script's syntax tree and fails any type the `setup` skill's step 4 offers that the compiler would not accept | the `setup` skill's step 4 (the list a run picks a type from), `SKILL.md` "Files in this skill" (the `category_rules.py` entry), `CONTEXT.md` § **Profile tag** for why that one ranks last, `CHANGELOG.md` |
| Where the category rules' backup and stamp live: `<workspace>/.mcp/`, `aw-categories-<timestamp>.json` and `category-rules.json` | `scripts/category_rules.py`, `STATE_DIR` / `STAMP` / `state_dir()`, whose docstring carries why a read mode does not create the directory | `skills/daily/tests/test_category_rules.py` — the backup's contents and path are asserted, and a `--status` run is asserted to leave no directory behind | `SKILL.md` "Files in this skill", `references/first-run.md` §"ActivityWatch categories" (which names the backup file a user recovers from), the `setup` skill's step 4, `README.md` §"The category rules", `docs/adr/0007-…` §Decision, `docs/skills/daily/decision-log.md`, `CHANGELOG.md` |
| The staleness verdicts `CURRENT` and `STALE`, which is what a run branches on at Step 2 | `scripts/category_rules.py` `status()` | the repo-level `tests/test_daily_skill.py`, which reads both words out of that function's source and fails a Step 2 that stops carrying either — the same shape as the calendar wrapper's two refusals, and for the same reason: the words are the whole difference and the exit code is 0 either way | `SKILL.md` Step 2's two bullets, `CHANGELOG.md` |
| The breadth ceiling: a compiled rule matching more than 0.35 of the sampled window titles is refused as over-broad, because the first matching rule wins and a broad one takes the label off a correct one | `scripts/category_rules.py` `DEFAULT_MAX_SHARE`, whose comment carries the measurement it was set from (256 of 552 titles in one day) | `skills/daily/tests/test_category_rules.py` — refused at the default, written when the flag raises it. The *number* in the prose copies is held by nothing; the flag name is | `references/context.md.example` § Preferences (`--max-share`), `SKILL.md` "Tunable defaults", the `setup` skill's step 4 failure branch (which quotes the refusal's wording, not the number), `README.md` § "The category rules" ("about a third"), `CHANGELOG.md` |
| A version bump is the only thing that reaches an installed user, so the manifest version and the changelog's newest heading must agree | `.claude-plugin/plugin.json` `version` | the repo-level `tests/test_distribution.py::test_every_version_marker_agrees` | `AGENTS.md` §Releasing, this file's own §Releasing below |

### Held by a reader

Before changing any of these, change every copy, and search for the *rule* rather than the
wording you happen to have in front of you. A row that gains an instrument moves up to the
first table and names it there.

| Rule | Owner (carries the reasoning) | Restated at |
|---|---|---|
| `--cover` takes every entry Step 9 will post | Step 6 guard 3 | Step 8 checklist |
| `work_end` is a ceiling | Step 3, second bullet | Step 6 guard 2, Step 8 checklist |
| A corroborated calendar event is drafted over the wrapper's `block` span, verbatim — the one block that may cross a break and run past `work_end`, and the break it swallows is declared under the table. An uncorroborated one is never *drafted* as a block — the row below is what becomes of it | Step 3's calendar paragraph, and `docs/adr/0008-the-calendar-is-evidence-of-intent-not-activity.md` §Decision for why corroboration is what ranks them | Step 6 guards 1, 2 and 3, Step 8 checklist, Step 2's load bullet and the `calendar_day.py` inventory entry (both of which say what a run does with the verdict), `references/output-format.md` §Conventions break rows (where the covered break keeps its row and the entry over it is declared in the Notes), `CHANGELOG.md`. #49 story 35 asks for one named exception across the guards rather than one each, so that they stay auditable: if a third guard looks like it needs one, re-read all three before writing it. Guard 2 quotes the `block` span deliberately — the first draft said `evidence`, which is the same field one step earlier in the arithmetic and would have shrunk away the minutes the exception exists to bill |
| An uncorroborated event is a **calendar question** under the table — one line each, out of the block counts and out of `--cover`, out of batch-accept, and a block over the event's span only once the user answers yes | Step 6's calendar-questions paragraph, and ADR-0008 §Decision "Uncorroborated" for why the answer is the user's | Step 3's calendar paragraph (which routes them there), its two `work_end` / break parentheticals and its `active_ratio` bands (which a user-dictated block is not validated against), the review-question quote and the rule that drops its calendar clause when there are none, Step 8's `work_end` line and its 🔸 line, Step 10's response-file line (an accepted block's only evidence is the answer, so the answer is recorded with it), the `calendar_day.py` inventory entry, `references/output-format.md` §Conventions break rows, the **Calendar** glossary entry in `CONTEXT.md` (which coins the term, and through it the vocabulary check holds the workflow to it), `README.md`'s feature list, `CHANGELOG.md`. §"The instrument" above says what the three assertions in `tests/test_daily_skill.py` do and do not reach; the exclusion sentence and everything after a yes are prose only. An accepted block is *not* a third guard exception — guard 1 owns the distinction, that the guards read the blocks *you* drafted and never touch one the user dictated, which is what makes it survive a loop back from Step 8. That sentence settles the guards and nothing else: the rules that would still undo the user's answer are the ones that never mention a guard (the ratio bands, the 0.25 hr fold, the questions heading), so walk for "every block" rather than for "guard" |
| No entry under 0.25 hr | Step 3, `0.4–0.7` band | Step 3 granularity line, Step 6 guard 1 |
| Per-user facts belong in `.context.md` | "What lives where" | Step 11, Non-negotiables |
| Work kind and task selection, and interleaved days | `references/classification-rules.md` | Step 4 points at it |
| One date per session | Step 12 | Step 1 scope paragraph, Step 10 wrap-up |
| Read `.context.md` whole, never partially | Prerequisite 1 | Step 2 load list, Step 11 size budget |
| Check the date against Harvest before rebuilding it | Step 1 | Step 8 checklist |
| Timesheet-admin time needs a screenshot before it is booked *or* accepted | `classification-rules.md` billing conventions | Step 1 already-covered branch |
| A skill defect goes upstream, not into `.context.md` | `references/reporting-issues.md` | Step 11 third bullet |
| Screenshots never settle active/idle — nor does the calendar | Step 5, first bullet | `SKILL.md` folder mechanics, Step 3's calendar paragraph ("the calendar re-infers idle no more than a screenshot does"), `classification-rules.md` §"Focused window ≠ active attention", `docs/adr/0008-…` §Context, which is the rule the whole calendar decision was shaped around |
| Check the other monitors before trusting one | `classification-rules.md` §"Focused window ≠ active attention" | `SKILL.md` folder mechanics + Step 5 subagent brief, `classification-rules.md` long-agent-CLI and browser-row paragraphs, interleaved-days probe step |
| The published configuration reaches the **Bash** tool and nothing else, so every read of a configured value happens there and PowerShell is handed the resolved literal | `scripts/skill_config.py` `note_for_an_unreached_shell()`, which is the copy a run is shown at the moment it matters | the precedence block at the top of the same module, `hooks/publish_plugin_config.py` module docstring and its `.sh` wrapper's second known limitation, `SKILL.md` "Running the scripts" + "Screenshot location", the `reconcile` skill's screenshot-index step, the `setup` skill's "Before you start" probe + step 5, `references/first-run.md` §"When the configuration does not arrive" cause 1, `README.md` §Updating step 2 and §8 step 3, the repo-level `tests/test_plugin_config.py`, `tests/test_setup_skill.py`'s two cross-skill guards, `skills/daily/tests/conftest.py`'s session-marker pin and `skills/daily/tests/test_config_seam.py`'s `REACHED`/`UNREACHED` constants, `scripts/calendar_day.py`'s off message (a toggle that never arrived reads as *off*, so that message carries the note too) and `skills/daily/tests/test_calendar_day.py`'s unreached-shell test, `docs/skills/daily/decision-log.md` §"Two ways the configuration does not arrive" and §"The calendar toggle and the wrapper behind it", `CHANGELOG.md`. Here rather than above on purpose: the scope is the thing to check when changing any of them, and it belongs to the harness, so no test here can hold it — which is why the first version of the check tested a *proxy* for the shell, passed, and was silent for the user it was written for. The tests encode whatever the check believes; change the check and the constants are the first thing that has to move |
| The judgement tunables live in the user's `## Preferences`, and reach the scripts as flags — never as an edited constant | `references/context.md.example` §Preferences | `SKILL.md` "Tunable defaults", the two scripts' constant blocks |
| Standing the pipeline up for the first time is the `setup` skill; `references/first-run.md` is the mid-run diagnostic for a prerequisite that failed on a machine already working | the `setup` skill's `SKILL.md` | `SKILL.md` "When to invoke", `references/first-run.md` header, `AGENTS.md`, `README.md`'s install section |
| A **profile tag** belongs only on a browser profile dedicated to one client; a general or default profile carries none, and its time is attributed from the page's own evidence | `CONTEXT.md` § **Profile tag** for the rule and the reason it is ranked last, the `setup` skill's step 3 for the procedure and the migration | `README.md` step 3, `references/first-run.md` §"ActivityWatch categories", `demo/tag-rule-demo.html` scenario 5 — which is the executable copy, showing an hour of a client's work claimed by a general profile's tag and released when that tag is cleared — the `setup` skill's finish, `CHANGELOG.md` 0.8.0 §Upgrading. The repo-level `tests/test_setup_skill.py` holds the *step*, not the rule: it fails a step 3 that stops saying which profiles carry a tag, and cannot see a README that says the opposite |
| The click-path through the URL-in-title options page, and the manual category procedure step 4 falls back to where the activity source will not take a write | the `setup` skill's `SKILL.md` steps 3 and 4, which are what a run reads out | `README.md` §"Tag the browser profiles that belong to one client" and §"The category rules", which are the reading version. These drifted on save order before anyone noticed, and the README went on naming a nested `Work > Acme` where the skill keeps the category flat until #68 — the timeline joins a name path with `>`, so the two are not interchangeable. What the two copies still share is smaller than it was, because the rules are no longer a procedure the user follows: the options page, and the fallback |

The `--cover` pair has already drifted once and cost a re-run — the decision log has the
entry. The fix at the time touched the checklist copy and missed the owner.

Don't write exclusivity claims ("this is the only place that says X") into any of these
files. They enforce a snapshot and rot silently into something that still reads as
authoritative.

## When you don't maintain this copy

This file assumes you can change the plugin and ship it. A user who installed it cannot, and
the route for a defect they found is `skills/daily/references/reporting-issues.md`: the
redaction, the gate before filing, the issue form. When this file was `self-development.md`,
three of three test agents handed a genuine script defect came looking here for that route,
because the name read as if it covered it. `CONTRIBUTING.md` is the name an outside reader
reaches for first, so the pointer sits in the opening paragraph as well as here.

## Releasing

There is one copy: this repo is the plugin, and installing it is `/plugin install`. A
change ships by being committed here — nothing to propagate, no second leg to verify, and
no marker inside the skill to keep in step.

Bump `version` in `.claude-plugin/plugin.json` and add the matching `## [x.y.z]` heading to
`CHANGELOG.md` in the same change — those two are what `tests/test_distribution.py` holds
together, and it fails when they disagree. A user on the shared Agent Skills
export re-runs the export to update; it is generated from this plugin every time, so their
copy cannot be a stale fork of it.

Add an `### Upgrading` section to that changelog entry whenever the update alone is not
enough — a setting that has to move, a script to re-run, a scheduled task pointing at a path
the change invalidates. An update installs itself; anything a user has to do by hand is
invisible until the run that needed it fails, and by then the release notes are weeks back.

Then tag it, so the version is a commit somebody can check out and not only a heading:

```
git tag -a vX.Y.Z -m "X.Y.Z — one line"
git push origin vX.Y.Z
```

`git push` does not carry tags, which is why the second line is there. Tag the last commit
of that version rather than the one that bumped the manifest, if cleanup followed it.

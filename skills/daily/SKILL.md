---
name: daily
description: Fill in, review, regenerate, or backfill a daily timesheet from ActivityWatch data and log the time to the timesheet provider (Harvest by default). User-invoked.
compatibility: Runs bundled Python scripts, so it needs Python 3.10+ on the PATH and a harness that can execute local commands. Reads a running ActivityWatch server (default http://localhost:5600) or a daily_exports/ dump of one. Logging time needs Harvest credentials. Screenshot capture is Windows-only.
disable-model-invocation: true
---

# daily

For consultants who track time across multiple clients. ActivityWatch plus a scheduled screenshot grabber (`~/Pictures/WorkScreenshots/`) capture the workday; this skill turns that into a reviewable billable timesheet and (with confirmation) posts it to Harvest.

**Read the whole Workflow section before starting a run — the guards in Steps 3 and 6 are where runs go wrong.**

## What lives where (read before adding any new fact)

This skill is **shareable** — sort every fact by who it applies to; don't use the cross-session memory store.

- **Generic mechanism** (any user) → `SKILL.md` / `references/` / `scripts/`.
- **One user's facts** → `Timesheets/.context.md` in the user's workspace: clients, colleagues, signals, billing-convention *overrides*, machine specifics, the work-item source (§ "Work-item source"), prefix→client map. Read every run; size-budgeted (Step 11).
- **This machine and account** → declared plugin configuration (`/plugin configure billables`): Harvest credentials, and the optional `TIMESHEET_TIMEZONE` / `TIMESHEET_ACTIVITY_URL` / `TIMESHEET_SCREENSHOTS_DIR` / `TIMESHEET_WORKSPACE`. The harness holds the credentials; there is no secrets file to create, read or share. An exported install keeps the same keys in a gitignored `.env`; share `.env.example`, never `.env`.

Precedence: flag, `.env`, process environment, script default; blank is unset (`scripts/skill_config.py`).

## When to invoke

**Strong triggers** — invoke without further confirmation: "summarise yesterday" / "what did I do on <date>" / "fill in <day>'s timesheet" / "log time for <date>" / "review today's work" / "backfill the timesheets".

**Soft triggers** — confirm first: the user mentions Harvest, ActivityWatch, `daily_exports/`, `Timesheets/` in passing; a new export landed and the user seems unsure what to do with it.

**Do NOT invoke when:**
- the user is asking about *configuring* the pipeline itself (export script, ActivityWatch setup, screenshot scheduler) — that's maintenance, not daily classification. Standing it up for the first time is the `setup` skill; `references/first-run.md` is for a prerequisite that failed mid-run
- the user wants *raw* Harvest data beyond a date range ("list my projects", "monthly totals") — point at the Harvest web UI or a one-off script


## Data sources

- **ActivityWatch** at `TIMESHEET_ACTIVITY_URL` (default `http://localhost:5600`) — **primary**, through the bundled scripts; raw only per `references/activitywatch.md`. Fallback when unreachable: `daily_exports/<date>/compact.jsonl`.
- **Screenshots** `~/Pictures/WorkScreenshots/<date>/HH-MM-SS_mN.png`, one PNG per monitor — **source of truth, for disambiguation only**: load specific timestamps, never proactively.
- **`Timesheets/.context.md`** — the user's attribution rules, source of truth for every ambiguity call. Read every run.
- **The provider's catalog** — read through `python scripts/provider/bin/timesheet-provider lookup`; no file or field is named here. **`.mcp/<catalog>.txt/.json`** is the work-item catalog (number → title).
- `Timesheets/<date>_timesheet.md` — optional audit trail, only on request, per `references/output-format.md`.

**Screenshot location.** Default `~/Pictures/WorkScreenshots/`; `TIMESHEET_SCREENSHOTS_DIR` overrides it. Resolve it once, **in Bash**, with `python "<this skill's folder>/scripts/screenshot_capture.py" --where` (never an `echo` of the setting) and quote the result in PowerShell. List it with PowerShell `Get-ChildItem`; Bash `dir`/`Glob` return empty. **A capture of wallpaper, a lock screen or a black screen is evidence about that monitor and nothing else**, never about whether the user was working; check the other monitors too. More: `references/day-reading.md`.

**Timezone.** Scripts use `TIMESHEET_TIMEZONE`, or this machine's own zone, applied at each instant (a daylight-saving change needs nothing from you). **There is no assumed zone and no default offset**; a run that can read neither stops and says so. A machine-read zone is labelled `derived from this machine` in every skeleton header and JSON `zone` field — **carry that label into the timesheet's Notes and the Step 8 confirmation**. On the day the clocks go back the repeated hour's second pass is suffixed `*` (`02:30:00*`): pass it to `--window` / `--cover` as part of the time. `--utc-offset <hours>` overrides for one run. See `references/activitywatch.md`, `references/output-format.md`.

**Running the scripts.** Every `python scripts/…` command is relative to *this skill's own folder* — the directory this `SKILL.md` was read from — not the workspace. Prefix it with that folder's absolute path, resolved once and reused; never guess one. Catalog paths resolve from the workspace. **Run scripts and read every configured value in Bash** — the configuration reaches Bash alone; paste the resolved literal into any PowerShell command. `python` means the interpreter this machine uses (`.context.md` → Machine records it): on Windows a bare `python` may be the Store stub (Store stub, exit 49: a missing interpreter; `py` usually works).

## Prerequisites — check at start of every run

Run in parallel before classifying anything. If a first-run piece is missing (workspace, `.context.md`, credentials, timezone, screenshot task, AW buckets), follow `references/first-run.md`.

1. **`Timesheets/.context.md` — read it, whole, every run.** If missing, run first-run setup; don't classify without it. Template placeholders (`<Full Name>`) are not facts: walk them with the user by `references/first-run.md` first. **Read the entire file; never grep it, never read a slice, never skim to the section you think you need.** Its facts are cross-cutting — an exclusion in one section decides a block whose client is named in another.
2. **ActivityWatch reachable** — `curl -s <activity-url>/api/0/buckets/` returns JSON, with the *configured* URL. If not, use `daily_exports/<date>/compact.jsonl`; if both are missing, say the day can only be reconstructed from screenshots and the user's memory.
3. **AW bucket ids resolved** — from `.context.md`, else discover and offer to cache.
4. **Catalogs fresh** — `python scripts/provider/bin/timesheet-provider refresh --age` prints `AGE <days>` or `ABSENT`; refresh with `timesheet-provider refresh` at `AGE` ≥ 7 or `ABSENT` (surface an `AGE` over 30 first, unless `.context.md` preferences say refresh silently). Work-item catalogs modified within 7 days; else `python scripts/refresh_catalogs.py` (with no work-item source in `.context.md` it says so and writes nothing — `references/catalog-refresh.md`).
5. **Provider credentials work** — `python scripts/provider/bin/timesheet-provider list <today> <today>` exits 0 (an empty day prints a notice and still exits 0). Exit 3 → credentials not found, `references/first-run.md`; 4 → refused (the user must regenerate it); 5 → no network.

**Tunable defaults** (override in `## Preferences`): AFK break threshold `1050s`; active/thin bands `0.7`/`0.4`; minimum billable block `0.25 hr`; smallest uncovered stretch worth flagging `900s`; the rest are in `references/context.md.example` § Preferences. Where `## Preferences` differs, **pass the flag the template names** — never edit a constant in `scripts/`. **Task names have no default and cannot have one**: the rubric decides a *work kind* and `.context.md` § "Work kinds" maps it to the user's own task. With no mapping, match the work kind against the tasks `timesheet-provider lookup` lists for the project, never a guessed name, and propose the row at Step 11.

## Workflow

The mechanism, the reasoning and the worked cases behind each step are in `references/day-reading.md` (Steps 1–3) and `references/review-and-posting.md` (Steps 6–12). What follows is what a run must do and must not.

### Step 1 — Resolve target date and scope

If the user gave a date, use it, then **check whether it is already billed** (below) before loading anything. Otherwise list the past ~10 days' entries (`python scripts/provider/bin/timesheet-provider list <from> <to>`), cross-reference the screenshot folder, and default to the oldest fully-unbilled *prior* day; mention today's partial state separately (**today is never a reason to ask**). No gaps → "all caught up" (offer today-so-far).

**One date per session.** "Backfill the timesheets" scopes the goal, not this run: report the whole gap list, work only its oldest entry; Step 12 hands off the rest.

**Check the target date against Harvest before rebuilding it, on *every* run:** `python scripts/provider/bin/timesheet-provider list <date> <date>`, before Step 2. Steps 3, 6 and 8 check against ActivityWatch, never Harvest, so a duplicate day passes every guard and double-bills the client. `Timesheets/<date>_harvest_responses.json` is a free done-marker and the record of what was decided.

- **Already covered** → *verify*, don't redraft: run Step 6's `--cover` on the existing entries and read one screenshot inside every **non-billable or internal** entry (`--cover` can't see right clock, wrong project). Propose changes only where evidence contradicts an entry.
  - **Read `Timesheets/<date>_harvest_responses.json` whole** first — its keys are ad hoc, so a partial read is a confident wrong answer.
  - **A ruling the user gave on a window binds; re-deriving the evidence does not reopen it.** Say the recomputation disagrees and leave the entry; only new information reopens it.
  - **Proposing a *reduction* (delete, trim, repoint) loads `references/classification-rules.md` first** — its guards against over-reading a thin block live there.
- **Partly billed** → treat billed windows as fixed; scope this run to the gaps unless told otherwise.
- **Nothing there** → Step 2.

Convert relative dates in the user's timezone. **Partial-day scope** ("only the morning") restricts classification to that window.

### Step 2 — Load inputs

Read in parallel:
- `Timesheets/.context.md` — the **whole** file, if not already read this run
- `references/classification-rules.md` (the rubric). `references/disambiguation.md` is not loaded here: Step 5 reads it once a block is flagged **or the day is shared between clients**
- Cached catalogs from `.mcp/`
- `python scripts/category_rules.py --status` — **before the timeline**, which labels every span with these rules. Branch on the word (every verdict exits 0):
  - **`CURRENT …`** — nothing to do.
  - **`BROKEN …`** — rules the activity source never matches. **Stop before the timeline**; tell the user `/billables:setup` replaces them. Don't rebuild them here.
  - **`STALE …`** — a client's **Category terms** moved, or the rules were never written. Rebuild before the timeline: `python scripts/category_rules.py --from-context`, which reads every client's **Category terms** from the context file itself. A client without terms is reported `NOTERMS`, and its rule is `DROPPED`; say so at Step 11. Tell the user what changed and carry on; a refused rebuild is raised at Step 11, not a stop.
  - **`UNVERIFIED`**: `dormant` needs nothing said; `suspect` means the client was worked on and a term never appeared — finish the day, then at Step 11 tell the user to run `/billables:setup` (its `SEEN` lines name the profile tags the titles carry). `OVERLAP` is raised at Step 11 the same way.
- `python scripts/category_rules.py --dormant <date>` — read-only; `DORMANT <category>` is a rule that matched in the fortnight before and nothing on the day. Draft anyway and say at Step 11 which went quiet.
- `python scripts/afk_blocks.py <date>` — the day skeleton (work_start/end, breaks, active spans)
- `python scripts/activity_timeline.py <date>` — merged window spans tagged with the AW category, plus rollup. **Compact output is enough**; zoom with `--window HH:MM-HH:MM`, not `--full`.
- `python scripts/calendar_day.py <date>` — the day's **calendar events**, each with a verdict: `corroborated` true or false, and if true the `evidence` span and proposed `block` span. Run it **in Bash** and judge it by its **`ERR` line, not its exit code** (every refusal exits 1):
  - **`ERR the calendar is off: TIMESHEET_OUTLOOK_CALENDAR is not set to true …`** — the only benign refusal; most installs. Read the day from the other sources and say nothing more. (If the line names a shell, you are in the wrong shell.)
  - **Anything else stops the run** — report the `ERR` line as it stands. A calendar the user turned *on* and did not get silently loses meetings; don't retry without the toggle or run the adapter yourself. `the calendar stays *off*: …` is not the bullet above: the toggle is on and the calendar cannot be read here.
  - **One reason is neither** — ActivityWatch unreachable while you read `compact.jsonl`: say once the calendar could not be read either. An event with no verdict is an unanswered question, not an uncorroborated one.
- `scripts/checkin_answers.py` — typed answers on return. Do not run it bare: the full command is in `references/check-in-answers.md`. `off`, `absent`, `empty` need nothing said, else read it.
- Screenshot index: list the day's folder (PowerShell). Don't open PNGs yet.
  - **`captures: none for this date` in the skeleton is the capture task dead all day** — treat every block as having no screenshot fallback; raise it at Step 11.
  - **Compare the last capture's timestamp against `work_end`.** If captures stop well before it, say so with the skeleton and flag later blocks 🔸 on weaker evidence. A dead capture task is maintenance: finish the day first (`references/first-run.md`).

AFK anchors the boundaries and the timeline shows what is inside them; the calendar records what the user was *meant* to do, so an event is settled by the wrapper's verdict, not the timeline. Don't derive any by hand (sole exception: AW unreachable — `references/activitywatch.md`).

### Step 3 — Block the day

**The skeleton is arithmetic, not judgment — take it verbatim:**

- **Breaks = `afk_blocks.py`'s `breaks` list** (afk ≥ threshold), plus any the user states. Never invent, stretch or infer one from short AFKs, window gaps or screenshots. One exception: a window-event gap ≥30 min with *no AFK record covering it* is also a hard boundary.
- **`work_end` = the script's `work_end`** — a *ceiling*, not a magnet. A window left in focus reads as "still working"; never extend a block to the screenshot or work-hours window. When `work_end` is a momentary blip (the script flags it), end the final block at its last *substantive* active span. (A declared calendar block may end after it — Step 6.)
- **A block runs from an active-span start to the next break start (or `work_end`)**, never across a break. (A declared calendar block may — Step 6.)
- **AFK events `< 1050s` fold in** — duration not subtracted.

**Validate every block with its `active_ratio`** (`afk_blocks.py <date> --window HH:MM-HH:MM`). A `.context.md` billing convention can override the verdict; a block the *user* dictated is not ratio-validated (their answer is the evidence, and a meeting the machine never saw scores 0.0):
- `≥ 0.7` — active; fold in short AFK.
- `0.4–0.7` — thin. Flag 🔸 and shrink to the contiguous active spans, then **re-merge for billing**: adjacent shrunk pieces with the same attribution become ONE entry whose duration ≈ summed active minutes, the netted-out idle noted in the presentation. Never propose an entry under 0.25 hr — fold it into a same-client neighbour or drop it, with a note.
- `< 0.4` — mostly idle; do not propose billing. Ask the user, citing screenshot timestamps. Window duration ≠ work time.

**Work fragments inside an excluded stretch**: ≥10 min for one client → bill it; under 10 min → surface, leave unbilled. **Under-billing is as much an error as over-billing**: `work_end` is the ceiling, `--cover` the floor.

**Soft boundaries** — split only where it improves classification: a sustained context switch (≥3 events on a different ticket/profile, ≥3 min); a Teams meeting (`Meeting | …` / `Call with …`), its own block even when attended while multitasking; an active-ratio drop.

**A corroborated calendar event is one block over its `block` span**, verbatim and unmoved at its start, *even across a break the skeleton recorded*. Nothing else about the skeleton changes: **AFK is settled by the AFK watcher, and the calendar re-infers idle no more than a screenshot does.** The break it swallows is declared with the draft (Step 6 guard 1). It is classified like any block and **replaces what it covers rather than doubling it**: drafted blocks either side tile up to its edges, never overlapping. An `evidence_share` under about 0.5 is a meeting on another monitor: read the call timer in a capture (`references/classification-rules.md` §3) and correct from it. A span starting before `work_start`, or ending after `work_end` **when the `evidence` stops earlier**, is flagged 🔸 and put to the user.

**An uncorroborated event is never drafted as a block.** Leave it out of the draft and the coverage check; Step 6 puts it to the user as a **calendar question**, and it becomes a block only on their answer.

### Step 4 — Classify each block

Attribution — **client + project + task + billable + confidence (high/medium/low)** — per `references/classification-rules.md`:

Full wording: `references/day-reading.md` § "Steps 4–5 and the data sources".

- The AW category is a client-level first pass only; investigate every `uncategorized` and `!MULTI` span.
- Work-item-shaped strings (`[A-Z]{2,4}\d{3,}S?`) are the highest-confidence signal: resolve the title in the work-item catalog and the project/task via `python scripts/provider/bin/timesheet-provider lookup <code-name-or-client>`; never hand-roll a glob loop. **A client's name is a first-class search term, and the top hit is not automatically the right project** — read all candidates; an all-non-billable task set is the tell for a shell.
- **Task and billable status follow the rubric's "Work kind and task selection" exactly**: `.context.md` overrides, then the dominant activity gives a work kind, then `.context.md` § "Work kinds" gives the task name. Billable comes from what `lookup` returns for the task, never from its name.
- **More than one client in the day, or a block titled by an agent-session file (`CLAUDE.md`, `AGENTS.md`, plan `.md`s): apply `references/disambiguation.md` § "Interleaved days" before accepting any block over an hour.**

### Step 5 — Disambiguate flagged blocks

Every 🔸 block is resolved here before Step 6 renders it. **Read `references/disambiguation.md` and work it**: the ladder (timeline zoom, a calendar event's own words, screenshots, then ask the user), the two signals that arrive already flagged, the interleaved-day protocol, and what a block may not settle — AFK stays the AFK watcher's. Load it on any day with a 🔸 **and on any day that shows more than one client, flagged or not.** A single-client day that flagged nothing skips this step.

### Step 6 — Present the proposed timesheet

Show, for every block, its time range, duration, client and the note it will post (the client-readable invoice text, with any work-item number). Layout is yours. Flag uncertain blocks 🔸, set apart from the blocks: breaks and end-of-day are deterministic, *which client / billable / where to split* is judgment.

**Three hard guards — all mandatory before presenting:**

1. **Outer block edges are the script's spans, transcribed verbatim** — start at an active-span start, end at a break start / `work_end`. *Interior* splits (client switch, meeting, work-item change) sit strictly inside a span, are evidence-based, and adjacent *billed* sub-blocks tile it exactly; a stretch excluded under Step 3's `<0.4` band is declared as a known exclusion, not tiled over. **Two sanctioned exceptions, only two:** shrunk-and-re-merged thin blocks (Step 3), and a **corroborated calendar block over its `block` span**, which may cross a break and pass `work_end`. Both are declared with the draft; the calendar one names the break it swallowed and the event. An undeclared block over a break is the same defect as a hand-tidied edge. No entry under 0.25 hr. **These guards read the blocks you drafted.** A block the *user* dictated (an accepted calendar question, a window they asked you to bill that no script span supports) is their instruction: no guard shrinks, splits or deletes it, drafted blocks tile up to its edges, and it is declared. A drafted block they merely approved is still the guards', including on a loop back from Step 8.
2. **No block ends after `work_end`.** Shrink any that do, except a user-dictated block and a corroborated calendar block, which ends where its **`block` span** does — **never shrink it to its `evidence`**, which would drop the listening-only minutes the exception exists to bill. Declare it, naming the break; never extend any *other* block to reach it.
3. **Logged blocks must cover the active spans.** Pass *every entry Step 9 will post* — non-billable and calendar blocks included, post-shrink:
   ```
   python scripts/afk_blocks.py <date> --cover "08:30-09:00,09:30-12:30,13:45-17:06"
   ```
   Every `UNCOVERED` stretch (≥15 min active, not in a break) must be billed or listed as a known exclusion (personal browsing per `.context.md`, or a documented thin-block drop). A stretch you are *excluding* is declared and **never passed here** — passing it makes the guard report clean while the under-billing goes unnoticed.

**Calendar questions** — every unanswered uncorroborated event, set apart from the blocks, labelled not drafted and not billed unless the user says so, giving time range, name, who it was with, that no meeting window was seen, and asking whether to bill it. None is a block, so none is in the block counts, in anything passed to guard 3, or 🔸.

- **Batch-accept covers the drafted blocks only**; each calendar question takes its own answer.
- **A yes makes it a block over the event's span**, classified like any other and declared naming the event and the answer. It may sit outside the active spans, across a break or past `work_end`; the guards don't touch it. It **replaces what it covers rather than doubling it** — a yes to a 15:00–15:30 call inside a drafted 13:30–17:00 stretch splits it in three, never a fourth entry on top (`--cover` can't see a double). Under 0.25 hr it folds into a same-client neighbour or goes back to the user. Step 8 lists it and passes it to `--cover`.
- **A no, or no answer, leaves it unbilled** — out of the draft, `--cover` and Step 9; ask once.
- **A check-in question** is not a block: own answer, never in `--cover` or batch-accept.

**Show the AFK skeleton with the draft**: work span, breaks, active minutes, hours billed, active time left unaccounted.

**Then ask for the review.** The question says how many blocks were drafted for the date, how many are high confidence and how many are 🔸, and how many calendar question(s) are pending — with the reminder that batch-accept doesn't cover those. It offers two ways on: walk through the 🔸 ones, or batch-accept and edit after. Leave the calendar clause out when there are none.

Wait for the answer; edit per their input.

### Step 6b — Final verify

Once the user is done editing, check the post preview before anything else: one read-only subagent per block on the cheapest model, each re-reading its start, end, client and any hidden switch against the timeline, AFK data and captures; wait for all of them, then verify each finding yourself (a finding is a lead, not a fact). If anything changed, reprint the whole table with the changes marked. No subagents: run the checklist yourself. Never skipped. Brief and checklist: `references/final-verify.md`.

### Step 7 — Write the timesheet .md *(optional — ask first)*

Harvest is the system of record. **Ask** first; if wanted, write `Timesheets/<date>_timesheet.md` per `references/output-format.md`.

### Step 8 — Confirmation gate before Harvest

First self-check every line of the proposal:

- [ ] `--cover` run and clean — passed **every entry Step 9 will post, non-billable and calendar blocks included**; an excluded stretch is declared, never fed to it. It cannot see a *double*-billed stretch (Step 3's "replaces what it covers" is the only check)
- [ ] Skeleton still current — re-run `afk_blocks.py <date>` if the day was in progress when read or the session crossed midnight
- [ ] No block past `work_end`, none crossing a script break — except a declared calendar block (Step 6 guards 1 and 2)
- [ ] Every `project_id`/`task_id` came from `timesheet-provider lookup`; billable flag checked; task name from `.context.md` § "Work kinds" or `lookup`, never memory
- [ ] Every Harvest note passes the client-readability test (Non-negotiables)
- [ ] All 🔸 blocks resolved and every calendar question put to the user — a no or silence is not an entry and is not posted
- [ ] `.context.md` exclusions applied
- [ ] **The date isn't already billed** — re-confirm Step 1's Harvest check; skipping it double-bills a client

Then put the posting question: how many time entries this will create, and for each one its hours, client, project and task, with `[Support]` where it applies, and its note exactly as it will post. When the skeleton's header read `derived from this machine`, add the zone: times in that zone, derived from this machine, and that `TIMESHEET_TIMEZONE` pins it (a configured zone is not announced). Close on yes, no, or edit a named block.

**An explicit "yes" or equivalent earns `--confirm` in Step 9** — without it nothing is written. Edits loop back to Step 6, then through Step 6b again.

### Step 9 — Post to the provider

For each confirmed block, serially (so the user can interrupt):

```
python scripts/provider/bin/timesheet-provider post --project-id <project_id> --task-id <task_id> --date <YYYY-MM-DD> --start <HH:MM> --end <HH:MM> --notes '<notes>'
```

- **Append ` --confirm` once Step 8 has the user's yes.** Without it the script prints `WOULD POST <body>`, exits 0 and creates nothing; never record that as posted.
- Times 24-hour zero-padded (`16:05`), dates `YYYY-MM-DD`; `4:05pm`, `20260812` and a `*` marker are usage errors (exit 2) — strip the marker first. **Single-quote the notes.**
- Success prints `OK <entry_id>` — capture it. Failure prints `ERR <message>`, exit 2–5 (usage, configuration, refused, unreachable): stop and surface, don't retry silently; after a 5 the entry may exist, so `list` first.
- **On the day the clocks go back, a block worked straight through the change is refused** (billed short by the repeated span). The `ERR` names the two entries to post instead; post both, don't close the overlap. `patch` refuses the same way; see `references/output-format.md` §Conventions.
- Report each post as it lands: hours, project code, task.

Fix a wrong entry with `python scripts/provider/bin/timesheet-provider patch <entry_id> [--start HH:MM] [--end HH:MM] [--notes "..."] [--project-id ID] [--task-id ID] [--date YYYY-MM-DD] [--confirm]` — at least one field flag, no duration flag, previews as `WOULD PATCH` until `--confirm`. A patch overwrites a line the user already approved, so it needs its own yes.

**Brand-new client work with no project yet** → `references/new-client-work.md`.

### Step 10 — Wrap-up

Summarise total hours posted, blocks deferred or skipped, and whether more days are outstanding — **don't name the next date here**; Step 12 does after the reset ask. Save the entry ids to `Timesheets/<date>_harvest_responses.json`: `{"entries": [{"id": 2933345845, "project_code": "NWC-001", "hours": 0.25, "notes": "..."}], ...}`. **Record every calendar question the user answered there too — yeses and noes, with the answer — and check-in questions under `checkin_questions`.** An accepted block has no activity evidence behind it, and Step 1's already-covered branch looks here for a ruling. A recorded no binds: that date does not ask again.

### Step 11 — Surface skill or `.context.md` improvements

Present what the run revealed, **one fact per ask, as the exact diff**: this user's clients/signals/preferences → `.context.md`; a generic heuristic or API quirk → `SKILL.md`/`references/`; the skill being wrong (a script answers wrongly, a guard didn't fire) → `references/reporting-issues.md` if installed, `docs/CONTRIBUTING.md` if maintained.

**A yes to a diff that adds or changes a client's Category terms rebuilds the category rules in the same breath** — write the file, run `scripts/category_rules.py --from-context`, report what it wrote in a line, and don't ask twice. A refusal or `suspect` line is reported here.

**`.context.md` size budget — check after every edit**: `(Get-Item Timesheets/.context.md).Length` under **14,000 bytes** (override in `## Preferences`). Over → compact now: (1) move generic rules into this skill's references; (2) delete facts proven wrong or superseded; (3) shorten examples to the date stamp. If that would drop a live user fact, ask which — never silently delete, never read part of the file instead.

### Step 12 — One date per session, then reset

**Finish one date per session and stop.** A date is done when nothing is left to post (posted, declined at Step 8, or no write in scope), Step 10 is wrapped up and every Step 11 proposal is written or declined. A partly-scoped date is **not** done.

**Then, only if days remain**, ask for the reset *before* naming the next date: where this date landed, that days are outstanding, and a request to run `/clear`. **Say to re-invoke the skill in the same breath** — it is not model-invocable, so a bare "do Thursday" in the cleared session runs without these guards. Today-so-far counts as a next date; all caught up → say nothing about resetting; if you can't tell whether days remain, ask rather than sweeping. Won't clear → ask for `/compact`; declines both → do as they ask and say once the next date will be read against this one's conclusions. You cannot run either; **don't open the next date in the same turn as the ask.**

## Non-negotiables

- **No provider write without explicit confirmation.** `post` and `patch` write only with `--confirm`. Never type it on a yes you don't have — a posted entry is not recoverable from your side.
- **Honor `.context.md` exclusions** — personal browsing, AFK breaks and personal home admin are NEVER billable.
- **Don't fabricate confidence.** A block that could be 2–3 clients gets surfaced, not arbitrated.
- **Entry notes are client-readable.** They go out on invoices: describe *what part of the client's project* was worked on, never the internal mechanism, file names, internal app names, or chat partners. If a term wouldn't appear in the SOW or on the client's own board, it doesn't go in the note. Work-item numbers (`ACM2232S`) and recurring meeting names are fine. Style: the rubric's "Writing the entry note" and `.context.md` "How I bill".
- **`.context.md` is the source of truth for per-user facts** — propose new user facts there, not in the skill.

## Files in this skill

`references/scripts.md` lists every script with its flags; read it before running one you have not used this session. The references: `first-run.md` (first-run setup, screenshot health check, category maintenance), `context.md.example` (the `.context.md` template), `classification-rules.md` (the rubric, read at Step 2 on every run), `disambiguation.md` (Step 5), `final-verify.md` (Step 6b), `check-in-answers.md` (Step 2 answers), `day-reading.md` (mechanism behind Steps 1–3 and the screenshot folder), `review-and-posting.md` (mechanism behind Steps 6–12), `scripts.md`, `activitywatch.md`, `output-format.md`, `catalog-refresh.md`, `new-client-work.md`, `reporting-issues.md`.

`.env.example` is the credential template. `docs/CONTRIBUTING.md` and `docs/skills/daily/decision-log.md` are in the repository, not an installed copy: **for changing this skill, not running it**.

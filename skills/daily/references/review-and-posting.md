# Reviewing and posting: the mechanism behind Steps 6-12

`SKILL.md` Steps 6 to 12 hold the guards a run acts on and point here for the full text of each,
and for the reasoning. Load this file when drafting the presentation, running the confirmation
gate, posting or patching, or wrapping up. Nothing here relaxes a guard in `SKILL.md`.

## Step 6: presenting the proposed timesheet

The draft is what the user reviews: for every block, its time range, duration, client and the note it will post — the client-readable text that goes out on the invoice, carrying the work-item number where there is one. Showing the note here is what lets the user correct it before Step 8. What this step fixes is the content the user sees; the layout is yours — present it in whatever form this harness shows best, unless the user has asked for a particular one.

Flag uncertain blocks 🔸, set apart from the blocks themselves. End-of-day and breaks are deterministic; *which client / billable / where to split* is judgment — flag it rather than committing silently. The user's review is what makes the sheet accurate, so make uncertain calls easy to see.

**Three hard guards — all mandatory before presenting:**

1. **Outer block edges are the script's spans, transcribed verbatim.** A block starts at an active-span start and ends at a break start / `work_end` — don't hand-tidy or merge those edges. *Interior* splits (classification boundaries at a client switch, meeting, or work-item change) are allowed and expected — they must sit strictly inside a script span and be evidence-based, and adjacent sub-blocks must tile the span exactly. **"Tile the span exactly" governs adjacent *billed* sub-blocks.** A stretch excluded under Step 3's `<0.4` band is declared as a known exclusion with the draft (guard 3), not tiled over — removing it is not inventing a break, and the blocks either side keep their evidence-based edges. This matters most on a day with no breaks at all, where the span is the whole day and its ratio can pass `≥0.7` while hiding stretches that are nearly dead. **Two sanctioned exceptions to verbatim edges, and only two:** shrunk-and-re-merged thin blocks (Step 3), and a **corroborated calendar event drafted over its `block` span** (Step 3) — the one block that may run *across* a break the skeleton recorded, and past `work_end` where its own evidence does (guard 2). Both are declared with the draft, and the calendar one declares the break it swallowed: name the break as the skeleton has it and the event that covers it, beside the known exclusions, so the user can see why the skeleton and the blocks disagree rather than reading it as a transcription error. An undeclared block over a break is the same defect as a hand-tidied edge. Entries post as start/end times and Harvest derives the hours — the duration shown is informational, so don't distort boundaries to make durations land on neat quarters; the only hard rule is no entry under 0.25 hr. If an outer edge doesn't match a script span (and isn't one of the two exceptions above, declared), that's a transcription bug, not a judgment call. **These guards read the blocks you drafted.** A block the *user* dictated — a calendar question they accepted at review, a window they asked you to bill that no script span supports — is their instruction and not your transcription of a script span: none of the three shrinks it, splits it or deletes it, the blocks you drafted tile up to its edges as they would around any other block, and it is declared with the draft like the exceptions. A drafted block they merely approved is not this: it has a script span, and these guards still own it. That holds on a loop back from Step 8 as much as on the first pass.
2. **No block ends after `work_end`.** Shrink any that do, with two left alone — a block the user dictated (guard 1), and guard 1's one named exception: a corroborated calendar block ends where its **`block` span** does, and a meeting the machine watched past the AFK watcher's last input is the case that exception exists for. **Do not shrink it to its `evidence` either** — the evidence is the window seen, the `block` span is what the wrapper concluded from it, and the two differ on the listening-only meeting by exactly the minutes this exception exists to bill. Declare it with the draft, naming the break, and never extend any *other* block to reach it.
3. **Logged blocks must cover the active spans.** Pass *every entry Step 9 will post* — post-shrink, non-billable ones (standups, internal admin, machine setup) and calendar blocks included, since they account for active time just as billable ones do. A calendar block is an entry like any other here: passed as its `block` span, and the break inside it needs no special handling, because a break is not an active stretch and the check does not ask about it. A stretch you are *excluding* is declared with the draft as a known exclusion and never passed here: feeding it to `--cover` makes the guard report clean while the under-billing it exists to catch goes unnoticed.
   ```
   python scripts/afk_blocks.py <date> --cover "08:30-09:00,09:30-12:30,13:45-17:06"
   ```
   Every reported `UNCOVERED` stretch (≥15 min active, not in a break) must be billed or explicitly listed as a known exclusion (personal browsing per `.context.md`, or a documented thin-block drop) — never silently absent.

**Calendar questions** — every uncorroborated event still unanswered, set apart from the blocks and labelled as not drafted and not billed unless the user says so. Each one gives the event's time range, its name, who it was with, that no meeting window was seen, and asks whether to bill it.

None is a block (Step 3), so none is among the blocks, in the block counts, or in anything passed to guard 3. They are not 🔸 either — a 🔸 is a drafted block.

- **Batch-accept covers the drafted blocks and nothing else** — each calendar question takes its own answer, a word each.
- **A yes makes it a block over the event's span**, classified like any other (Steps 4 and 5) and declared with the draft naming the event and the user's answer. It may sit anywhere they say they were: outside the active spans (a client site before the laptop opened), across a break (a client lunch), or past `work_end`. The guards do not touch it (guard 1). It **replaces what it covers rather than doubling it**, exactly as a corroborated block does (Step 3): a yes to a 15:00–15:30 call inside a drafted 13:30–17:00 stretch splits that stretch into 13:30–15:00, the call, and 15:30–17:00 — never a fourth entry over the top. `--cover` reads both drafts as covered, so this rule is the only check on it. The 0.25 hr minimum still holds: an event shorter than that folds into a same-client neighbour or goes back to the user, never posts as a sliver. Then it is an entry like any other: Step 8 lists it and passes it to `--cover`.
- **A no, or no answer, leaves it unbilled** — out of the draft, out of `--cover`, out of Step 9. Ask once.

**Show the AFK skeleton with the draft** so the user can sanity-check boundaries at a glance: the work span, each break, the active minutes, the hours billed, and how much active time the blocks leave unaccounted.

**Then ask for the review.** The question says how many blocks were drafted for the date, how many are high confidence and how many are 🔸, and how many calendar question(s) are pending — with the reminder that batch-accept doesn't cover those. It offers two ways on: walk through the 🔸 ones, or batch-accept and edit after. Leave the calendar clause out when there are none.

Wait for the answer; edit per the user's input.

## Step 8: the confirmation gate

First self-check every line of the proposal:

- [ ] `--cover` run and clean (no unexplained UNCOVERED) — pass **every entry Step 9 will post, non-billable ones and calendar blocks included**; a stretch you're excluding is declared with the draft, never fed to `--cover` to make it look covered. It cannot see a *double*-billed stretch: two blocks over one meeting read as covered, so Step 3's "replaces what it covers" is the only check on that
- [ ] Skeleton still current — if the day was still in progress when you read it, or the session has since crossed midnight, re-run `afk_blocks.py <date>` before posting. An open day's `work_end` advances and late spans appear, which moves both the final block's end and the coverage denominator
- [ ] No block past `work_end`; no block crossing a script break — except a calendar block, which may do both and is declared with the draft: a corroborated one over its `block` span (Step 6 guards 1 and 2), or one the user accepted at review, which the guards leave alone as their instruction (Step 6 guard 1)
- [ ] Every `project_id`/`task_id` came from `python scripts/provider/bin/timesheet-provider lookup`; billable flag checked
- [ ] Work kind = the block's dominant activity per the rubric, and the task name came from `.context.md` § "Work kinds" or from the tasks `lookup` lists for this project — never from memory; `.context.md` overrides applied
- [ ] Every Harvest note passes the client-readability test (Non-negotiables below)
- [ ] All 🔸 blocks resolved with the user, and every calendar question put to them — an accepted one is an entry on this list; a no or a silence is not one and is not posted
- [ ] `.context.md` exclusions applied (personal browsing, recurring internal items)
- [ ] **The date isn't already billed** — re-confirm Step 1's Harvest check still holds. Every other line above compares the proposal against ActivityWatch; this line is the checklist's comparison against Harvest, and the cost of skipping it is double-billing a client

Then put the posting question: how many time entries this will create, and for each one its hours, client, project and task, with `[Support]` where it applies, and its note exactly as it will post. When the skeleton's header read `derived from this machine`, add the zone — times in that zone, derived from this machine, and that setting `TIMESHEET_TIMEZONE` pins it. Close on the three answers: yes, no, or edit a named block.

The zone is there only on a derived zone — a configured zone is the user's own choice and is not announced. It is the last moment the user sees the zone before anything reaches the provider, and a wrong one dates every entry above it.

**An explicit "yes" or equivalent is what earns `--confirm` in Step 9** — without that flag the posting scripts write nothing and print what they would have posted instead, so anything short of a yes simply leaves it off. Edits loop back to Step 6, then through Step 6b again.

## Step 9: posting

For each confirmed block, serially (so the user can interrupt):

```
python scripts/provider/bin/timesheet-provider post --project-id <project_id> --task-id <task_id> --date <YYYY-MM-DD> --start <HH:MM> --end <HH:MM> --notes '<notes>'
```

- **Append ` --confirm` to that command once Step 8 has the user's yes.** The template leaves it off on purpose: without the flag the script prints `WOULD POST <body>` and exits 0 having created nothing, so a command copied straight from here bills nothing until someone adds it deliberately. A run that comes back `WOULD POST` has *not* billed the block — re-run it with the flag, and never record it as posted.
- Times: 24-hour, zero-padded (`16:05`) and dates `YYYY-MM-DD` only — `4:05pm`, `20260812` and a `*` second-pass marker are usage errors (exit 2), so strip the marker before the call. A flag is given once.
- **Single-quote the notes** — money amounts (`$5k`), backticks, and shell-shaped substrings get mangled otherwise.
- Success prints `OK <entry_id>` — capture it for Step 10. Failure prints `ERR <message>` on stderr and exits 2–5 (2 usage, 3 missing configuration, 4 the provider refused, 5 unreachable) — stop and surface, don't retry silently. After a 5 the entry may or may not exist: `list` before retrying.
- The entry is always sent as a fixed interval — a start and an end, never a running timer and never a bare duration; that is the contract's promise for every account mode, and a caller never has to ask for it.
- **On the day the clocks go back, a block worked straight through the change is refused** — Harvest bills the difference between the two clock times, which is short by however long the clocks repeated (an hour in most zones; the `ERR` states it). It names the two entries to post in its place and why they are not the overlap they look like; post both, and do not close the overlap. `patch` refuses the same entry, judged on what the patch would leave behind — so correcting a block onto that morning meets the same message, and the fix is the same two entries: patch the one you have to the first, post the second. `references/output-format.md` §Conventions has the cases the refusal cannot see, where a block touches the repeated span rather than straddling it.
- Report each post as it lands — its hours, project code and task — so the user can follow along and interrupt.

Fix a wrong entry with `python scripts/provider/bin/timesheet-provider patch <entry_id> [--start HH:MM] [--end HH:MM] [--notes "..."] [--project-id ID] [--task-id ID] [--date YYYY-MM-DD] [--confirm]` (≥1 field flag; same OK/ERR convention, same gate — it previews as `WOULD PATCH <entry_id> <body>` until `--confirm` is added; there is no duration flag — change a duration with `--start` and `--end`). A patch overwrites a line the user already approved, so it needs its own yes; Step 8's covers the entries it listed, not a later correction to one.

**Block belongs to brand-new client work with no project yet** → follow `references/new-client-work.md` (create the backend work item, post other blocks now, bill the deferred one when the synced project appears).

## Step 10: wrap-up

Summarise: total hours posted, blocks deferred/skipped, and whether more days are outstanding — but **don't name the next date here**; Step 12 does that after the reset ask. Save the entry ids to `Timesheets/<date>_harvest_responses.json`: `{"entries": [{"id": 2933345845, "project_code": "NWC-001", "hours": 0.25, "notes": "..."}], ...}`. **Record every calendar question the user answered there too — the yeses and the noes, with the answer** — an accepted event's block has no activity evidence behind it, and this file is where Step 1's already-covered branch looks for a ruling before proposing to change a day. A recorded no is a ruling like any other: it binds, and that date does not ask again.

## Step 11: improvements

A run frequently reveals a fact the skill or `.context.md` doesn't know (a new signal you had to guess, a convention that turned out wrong, an offline watcher). Collect them and present at the end:

- *This user's* clients/colleagues/signals/preferences → propose for `.context.md` (most additions).
- The *workflow itself* (a generic heuristic, data-source change, API quirk) → propose for `SKILL.md`/`references/`.
- The *skill is wrong* — a script returns a wrong answer, a guard didn't fire, an instruction is wrong for every user → `references/reporting-issues.md` if the user installed this skill, `docs/CONTRIBUTING.md` (in the repository, not in an installed copy) if they maintain it.

Show the exact diff, one fact per ask. Example: "The XrmToolBox signal isn't in `.context.md`; I guessed Ledger Learning. Add `XrmToolBox connecting to env X → Ledger Learning` under Ledger Learning?"

**A yes to a diff that adds or changes a client's **Category terms** rebuilds the category rules in the same breath** — write the file, then run `scripts/category_rules.py --from-context`, which reads every client's terms from that file, and report what it wrote in a line. Don't ask a second time: the rules are a derived copy of the terms they just approved, and a second approval for the derived thing is a question with no other answer. It is also what keeps the promise the staleness check at Step 2 makes — a term added today matches tomorrow, without anybody remembering to re-run setup. A refusal from the gate, or a `suspect` line, is reported here rather than at Step 2, since this is where it happened.

**`.context.md` size budget — check after every edit to it.** `(Get-Item Timesheets/.context.md).Length` must stay under **14,000 bytes** (override via `## Preferences`). The budget exists to keep Prerequisite 1's whole-file read affordable on every run — that is what it is *for*, so a file over budget gets trimmed, never partially read. Over budget → compact in the same session, in this order: (1) move any *generic* rule that crept in into this skill's references — that's skill drift, not a user fact; (2) delete facts proven wrong or superseded (finished workstreams, retired clients, one-off work-item examples older than a few months); (3) shorten confirmed-example parentheticals to the date stamp. If getting under budget would drop a live user fact, ask the user which to drop — never silently delete.

## Step 12: one date per session

**Finish one date per session and stop.** The date is done when nothing is left to post (Step 9 posted it, the user declined at Step 8, or the run had no Harvest write in scope), Step 10 has wrapped up, and every Step 11 proposal is written or declined — a reset mid-follow-up loses those proposals. A date the user deliberately scoped to part of the day is **not** done: the rest of it is unfinished business on this date, not a next day.

**Then, only if days remain**, ask for the reset *before* naming the next date. Say where this date landed, that days are outstanding, and ask the user to run `/clear` before the next one — this date's blocks, client mix and resolved ambiguities read like evidence for the next date.

- **Today-so-far counts as a next date.** Starting a fresh date is what triggers the ask, whether that date is an old gap or the rest of today. Step 1's "today is in progress, not a reason to ask" governs *date selection* on a no-date run; it does not exempt today from the reset.
- **Say to re-invoke the skill, in the same breath as `/clear`.** It is not model-invocable, so a bare "do Thursday" in the cleared session runs with none of these guards. Dropping this makes the reset actively worse than not resetting.
- **All caught up → say nothing about resetting.**
- **You may not know whether days remain.** Only a no-date run builds the gap list (Step 1); on "do Friday" you never swept for one. Ask the user — don't run an unrequested sweep to find out. A month-wide answer is the `reconcile` skill's, and it is the user's to invoke.
- **Won't clear → ask for `/compact`.** Weaker: it carries this date's conclusions forward, but it drops the raw timelines, screenshot reads and catalog dumps.
- **Declines both → do as they ask**, and say once that the next date will be read against this one's conclusions.
- You cannot run either; the user does. **Don't open the next date in the same turn as the ask** — "yes, do Thursday next" is not permission to skip it. Proceed once they have reset, or declined both.

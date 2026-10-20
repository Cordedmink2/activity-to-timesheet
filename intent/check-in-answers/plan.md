# Plan: Check-in answers bill work the computer couldn't see

**Spec:** [spec.md](spec.md) (spec gate t_a6ab865c returned CHANGES REQUIRED at 9b2c56d; this plan is written against 9b2c56d and is re-checked when atlas amends the spec, see Risks)  **Intent:** [intent.md](intent.md) (Accepted 2026-10-20)
**Author:** dev  **Date:** 2026-10-20  **Status:** Draft (plan gate: t_57316f22)

## Approach

An answer is context. It is never a block, never a change to the skeleton, and never billed without its own yes. The whole feature is one new read-only script, two small instruction edits and one new setup step. Nothing existing is rewired, which is also what keeps US-5 true.

**1. Reading (`skills/daily/scripts/checkin_answers.py`, new).** One day, one host. It lists buckets once with `aw_client.get("/buckets/")`, picks the AFK bucket with `pick_bucket` (as `afk_blocks.discover_buckets` does), reads that bucket's host suffix, and picks `aw-watcher-ask-away` (check-in, type `afktask`, one event over the away gap, `data.message`) and `aw-watcher-ask` (point events, `data.success`, answer under a title key) for the same host. It fetches events with `aw_client.fetch_events`, clips each to the day in the configured zone (E5), and prints JSON in the skeleton's clock notation. It writes nothing and reads only the local activity source. It is not imported by `afk_blocks.py`, `activity_timeline.py` or `calendar_day.py`, so the skeleton cannot depend on it (US-1/AC-4).

**2. Classifying.** The script is given the user's terms in a small JSON file (`--terms <file>`): the clients' category terms in the same `{client, terms}` shape Step 2 already builds for `category_rules.py --candidates`, plus the user's exclusions from `.context.md`. The agent already holds both after the whole-file read of `.context.md`, so no new parsing of that file ships. Each answer gets one class, in this order:

1. **personal**: empty, dismissed or unanswered (`success` false), a match in the shipped generic list, or a match in the user's exclusions. Stretch stays a break, no question (US-2/AC-1, US-3/AC-3).
2. **work, one client**: exactly one client's terms appear. The question names that client.
3. **work, several clients** (E4): the question names all of them and asks which, or whether to split.
4. **work, no client** ("meeting"): the question asks whether it was work and for which client (US-2/AC-2).

Personal wins over a client term, by decision D6.

**3. Placing.** The script gets breaks from `afk_blocks.day_skeleton` (read only). A check-in answer that overlaps a break is clipped to the break and becomes a **question**. One that does not (the gap was shorter than the break threshold, E3), or that is an `aw-watcher-ask` answer, becomes a **hint** with its words and time. A question whose clipped span overlaps an uncorroborated calendar event carries that event, so one question cites both (E1). One inside a corroborated calendar block is context only (E2). These two inputs come from an optional `--calendar <file>` holding `calendar_day.py` output.

**4. Asking, and rulings (daily skill).** The question path copies the calendar question path (ADR-0008, SKILL.md Steps 3, 6 and 10), it does not add a parallel one: listed under the table; own answer per question; "accept all" does not cover it; never drafted and never passed to `--cover`; a yes becomes a user-dictated block that the three Step 6 guards leave alone, declared with the draft; a no or a silence leaves it unbilled. Step 10 records both the yes and the no, with the answer, in `Timesheets/<date>_harvest_responses.json` under a `checkin_questions` list keyed by the clipped start and end. `--rulings <that file>` makes the script mark a question already ruled (`ruled: yes|no`) and leave it out of `questions`, so a re-run, and the already-covered branch of Step 1, do not ask twice (E6, US-1/AC-3). Hints go to Step 5's ladder as one more rung, below a work-item reference and below the activity evidence, and never settle a block the evidence settled confidently (US-3/AC-2).

**5. Instructions stay small.** New detail lives in `skills/daily/references/check-in-answers.md`. SKILL.md gains only a pointer in Step 2, one bullet each in Steps 6 and 10, and a Files entry. A net-added-words budget is tested. The #57 ceiling (5,000 words) is a hard stop: this build starts only after PR #106 is on main (D9).

**6. Setup (`skills/setup`).** One new step offers each watcher in plain words: what it asks and when. It installs, makes it survive a reboot, and verifies it by finding its bucket for this host with an event (`checkin_answers.py --probe`). A decline is written as `Check-in watcher: off` or `Ask watcher: off` under `## Preferences` in `.context.md`; the daily run skips the script on `off`, and neither the setup finish nor the daily run reports a failure (US-4/AC-3). Two AFK buckets from different hosts (the condition that makes the check-in watcher refuse to start) are detected by `--diagnose` and explained; nothing is deleted unless the user says yes to that named bucket, after an export is saved (US-4/AC-4). Detail is in `skills/setup/references/checkin-watchers.md`.

**7. Windows persistence.** `skills/daily/scripts/setup_checkin_watcher.ps1` registers one per-user scheduled task that starts the watcher at logon, `RunLevel Limited`, interactive logon type (the dialog needs the user's desktop), no admin, `-DryRun` and `-Force` as in `setup_screenshot_pipeline.ps1`. It restarts on failure. Uninstall is `Unregister-ScheduledTask` plus the package's own uninstall, stated in the reference. Linux and macOS persistence is settled by the spike (T1): `aw-qt` autostart if the watcher is discovered there, otherwise a documented per-user unit.

**8. Real-Windows proof.** No Windows host is reachable. CI `windows-latest` runs the `.ps1` in `-DryRun` and the script's tests. US-4/AC-2 and the intent's S1 walk are recorded PENDING-REAL-WINDOWS with exact steps (T14), never passed.

## Research and spike (autonomous prerequisites)

Problem and context: established in the intent, `/home/ubuntu/artefacts/activitywatch-three-repos-research.md` (core.py 179 lines; gaps 5 to 10 minutes old; `find_afk_bucket` fails on a stale old-host AFK bucket; PyPI 0.0.6 is from 2023 and older than the org's changes) and the existing code (`pick_bucket`, the calendar question path). Load-bearing assumptions that research does not prove, so T1 tests them before the build commits to D1, D2 and D4:

- **H1:** PyPI 0.0.6 writes `aw-watcher-ask-away_<host>` with `data.message` over the away gap, and is good enough for outcome 1 on Windows. *Control:* the org default branch at a recorded commit. *Expected observation:* same bucket name and event shape; any behavioural difference listed. *Exit:* if 0.0.6 differs in a way that breaks outcome 1 (name, shape, no Windows start), choose a pinned reviewed commit of the ActivityWatch-org repository instead; never PR #5.
- **H2:** `aw-qt` discovers an `aw-watcher-*` executable on PATH on Linux and macOS, so persistence needs nothing new there.
- **H3:** the watcher has no host or bucket option, so the stale-bucket fix cannot be a flag. *Exit:* if it has one, D4's fix becomes that flag and no deletion is ever proposed.
- **H4:** `aw-watcher-ask` default schedule and config format allow "two prompts a day, weekdays" (D14).

*Safe boundary:* scratch venv and scratch clone under the task scratch directory; a throwaway `aw-server` on a non-default port with its own data directory for any live run; never the user's, this host's, or any real activity source. *Evidence:* commands and observed output recorded in `tasks.md` T1. *Cleanup:* the venv, clone, throwaway server process and its data directory are named in T1 and removed by T18 after the observations are copied into the PR; nothing outside the scratch directory is created.

## Decisions

- D1: Install source is PyPI `aw-watcher-ask-away` 0.0.6 pinned by version, by `pipx`; fall back to a pinned commit of the ActivityWatch-org repository only if T1 shows 0.0.6 fails H1. Alternatives: the org repo head (unpinned, changes under users); PR #5 (Reserved, never planned). Why: a published, versioned artifact installs on Windows without git and is reproducible. The release gate for "newer is better" is a person's review, not ours.
- D2: Windows persistence is a per-user scheduled task at logon, limited run level, interactive logon, no admin. Alternatives: per-user Startup-folder shortcut (works, no restart-on-failure, hard to check by script); service (needs admin, Reserved). Why: matches the existing screenshot task, can be dry-run and checked in CI, and `Get-ScheduledTask` verifies it.
- D3: One new read-only script, not an extension of `afk_blocks.py`. Alternatives: a flag on `afk_blocks.py` (risks the skeleton and the byte-identical bar). Why: the skeleton cannot change by construction.
- D4: Host scope comes from the picked AFK bucket's suffix. The `aw-watcher-ask` prefix must exclude `aw-watcher-ask-away*` before `pick_bucket` runs, because `pick_bucket` matches by `startswith` and `aw-watcher-ask` is a prefix of `aw-watcher-ask-away`. Why: otherwise the ask reader reads the check-in bucket. Stale-bucket fix is settled by H3.
- D5: Terms and exclusions arrive in a file the agent writes from `.context.md`; the script never reads `.context.md`. Alternative: parse `.context.md` in the script (a new parser of a free-form user file). Why: smallest, deterministic, and reuses the shape Step 2 already builds.
- D6: A personal match always wins, even beside a client term ("lunch with <client>" stays a break). Alternative: turn it into a question. Why: the intent's first priority is never to bill what the user didn't confirm and never to mistake personal time for work. The cost (a client lunch missed) is recoverable because the user can still dictate a block at review.
- D7: Only `aw-watcher-checkin` answers over a break create questions. `aw-watcher-ask` answers are hints only (a point in time cannot explain a gap, per the research).
- D8: Rulings reuse `Timesheets/<date>_harvest_responses.json`, the file Step 1 already reads before proposing changes. Alternative: a new file. Why: one record, one read, binds on re-run.
- D9: New instruction detail goes to a reference file; SKILL.md net growth is tested; this build starts after PR #106 (#57) is on main, so the 5,000-word ceiling can be checked rather than assumed.
- D10: "Off" is a line under `## Preferences` in `.context.md`, where the other overridable preferences already live. Alternative: an environment setting (needs the declared-configuration machinery for a fact about one person).
- D11: The shipped personal list is small, generic and ships no user words: lunch, break, coffee, tea, school run, school pickup, gym, commute, errand, personal, nap, doctor, dentist, kids. Words match whole, case-insensitive. The user's exclusions extend it. Alternative: a long list (more wrong breaks, more surprises).
- D12: US-4/AC-2 and the intent's S1 walk are PENDING-REAL-WINDOWS until a person runs the steps in T14.
- D13: Docs: new ADR-0009 (check-in answers are questions, extends ADR-0008, because a plain reading of "an answer says what I did" invites drafting a block); decision-log entry; `CONTEXT.md` glossary term **Check-in question** (the vocabulary test reads it); CONTRIBUTING instrument row; CHANGELOG in-progress section per AGENTS.md § Releasing, no tag, no version bump.
- D14: In-work prompt cadence (outcome 2): check-in itself prompts only on return from away; periodic prompts come from `aw-watcher-ask` on Linux and macOS, defaulted to two weekday prompts (schedule confirmed in T1/H4), user-adjustable, never offered on Windows. Block-end prompts need PR #5 and are out of scope (E9).
- D15: Verification runs from the build worktree's own venv, `.venv/bin/python -B -m pytest -q -p no:cacheprovider tests skills/daily/tests` and `.venv/bin/pyright`, not the shared checkout (spec gate F1). The two `auto` probes in the spec use bare `python` and `pyright`; if atlas pins them, the plan follows.

## Coverage

| Criterion | Plan section | Tasks |
|---|---|---|
| US-1/AC-1 | Approach 1 to 3, 5 | T2, T3, T4, T5, T10, T14 |
| US-1/AC-2 | Approach 4 | T5, T10, T12 |
| US-1/AC-3 | Approach 4 | T6, T10 |
| US-1/AC-4 | Approach 1, D3 | T7 |
| US-2/AC-1 | Approach 2, D6, D11 | T4 |
| US-2/AC-2 | Approach 2 | T4 |
| US-3/AC-1 | Approach 3, 4 | T3, T5, T10 |
| US-3/AC-2 | Approach 3, 4 | T5, T7, T10 |
| US-3/AC-3 | Approach 2, D7 | T3, T4 |
| US-4/AC-1 | Approach 6, D14 | T11, T13, T15 |
| US-4/AC-2 | Approach 6, 7, 8, D2 | T1, T9, T11, T14 |
| US-4/AC-3 | Approach 6, D10 | T8, T13, T15 |
| US-4/AC-4 | Approach 6, D4 | T1, T9, T13 |
| US-5/AC-1 | Approach 1, D3 | T2, T7, T8 |
| US-5/AC-2 | Approach 8 | T16 |
| US-5/AC-3 | Approach 8 | T16 |
| US-6/AC-1 | Approach 1, D5, D11 | T6, T12, T16 |
| US-6/AC-2 | Approach 1, 4 | T6, T12 |

Edge cases: E1 T5; E2 T5; E3 T5; E4 T4; E5 T3; E6 T6; E7 T3; E8 T8; E9 documented in T13 and not built. Spec gate finding F2 (a `usage` criterion for S1) is covered by D12 and T14; its criterion ID is added to the table when atlas adds it.

## Risks and rollback

- Spec not yet approved or merged (gate returned CHANGES REQUIRED; PR #107 open). → The plan is anchored to 9b2c56d. If atlas changes an AC, T-IDs that serve it are re-pointed before the build starts, and the plan is re-gated. Build does not start until the spec is gated and merged.
- `SKILL.md` and `setup/SKILL.md` are hotspots (#57/PR #106, #48, the guided-setup build). → Build starts from fresh origin/main after #106; edits are small and additive; flag a hotspot comment if the diff collides.
- A bucket-name collision (D4) reads the wrong watcher. → Fixture with both buckets present, T3.
- PyPI 0.0.6 turns out stale on Windows. → H1 exit: pinned org commit. If neither works without PR #5, brief atlas with an amendment (outcome 1 alone is the accepted fallback).
- A personal answer drafted as work. → Cannot happen: only a user's yes makes a block (T5, T10), and the classifier errs to break (D6). Test cases cover each personal fixture.
- Real-Windows proof is absent. → Recorded as PENDING-REAL-WINDOWS (T14); never claimed passed.
- Rollback: every change is additive. Revert the PR; with the script gone, nothing in the skeleton, timeline or calendar wrapper changes (T7 proves they never read it). For a user: Unregister-ScheduledTask and pipx uninstall (text in the reference, T13); remove the `Check-in watcher:` line from `.context.md` (inert without the script). No data migration; `checkin_questions` in an old `harvest_responses.json` is ignored by older versions.

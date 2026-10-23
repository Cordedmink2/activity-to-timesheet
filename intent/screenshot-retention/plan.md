# Plan: Screenshots don't pile up after they've done their job

**Spec:** [spec.md](spec.md) (re-gated and merged at 41b5670 via PR #107; this plan is re-pointed to 41b5670)  **Intent:** [intent.md](intent.md) (Accepted 2026-10-20)
**Author:** dev  **Date:** 2026-10-20  **Status:** Draft (plan gate: t_f84cee3e)

## Approach

The clean-up is one new script that decides and deletes, two short instruction additions that offer it, and one setting. Nothing that reads the capture folders changes, which is what keeps US-3 and US-5 true.

**1. The script (`skills/daily/scripts/screenshot_cleanup.py`, new, stdlib only).** Two commands, in the provider's own shape (preview, then `--confirm`):

- `plan --through <date> [--flagged <file>] [--exclude <date>,...] [--floor <hours>] [--month-reconciled <YYYY-MM>,...]` is read-only. It resolves the capture folder with the same `setting("TIMESHEET_SCREENSHOTS_DIR")` call `screenshot_capture.py --where` uses, lists the dated folders, asks the timesheet provider what is billed by running the contract command `timesheet-provider list <first> <last> --by-day` (it names no provider and reads no credential), and prints JSON: the eligible dates, the image count and bytes, the date range, and the days kept with one reason each. If the provider read fails or the setting is off, it prints one plain line, `NO-OFFER <reason>`, and exits 0 with nothing eligible (US-2/AC-2, US-4/AC-2).
- `apply --dates <list> --confirm` deletes. Without `--confirm` it prints what it would delete and deletes nothing. It re-runs the same eligibility check itself instead of trusting the date list it was given, so a stale or hand-edited list cannot delete a kept day.

**2. Eligibility, per day.** A dated folder is eligible only when all of these hold (decided from the provider's rows and the run's records, never assumed):

1. It is a real date, strictly before today, and not in `--exclude` (the day this run drafted). B3, US-2/AC-4.
2. The provider shows it **fully billed**: at least one entry and billed hours at or above the short-day floor. The floor is the reconcile skill's own (`## Preferences` in `.context.md`, default 6.0 hrs); the agent passes it with `--floor`. A day with no entries, or under the floor, is not billed and is kept. This is also how a weekend or evening folder with captures and no billed work is kept (see Risks, spec E3).
3. It is not in `--flagged`: dates a reconcile run in this session returned as Gap, Short or Unclear, plus any date whose `Timesheets/<date>_harvest_responses.json` records a deferred or skipped block. The agent builds `--flagged` after the first `plan` pass by reading each candidate day's whole file and extracting the dates with deferred/skipped blocks, then reruns `plan --flagged <file>`; keys in these files are ad hoc, so do not assume a fixed key schema. Unexplained and user-named leave days are also kept, because they are not billed.
4. Then one of two routes: **age**, the date is more than the configured days old (default 35); or **month**, its month is named in `--month-reconciled`. A month counts as reconciled only when a reconcile run in this session covered the whole month (it ended before today) and ended with no Gap, Short or Unclear date left in it. The agent passes the month only in that case.

**3. The day index stays: dated folders are left in place, with a one-line marker.** After deleting a day's images, the script writes `.cleaned` in that folder (the date and the count removed). Not a manifest, because the three readers already take the index from folder names alone, and a folder that stays is the index unchanged. Verified against `main` at 5f78de3:

- `reconcile` Step 1 lists `Get-ChildItem -Directory | Select Name`: names only, so an empty folder counts.
- The daily no-date picker (SKILL.md Step 1) uses the same listing.
- `afk_blocks.captures()` runs `os.listdir` on the day's folder and matches `HH-MM-SS[_mN].png` only, so `.cleaned` is invisible to it. I ran it on a real empty folder: it answers `{'count': 0, 'last': None}`.

That last result is the one reader this breaks, quietly. A cleaned day that the user later reopens (already-covered branch, or a correction) would print `captures: none for this date <- capture task dead all day`, which is false and sends the user to fix a task that is working. So `captures()` gains one rule: a `.cleaned` marker in the folder gives a `cleaned` result and the skeleton line reads `captures: removed by clean-up on <date>`. This changes the output only for a cleaned day; every other day is byte-identical, pinned by the existing goldens (US-5). It does not change the break, work start or end, active spans or ratios.

**4. Confinement.** Deletion code never builds a path from user text. Per candidate it requires: the capture root resolved with `realpath` (the root itself may be a link the user made on purpose; it is resolved once, then never again); the dated folder is a real directory (`lstat`, not a symlink) whose name is `YYYY-MM-DD` and whose `realpath` parent is the root; each file is a regular file (`lstat`, not a symlink) whose name matches the capture pattern (`HH-MM-SS[_mN].png`, the one `afk_blocks.py` already uses) and whose `realpath` parent is the dated folder. Anything else is skipped and reported by name; it is never followed and never removed. A symlinked dated folder is refused whole. `capture.log` and every other file are untouched. A file that cannot be removed (locked by a viewer, E5) is reported; the folder keeps no marker until all its images are gone, so the day is offered again later with what is left. The script never reads or writes outside the root, makes no network call, and never touches `daily_exports/`.

**5. Offering (instructions).** New detail goes to `skills/daily/references/screenshot-cleanup.md`, loaded only at the end of a run. SKILL.md gains one bullet in Step 12 (after posting and the reset ask) and `reconcile/SKILL.md` gains one paragraph after Step 4 (after the worklist), each naming the reference. A net-added-words test caps the growth, and this build starts after PR #106 is on main so the 5,000-word ceiling is checked, not assumed (SKILL.md is 11,806 words at 5f78de3 before #106).

The reference says, in order: run `plan` only at the end of the run (never during the day read, so no day's evidence moves mid-run); say nothing if it prints `NO-OFFER` apart from the one-line reason when the user has asked for the offer and could not get it (provider down); otherwise make **one** offer naming the date range, the day count and the freed size, plus the sentence "I always ask before deleting screenshots, and I only offer for days that are fully billed." A yes runs `apply --confirm`. A no, or no answer, deletes nothing and is not repeated in that run (US-1/AC-2). The user may exclude named days from the offer. After deletion it prints the result from the script and says any file that could not be removed. On macOS and Linux the capture folder does not exist, so nothing is offered (E4).

**6. Setting.** One key, `TIMESHEET_SCREENSHOT_CLEANUP`, read through `skill_config.setting()`: blank means offer after 35 days; a whole number of days sets the age; `off` (any case) never offers. Any other value is treated as off and the one-line reason says so, because a typo must never mean "delete sooner". It is declared where the other settings are: `.claude-plugin/plugin.json` `userConfig` (optional string), `skills/daily/.env.example`, the README settings table, the `OPTIONAL` set in `tests/test_plugin_config.py`, and `SETTING_KEYS` in `skills/daily/tests/support.py`. Setup (`skills/setup` Step 5, the screenshot step) gets the one plain sentence of US-4/AC-1: "Screenshots stay until the days are billed and 35 days old, or until you reconcile the month, and I always ask before I delete any."

**7. Other capture folders and no eligible days.** Resolve the configured capture folder once and clean only that resolved folder. Before offering, check whether the other of the default capture folder and configured folder contains dated folders; if so, tell the user those captures are untouched and name the folder, without reading or deleting its contents. If the plan has zero eligible days, make no clean-up offer.

**8. Build order.** Lands after the web-watchers build and after PR #106 (#57), from a fresh `origin/main`, because all three touch `skills/daily/SKILL.md` and `skills/setup/SKILL.md`. The script, the afk_blocks rule and the setting do not touch those files and can start first.

## Research and spike (autonomous prerequisites)

Problem and context: set by the intent; code read at 5f78de3 (`screenshot_capture.py`, `afk_blocks.captures`, reconcile Step 1, daily Step 1, the provider contract `list --by-day`, the dispatcher test's `FakeAdapter`).

Load-bearing assumptions the plan would otherwise only confirm by itself, so T1 tests them before T2 onward commits to D1 and D2:

- **H1:** every reader of the date index takes it from folder names alone, so an empty folder with a marker leaves the index unchanged. *Control:* the 60-day fixture before and after. *Expected observation:* identical `Get-ChildItem -Directory`-equivalent name lists and identical no-date picker candidates; `afk_blocks.captures()` returns zero ticks with no error. *Exit:* if any reader changes, decide a manifest (D1 reversed) and brief atlas. Already supported by a read of the code and by one run on an empty folder; T1 repeats it on the fixture and, in CI, on `windows-latest`.
- **H2:** an empty folder reads as "capture task dead all day" in the skeleton. *Observed true* on one run (above); T1 records the exact line. This is why D3 exists.
- **H3:** deleting a `.png` while its folder stays works on Windows, and a file held open fails without stopping the run. *Control:* `windows-latest` runs the locked-file test. *Exit:* if the lock cannot be simulated there, E5 is stated as not verified by CI for Atlas's ship decision; it is not marked passed.

*Safe boundary:* `tmp_path` fixtures only; no real capture folder, no real provider, no network. *Cleanup:* every fixture lives in pytest's `tmp_path` and is removed by pytest; nothing else is created, no service or job is added. The script adds no scheduled task: it runs only when a skill runs it, so it has no maintenance owner beyond the repository's tests.

## Decisions

- D1: The index is the dated folder left in place with a `.cleaned` marker, not a manifest. Alternatives: a manifest file (a new second index every reader would have to learn, and a place for the two to disagree); an empty folder with no marker (works for the readers, but cannot tell a cleaned day from a dead task, H2). Why: smallest thing that leaves reconcile and the day picker byte-for-byte unchanged (US-3).
- D2: The script asks the provider through the contract command, not an adapter, and decides "fully billed" as at least one entry and hours at or above the user's short-day floor; this is exactly reconcile's `Billed` verdict, with the floor named as `--floor` (default 6.0 hrs from `## Preferences` in `.context.md`). A day with no entries or under the floor is not billed. Alternatives: compare billed hours to the day's active minutes from `afk_blocks.py` (more exact, but needs the activity source up and a per-day read of hundreds of days; reconcile defers that to Step 3); accept any entry as billed (loses unbilled work on a half-billed day, which B1 forbids). Why: one cheap read and the same verdict reconcile uses.
- D3: `afk_blocks.captures()` reports a cleaned day as cleaned. Alternative: leave it (a false "capture task dead" alarm on reopened days). This is the one reader change, and it is the only output that differs, on cleaned days only.
- D4: The script re-derives eligibility on `apply`; the date list in the offer is never trusted. Alternative: apply what `plan` printed (a stale list could delete a day billed late-edited to partly billed, E1).
- D5: One setting key with `off` as a value, not two keys (days, on/off). Alternative: the `enabled()` helper (blank means off, which would make clean-up opt-in and contradict the default); two keys (two things to document and keep in step). Invalid value means off.
- D6: The offer text, not state, carries the "I always ask first" sentence. Alternative: a per-user "told" flag in `.context.md` (state to keep for one sentence). Why: existing users hear it the first time because every offer carries it (US-4/AC-1).
- D7: "Month reconciled" is a fact of the current run (a whole-month reconcile that left no Gap, Short or Unclear), passed in by the agent; the script stores no reconcile verdict. Alternative: record the verdict in the workspace (new state, can go stale). Why: nothing to expire; no run, no month route.
- D8: Only files matching the capture pattern are deleted. Alternative: any `*.png` or any file in a dated folder (would take a user's own image dropped there; the spec says images only and the capture pattern is stricter and already tested).
- D9: Weekend, evening and no-entry days are kept (see Risks, E3). Alternative: delete them as "no billable work", which contradicts B1 and D1 and replaces provider evidence with a guess.
- D10: Verification is the build worktree's own venv, `.venv/bin/python -m pytest -q tests skills/daily/tests` and `.venv/bin/pyright`, plus `Checks` green on the PR head (windows-latest and ubuntu-latest). The spec's two `auto` probes now read the latest completed `Checks` conclusion on main, so at the build gate the run's `headSha` must contain the build.
- D12: E3 days (a weekend or evening folder with captures and no provider entries) are never eligible (Atlas ruled, spec E3 amended). D9 already does this. The US-2/AC-1 bar includes the E3 fixture and a dry run: `plan` is the dry run and lists exactly the eligible days before anything is deleted (T4, T11).
- D13: Tests go beyond pytest and pyright: a retention dry run on a dated screenshot tree (T11), a locked-file and confirmed-delete run on `windows-latest` in the shared Windows end-to-end job (D14, T12).
- D14: Windows proof is the shared end-to-end job on `windows-latest` in `.github/workflows/checks.yml` (Atlas, 2026-10-20), created by the earlier builds. This build extends it with named steps and creates no second job. Steps: build a dated tree, run `screenshot_cleanup.py plan` (dry run) and assert the eligible list, then `apply --confirm` and assert the images are gone, the folders and `.cleaned` markers stay, the day picker and reconcile's index are unchanged, and a file held open is reported and does not stop the run.
- D11: Docs: CHANGELOG in-progress section per AGENTS.md § Releasing (check `git tag --list` first; no tag, no version bump); a decision-log entry for D1, D2 and D9; a CONTRIBUTING row listing every copy of the sentence and of the setting (README, `.env.example`, `plugin.json`, the reference); an ADR only if T1 reverses D1. The CONTRIBUTING evaluation for the skill changes is run by the build.

## Coverage

| Criterion | Plan section | Tasks |
|---|---|---|
| US-1/AC-1 | Approach 1, 2, 5 | T4, T7, T9 |
| US-1/AC-2 | Approach 5 | T7, T9 |
| US-2/AC-1 | Approach 2 (eligibility rules 2 and 3), D2, D9, D12 | T3, T4, T5, T11 |
| US-2/AC-2 | Approach 1, 2 | T4, T6 |
| US-2/AC-3 | Approach 4, D8 | T5 |
| US-2/AC-4 | Approach 2 (rule 1), 5 | T3, T7 |
| US-3/AC-1 | Approach 3, D1, D14 | T1, T5, T8, T12 |
| US-3/AC-2 | Approach 3, D1 | T1, T8 |
| US-4/AC-1 | Approach 5, 6, D6 | T7, T9 |
| US-4/AC-2 | Approach 6, D5 | T2, T6, T9 |
| US-5/AC-1 | Approach 7, D10 | T8, T10 |
| US-5/AC-2 | Approach 7, D10 | T10 |

## Risks and rollback

- **Spec E3 (resolved, F3).** Spec E3 now says such days are never eligible, matching D9 and intent B1/D1 (D12). Old risk text follows for the record: if atlas had kept deletion, the plan would have stopped and gone back to atlas, which is a spec change, not a build choice.
- **Spec probes (resolved, F1).** They now read `Checks` on main; D10 is the method.
- **Provider says billed, the user disagrees.** The offer lists the range and count and the user can say no or exclude a day. Nothing is deleted without the yes, and the confirmed list is re-checked (D4).
- **A wrong `--floor` can classify a partially billed day as billed.** Refuse a missing, zero or negative floor; never silently substitute one. Default floor is 6.0 only when explicitly supplied by reconcile's documented default.
- **Marker or folder deleted by the user.** The index then loses that date, the same as today. Nothing recreates it.
- **Locked file or an antivirus quarantine (E5).** The remaining images and no marker mean the day is offered again; the index is the folder, so it is not lost.
- **Hotspots:** `skills/daily/SKILL.md` and `skills/setup/SKILL.md`. The plan adds one bullet to each and puts the detail in a reference. If the 5,000-word ceiling fails at build time, the bullet moves into the Step 12 reference rather than growing SKILL.md.
- **Rollback.** All changes are additive and in git: revert the build PR. Deleted images cannot be restored by a revert, so the only guard is the confirmed offer; that is why `apply` has no mode that deletes without `--confirm`, and why this plan never runs a deletion outside a test fixture. Setting `TIMESHEET_SCREENSHOT_CLEANUP=off` stops all offers on an installed copy.

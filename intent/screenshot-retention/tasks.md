# Tasks: Screenshots don't pile up after they've done their job

**Plan:** [plan.md](plan.md)  **Spec:** [spec.md](spec.md)
Check: `python3 /home/ubuntu/.hermes/sdd-skills/sdd-plan-and-tasks/scripts/trace_check.py intent/screenshot-retention` must print OK.

Rules for every task: tests first (write the failing test, run it, see it fail, then build). Fixtures use only synthetic dates and the synthetic names the existing tests use, in pytest's `tmp_path`; no test touches a real capture folder or a real provider, and nothing is deleted outside a fixture. Run from the worktree's own venv: `.venv/bin/python -m pytest -q tests skills/daily/tests` and `.venv/bin/pyright`, and finish with `Checks` green on the PR head. Build starts from a fresh `origin/main` (spec merged at 41b5670), after the web-watchers build and after PR #106 (#57) is on main. Evidence is filled in at build time and is the command with its observed output, never a claim. Judged criteria carry the reviewer's probe from the spec; the fixture below is the one it runs on.

**The 60-day fixture** (built once in `skills/daily/tests/`, used by T1, T4, T5, T8): pin `today` through an injectable clock/test seam to 2026-03-02; use folders for fixed dates 2026-01-01 through 2026-03-01 inclusive (60 days), with `HH-MM-SS_mN.png` files in each (two monitors, small byte content), plus `capture.log` in the root. January is a whole reconciled month, and the provider supplies entries at or above the floor on billed January days. At least some January days must be under 36 days old relative to the pinned date, so the month route is what makes those days eligible. Later days include: unbilled days, a partly billed day (under the floor), a reconcile-flagged day, a day billed but newer than the age, a weekend folder with captures and no entries, today's folder and the drafted day's folder. Add a billed-at-or-above-floor candidate day whose whole `Timesheets/<date>_harvest_responses.json` contains a deferred block; after deriving `--flagged`, it remains ineligible.

### T1 — Spike: confirm the index readers and the empty-folder reading (H1 to H3)
serves: D1, US-3/AC-1, US-3/AC-2
- Test first: write H1 to H3 and the expected observation for each (plan, "Research and spike") in this card's Evidence before running anything. Build the 60-day fixture. Record, before any deletion code exists: the sorted dated-folder names a directory listing gives, the no-date day picker's candidate days for the fixture (as SKILL.md Step 1 builds them from that listing and the fake provider's `list --by-day`), and `afk_blocks.captures()` for a full, an empty and an absent folder.
- Do: run the same three by hand against a copy of the fixture with one month's images removed and the folders left, and against one with a `.cleaned` marker only. Compare. Run the locked-file case on `windows-latest` (a file held open; the delete must fail for that file only). If any reader differs, stop and send atlas the evidence (D1 reversed means a manifest, an ADR and a spec re-check).
- Evidence: <commands and observed output: identical name lists, identical picker candidates, captures() results, the shared Windows CI job's result, or the plain statement that CI could not drive it>

### T2 — The setting: parse, default, off
serves: US-4/AC-2, D5
- Test first: table-driven test of the parser for `TIMESHEET_SCREENSHOT_CLEANUP` through `skill_config.setting()`: blank gives 35; `45` gives 45; `OFF`, `off` give off; `0`, `-3`, `abc`, `3.5` give off with a one-line reason; the `.env` line beats the environment, as for every key (`test_config_seam.py` style). A test fails if the key is missing from `plugin.json` `userConfig`, `skills/daily/.env.example`, the README settings table, `OPTIONAL` in `tests/test_plugin_config.py` or `SETTING_KEYS` in `support.py`.
- Do: add the key to those five places in plain words (what it does, the default 35, `off`), and the parser in the script's module.
- Evidence: <pytest output for the new tests; the five files' diff>

### T3 — Eligibility core: dates, today, the drafted day, fully billed, flagged
serves: US-2/AC-1, US-2/AC-4, D2, D9, D12
- `--through <date>` is an inclusive upper bound on candidate dates, defaulting to today; it never makes today or a future date eligible. The caller passes it explicitly when bounding a run's candidate set.
- Test first: table-driven test of one pure function `eligible(days, billed, today, floor, age, flagged, exclude, reconciled_months, through)` with the fake provider's rows. Expect kept, each with one reason: today; the excluded (drafted) day; a future date; an unbilled day; a day under the floor; a day with one entry and zero hours; a weekend folder with captures and no entries (D9); a flagged day, even when older than the age and in a reconciled month; a non-date folder name. Expect eligible: a fully billed day older than the age; a fully billed day in a reconciled month though newer than the age; the boundary days 35 and 36 old. A property loop over a generated set asserts an unbilled day is never eligible on any combination, and candidate dates after `through` are excluded.
- Do: implement the pure function and its reason strings.
- Evidence: <pytest output>

### T4 — `plan`: the offer data from the provider, on the 60-day fixture
serves: US-1/AC-1, US-2/AC-1, US-2/AC-2
- Test first: with the fake provider selected by `TIMESHEET_PROVIDER` (as `test_provider_dispatcher.py`'s `FakeAdapter`), run `screenshot_cleanup.py plan` on the fixture. Expect JSON naming the first month's date range, its day count and bytes, every kept day with its reason, and no file removed (listing equal before and after). Include a January candidate billed at or above the floor whose whole `Timesheets/<date>_harvest_responses.json` has a deferred block; after the agent reads that day's full file, builds `--flagged`, and reruns `plan`, assert its images remain after confirmed cleanup (T11 repeats this protection). With no eligible days, assert the plan produces no offer. With the fake provider raising `Unreachable` and again `Misconfigured`: one line `NO-OFFER <reason>`, exit 0, nothing eligible. A test asserts the script imports no adapter and names no credential (the existing boundary tests must stay green).
- Do: implement `plan`: resolve the root with `setting()`, list dated folders, read billed days with the contract command (`list <first> <last> --by-day`), call the core from T3, sum the images and bytes.
- Evidence: <pytest output; the plan JSON for the fixture; the listing before and after>

### T5 — `apply` with confinement, the marker, and the hostile folder
serves: US-2/AC-1, US-2/AC-3, US-3/AC-1, D4, D8
- Test first: on the 60-day fixture, without `--confirm`, nothing is removed. With `--confirm`: exactly the eligible days' capture-pattern images are gone, every kept day's images remain, each cleaned folder still exists and holds only `.cleaned`. On a hostile fixture: `capture.log` in the root, a non-image file and a `.png` that does not match the capture pattern inside an eligible dated folder, a dated-folder symlink pointing at an outside directory holding images, a file-level symlink inside an eligible folder pointing outside, a folder named `..` and an absolute date argument. Expect: only matching regular files in real dated folders are removed; every symlink is refused and reported and its target untouched; a path argument is refused; the log and the non-image files are untouched. A stale `--dates` list including a day billed later to partly billed (E1, fake provider changed between `plan` and `apply`) is refused by the re-check. A file that cannot be removed (a mocked `OSError`; on Windows CI a held-open file) is reported and leaves no marker, and the rest of that day's files are still removed.
- Do: implement `apply` per plan Approach 4, re-deriving eligibility (D4), removing only pattern-matching regular files whose `realpath` parent is the dated folder, then writing `.cleaned`.
- Evidence: <pytest output; the hostile fixture listing before and after>

### T6 — Setting off, provider down: no offer, one reason
serves: US-2/AC-2, US-4/AC-2
- Test first: with the setting `off`, `plan` prints `NO-OFFER off` and does not call the provider (fake provider's call list empty); an invalid value prints the one-line reason naming the setting; the provider failing prints one line naming the class of failure (unreachable or missing configuration) and the next step in plain words; none of them exits non-zero or prints a traceback.
- Do: wire the setting and the failure mapping into `plan`; the text is Simplified Technical English.
- Evidence: <pytest output>

### T7 — Instructions: when and how it is offered
serves: US-1/AC-1, US-1/AC-2, US-2/AC-4, US-4/AC-1, D6
- Test first: instruction tests in the style of `tests/test_reconcile_skill.py` and `tests/test_daily_skill.py`: `skills/daily/references/screenshot-cleanup.md` exists and is named in SKILL.md Step 12 and in `reconcile/SKILL.md` after its worklist step; it says to run `plan` only at the end of a run and after posting or the worklist; it carries the exact sentence "I always ask before deleting screenshots, and I only offer for days that are fully billed."; it says a no, or no answer, is not repeated in the same run; it says to pass the drafted day with `--exclude` and a reconciled month only after a whole-month reconcile with no Gap, Short or Unclear left; and instructs the agent to read each candidate day's entire `Timesheets/<date>_harvest_responses.json`, because keys are ad hoc, build `--flagged` from deferred/skipped dates and rerun `plan`. The reference names no client and no user fact (`test_redaction`, `test_provider_neutrality`); net word growth of SKILL.md is under budget and the file is under #57 ceiling.
- Do: write the reference and the two short pointers. Run the CONTRIBUTING instruments and the fresh-agent evaluation it requires for a skill change.
- Evidence: <pytest output; word counts before and after; the evaluation result per CONTRIBUTING>

### T8 — The readers stay unchanged; a cleaned day is not "capture task dead"
serves: US-3/AC-1, US-3/AC-2, US-5/AC-1, D3
- Test first: on the pinned fixture, before and after confirmed clean-up, assert the three S1 outcomes together: January's images are gone; every January date remains in reconcile's index; and every unbilled day keeps all its images. Also assert byte-identical no-date picker candidates, `afk_blocks.captures()` for a cleaned folder returns a `cleaned` result, the skeleton line reads `captures: removed by clean-up on <date>`, and `capture task dead all day` is not printed for it. Assert every existing golden is byte-identical, and that a day with no folder still prints the existing dead-capture line.
- Do: add the `.cleaned` rule to `captures()` and to the skeleton line; no other output changes.
- Evidence: <pytest output: goldens green; index before/after identical; the skeleton lines>

### T9 — Setup sentence and user-facing documentation
serves: US-1/AC-1, US-4/AC-1, US-4/AC-2
- Test first: a setup-skill test in the style of `tests/test_setup_skill.py`: Step 5 carries the sentence "Screenshots stay until the days are billed and 35 days old, or until you reconcile the month, and I always ask before I delete any." and names the setting; a doc test that README, `.env.example` and `plugin.json` state the same default (35) and the `off` value; a test that the first-offer text carries the same "I always ask" sentence as T7. A CONTRIBUTING row names every copy of the sentence and the setting.
- Do: add the sentence to the setup step, the README row, and the CONTRIBUTING row; add the first-run note to the reference. Step 5 is a Windows-only step, so the sentence is said only there (E4).
- Evidence: <pytest output; the diff of the three docs>

### T10 — Full suite, release notes, decision log, and the clean-up of the work
serves: US-5/AC-1, US-5/AC-2, D10, D11
- Test first: from the build worktree's own venv run `.venv/bin/python -m pytest -q tests skills/daily/tests` and `.venv/bin/pyright | grep -E '^[0-9]+ errors?'` before any edit of this task, and record the baseline.
- Do: add the CHANGELOG entry to the in-progress section per AGENTS.md § Releasing (run `git tag --list` first; bump only if the newest heading is tagged, then stop; cut no release); add the decision-log entry for D1, D2 and D9 (and a note on spec E3 and its outcome); confirm no temporary artifact remains (fixtures live in `tmp_path`; the spike adds none). Push, wait for `Checks` (windows-latest, ubuntu-latest and the shared Windows job) green on the PR head and record its `headSha`. State in the PR what CI could not drive (an antivirus quarantine of a real capture) for Atlas's ship decision. Never mark it passed; no step for Connor.
- Evidence: <pytest and pyright output after; the `Checks` run URL and headSha; `git tag --list`; the CHANGELOG diff; the Windows steps and their status>

### T11 — Retention dry run on a dated screenshot tree, with the E3 and deferred-block fixtures
serves: US-2/AC-1, D12, D13
- Test first: on the pinned 60-day fixture extended with a weekend folder and an evening-only folder that hold captures and have no provider entries (E3), run `screenshot_cleanup.py plan` (the dry run) and assert it lists exactly the eligible days and names each E3 day with reason `no provider entries`; assert the tree listing is byte-identical before and after the dry run. Include a date billed at or above the floor with a deferred block recorded in the whole `Timesheets/<date>_harvest_responses.json`; after parsing that whole day's file and passing its date through `--flagged`, assert the date remains ineligible and every image survives confirmed cleanup. Then assert every E3 day, unbilled day, partly billed day and reconcile-flagged day keeps all its images. The fixture tree uses real dated-folder and capture file naming (`YYYY-MM-DD/HH-MM-SS_mN.png`) as the capture pipeline writes it, with the source file named in the test.
- Do: add E3 and deferred-block folders to the shared fixture builder and dry-run/confirmed-cleanup assertions.
- Evidence: <pytest output; dry-run listing; before and after tree listings>

### T12 — Other capture folder and zero eligible days
serves: US-2/AC-3, US-1/AC-1, E2
- Test first: with `TIMESHEET_SCREENSHOTS_DIR` configured to a fixture, assert only that resolved folder is eligible for cleanup. Put dated folders in the other of the default capture folder and configured folder; assert the user-facing result names that other folder and says its captures are untouched. If the resolved folder has zero eligible days, assert no offer is generated even when the other folder has dated captures.
- Do: implement the check and message without reading or deleting the other folder's contents; add the named folder and zero-eligible assertions to tests.
- Evidence: <pytest output; both fixture folder listings before and after>

### T13 — Extend the shared Windows end-to-end CI job: retention dry run, confirmed delete, locked file and junction
serves: US-3/AC-1, D14
- Test first: write the assertions first and see them fail without the feature. The job is the one on `windows-latest` in `.github/workflows/checks.yml` created by the earlier builds; extend it with new named steps. Do not create a second job; if it is not on main when this build starts, stop and `kanban_block(needs_input)` to atlas.
- Do: on the runner, build a dated tree on the real filesystem, run the dry run and assert the eligible list; run `apply --confirm` with one file held open (opened without share-delete) and assert that file is reported, the others are removed, the folder stays, and no marker is written for that day; release the file, re-run, assert the day is then cleaned and `.cleaned` exists; assert the day picker's candidate days and reconcile's index are the same as before. Create a Windows junction for a dated folder pointing outside the capture root; assert it is refused and reported and no outside image is touched (the realpath-parent check is expected to catch it).
- Not verified by CI, stated for Atlas's ship decision: an antivirus quarantine or a cloud-sync client holding a real capture. Never marked passed; no step for Connor.
- Evidence: <windows-latest run URL, head SHA, job output lines per assertion>

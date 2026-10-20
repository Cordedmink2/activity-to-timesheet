# Tasks: Check-in answers bill work the computer couldn't see

**Plan:** [plan.md](plan.md)  **Spec:** [spec.md](spec.md)
Check: `python3 /home/ubuntu/.hermes/sdd-skills/sdd-plan-and-tasks/scripts/trace_check.py intent/check-in-answers` must print OK.

Rules for every task: tests first (write the failing test, run it, see it fail, then build). Fixtures use only the synthetic names ACME / BETA / Ledger / Nimbus and `example.*` hosts, as `skills/daily/tests/scenarios.py` does. Run from the worktree's own venv: `.venv/bin/python -m pytest -q tests skills/daily/tests` and `.venv/bin/pyright`, and finish with `Checks` green on the PR head. Build starts from fresh origin/main (spec 41b5670 is merged) and after PR #106 (#57) is on main. Evidence is filled in at build time and is the command with its observed output, never a claim. A `check: usage` item is proven by the shared Windows end-to-end CI job (T14); what CI cannot drive is stated as not verified for Atlas's ship decision, never marked passed and never a step for Connor.

### T1 — Spike: confirm the watcher facts the build depends on (H1 to H4)
serves: D1, US-4/AC-2, US-4/AC-4
- Test first: write the hypotheses and the expected observation for each (plan, "Research and spike") in this card's Evidence before running anything. Run only in the scratch directory: a venv with `aw-watcher-ask-away==0.0.6`, a scratch clone of the ActivityWatch-org repo at a recorded commit, and a throwaway `aw-server` on a non-default port with its own data directory. Never touch a real activity source.
- Do: (H1) with a fake away gap, record the bucket name, event type and `data` shape from 0.0.6 and from the org commit; (H2) read `aw-qt` discovery in source; (H3) read the watcher's CLI and `find_afk_bucket` for any host or bucket option; (H4) read `aw-watcher-ask` schedule and config format. Choose D1's install source from H1. If neither passes H1 without PR #5, stop and brief atlas.
- Evidence: <commands, versions, commit SHAs and observed output; name of each scratch artifact>

### T2 — Pin today's outputs and add the reader's shell
serves: US-5/AC-1, US-1/AC-1
- Test first: a test that runs `afk_blocks.py`, `activity_timeline.py` and `calendar_day.py` over every existing scenario in `skills/daily/tests/scenarios.py` and compares to the checked-in goldens unchanged; a failing test that `checkin_answers.py` exists, exits non-zero with a plain `ERR` when the activity source is unreachable, and prints an empty result for a day with no check-in bucket.
- Do: add `skills/daily/scripts/checkin_answers.py` with `main()`, date and `--utc-offset` handling as the sibling scripts, and the unreachable refusal from `aw_client`. No classification yet. Register it in `support.bundled_scripts` the way the siblings are.
- Evidence: <pytest output: goldens byte-identical; new tests passing>

### T3 — Read the check-in and ask buckets for this host only, clipped to the day
serves: US-1/AC-1, US-3/AC-1, US-3/AC-3
- Test first: fixtures with (a) a check-in bucket and a matching AFK bucket, (b) buckets for two hosts (E7), (c) both `aw-watcher-ask-away_<host>` and `aw-watcher-ask_<host>` present (the prefix-collision case, D4), (d) a gap that crosses local midnight in `Pacific/Auckland` (E5), (e) an unanswered ask event with `success: false`. Assert only this host's events are read, the ask reader never returns a check-in event, the midnight event is clipped to the day, and the unanswered event is dropped.
- Do: implement host scope from the picked AFK bucket's suffix with `pick_bucket`, exclude `aw-watcher-ask-away` from the ask prefix, fetch with `aw_client.fetch_events`, clip in the configured zone.
- Evidence: <pytest output>

### T4 — Classify each answer: personal, one client, several clients, no client
serves: US-2/AC-1, US-2/AC-2, US-3/AC-3
- Test first: table-driven test of the classifier with the fixture answers "lunch", "school run", an exclusion term from a fixture terms file, an empty string, a dismissed prompt, "call with ACME", "call with ACME and BETA" (E4), "meeting", and "lunch with ACME" (D6: stays personal). Expect: personal for the first five and the last, one client, two clients, no client. Also assert no shipped word list contains a client name.
- Do: add the small generic personal list (D11) to the script, the `--terms <file>` input (D5), whole-word, case-insensitive matching, in the order in the plan.
- Evidence: <pytest output>

### T5 — Place each answer: question, hint or context only
serves: US-1/AC-1, US-1/AC-2, US-3/AC-1, US-3/AC-2
- Test first: fixture days for (a) a work answer over a break, which gives one question with start, end, verbatim words and client, with no entry in any block list; (b) an answer overlapping an uncorroborated calendar event, which gives one question citing both (E1); (c) an answer inside a corroborated calendar block, which gives context only and no question (E2); (d) an answer whose gap is shorter than the break threshold, which gives a hint and no question (E3); (e) an ask answer over a break, which gives a hint only (D7); (f) an answer naming client B over a stretch confidently attributed to A, which leaves A and adds at most a note to ask about it. Assert the JSON has separate `questions` and `hints` lists and that nothing is ever emitted as a block.
- Do: take breaks from `afk_blocks.day_skeleton` (read only), accept `--calendar <file>`, clip and place per the plan. Output in the skeleton's clock notation.
- Evidence: <pytest output>

### T6 — Rulings bind on re-run
serves: US-1/AC-3, US-6/AC-1, US-6/AC-2
- Test first: given a `harvest_responses.json` whose `checkin_questions` records a yes and a no for two stretches, a re-run lists neither as open (E6) and shows them as ruled; a changed answer text for the same clipped span is still ruled; a file with no `checkin_questions`, or from an older version, is read without error; the script never writes the file or any other file.
- Do: add `--rulings <file>`, key by clipped start and end, mark `ruled: yes|no`. Read only.
- Evidence: <pytest output, including a check that the working directory is unchanged after a run>

### T7 — The skeleton cannot move
serves: US-1/AC-4, US-3/AC-2, US-5/AC-1
- Test first: for a scenario day, build the fake server once with the check-in and ask buckets and once without; assert `afk_blocks.py` and `activity_timeline.py` output is byte-identical (including the `captures:` line, which does not depend on check-in data). Add a module-boundary test that none of those scripts, nor `calendar_day.py`, imports `checkin_answers`.
- Do: no production change expected; if the test fails, the change that broke it is the bug. Add the boundary entry to `test_module_boundaries.py`.
- Evidence: <pytest output>

### T8 — No watcher, nothing recorded, or "off": today's behaviour
serves: US-5/AC-1, US-4/AC-3
- Test first: with the buckets absent, present but empty (E8), or the terms file marking the watcher off, the script prints an empty result and a plain note, exits 0, and the existing goldens are unchanged. A test reads the shipped instructions for the check-in step and fails if "off" is not treated as a settled choice (no failure wording, no re-ask).
- Do: the "off" handling in the script's output contract (`status: off|absent|empty|ok`) and the instruction wording in T10 and T13.
- Evidence: <pytest output>

### T9 — Probe and diagnose modes for setup
serves: US-4/AC-2, US-4/AC-4
- Test first: `--probe` returns found/not-found for this host's bucket with its newest event time; `--diagnose` over a bucket list with two AFK buckets from different hosts returns the named condition, which buckets, which is the stale one by `last_updated`, and the candidate fixes, and over a single-host list returns clean. Assert neither mode deletes or posts anything (the fake server records zero DELETE or POST calls).
- Do: add both modes. The fix text follows H3: a flag if one exists, otherwise export-then-delete of the named stale bucket, only on the user's explicit yes naming it.
- Evidence: <pytest output; recorded request log from the fake server>

### T10 — Daily instructions: the check-in question path
serves: US-1/AC-1, US-1/AC-2, US-1/AC-3, US-3/AC-1, US-3/AC-2, D9
- Test first: `tests/test_daily_skill.py` additions: the vocabulary check reads **Check-in question** from `CONTEXT.md`; Step 2 names the script and the three statuses; Step 6 says a check-in question is not a block, is not passed to `--cover`, and is not covered by batch-accept; Step 10 says both yes and no are recorded under `checkin_questions`; the reference file exists and is linked in Files; SKILL.md word count rises by no more than the budget set in D9 and stays under 5,000 words. Then run the fresh-agent evaluation CONTRIBUTING.md requires, before and after, on a fixture day with a work answer, and record the result.
- Do: write `skills/daily/references/check-in-answers.md` (how to build `--terms`, `--calendar`, `--rulings`; how to phrase the question; the yes path through Steps 3, 4, 5, 6, 8, 9; the hint rung in Step 5), and the minimal pointers in SKILL.md and `disambiguation.md`.
- Evidence: <word counts before and after; pytest output; fresh-agent evaluation transcript path>

### T11 — Windows persistence at logon, no admin
serves: US-4/AC-1, US-4/AC-2, D2
- Test first: a test that runs `setup_checkin_watcher.ps1 -DryRun` (skipped where no PowerShell) and asserts it prints a task with logon trigger, `RunLevel Limited`, interactive logon type, restart on failure, the pinned package version from T1, and no `-RunLevel Highest`; a test that the script contains no admin-only call. CI `windows-latest` runs it.
- Do: add `skills/daily/scripts/setup_checkin_watcher.ps1` modelled on `setup_screenshot_pipeline.ps1` (`-DryRun`, `-Force`, `-PythonExe`); install by pipx at the pinned version; register the task; print how to check and remove it. Linux and macOS: the persistence found in T1/H2 is written into the reference, not scripted.
- Evidence: <dry-run output; windows-latest CI run URL>

### T12 — Answers stay on the machine and out of bug reports
serves: US-1/AC-2, US-6/AC-1, US-6/AC-2
- Test first: `tests/test_provider_neutrality.py` and `tests/test_redaction.py` pass over the new files and fixtures; a new test that no shipped file other than fixtures contains a host name or an answer string; a test that `reporting-issues.md` lists check-in answers among what is redacted; a test that `checkin_answers.py` makes no network call to anything but the configured activity source and writes no file.
- Do: add the redaction line; keep fixtures synthetic.
- Evidence: <pytest output>

### T13 — Setup: offer, install, verify, decline as off, stale bucket
serves: US-4/AC-1, US-4/AC-3, US-4/AC-4
- Test first: `tests/test_setup_skill.py` additions: the new step offers each watcher with what it asks and when; the Windows path never recommends `aw-watcher-ask` or Zenity; the Linux and macOS path may offer it; a decline writes `off` and the finish reports "off, by your choice"; the step quotes `--diagnose`'s condition and refuses deletion without a named yes; the step's wording is Simplified Technical English (the setup skill's existing reading-level test, if present, otherwise sentence length and no jargon). Step numbering, "Done" and the compatibility line stay consistent.
- Do: add the setup step and `skills/setup/references/checkin-watchers.md` (install, verify, uninstall, PR #5 not used and why).
- Evidence: <pytest output>

### T14 — Shared Windows end-to-end CI job (creates it; later builds extend it)
serves: US-4/AC-2, US-1/AC-5, US-1/AC-1, D12, D16
- Test first: write the job's assertions before the steps, in `tests/` or the job's own script, and see them fail on a run without the feature. The job lives in `.github/workflows/checks.yml` as a job on `windows-latest` (D16).
- Do: (1) install `aw-server` and `aw-watcher-checkin` the way setup installs them (pinned from T1; `setup_checkin_watcher.ps1` run for real, task registered, checked with `Get-ScheduledTask`); (2) start `aw-server` on a non-default port with its own data directory; (3) inject the away answers \"call with ACME\" and \"lunch\" through the watcher's own bucket `aw-watcher-ask-away_<host>` as real `afktask` events with `data.message` (shape from T19), plus the AFK bucket; (4) run the daily scripts for that day and assert: the \"call with ACME\" stretch is a question quoting the answer, with no block and no entry before confirmation (test provider); a yes adds it for ACME; the \"lunch\" stretch stays a break; (5) uninstall and assert the day's output is as before. Keep the job's steps in separate, named functions so the web watchers, retention and consent builds add steps without editing this one.
- Not verified by CI, stated in the PR and in the decision log for Atlas's ship decision: a person answering the real dialog and focus behaviour. Never marked passed; no step for Connor.
- Evidence: <windows-latest CI run URL, head SHA, and the job's output lines for each assertion>

### T15 — Fresh-agent dry runs of the setup offer
serves: US-4/AC-1, US-4/AC-3
- Test first: write the two judged bars as a checklist before running: a Windows path and a Linux path each produce one plain offer per watcher with what it asks and when, the Windows path does not recommend `aw-watcher-ask` or a Zenity port; a run that declines both reports both as off at the finish and the next daily run raises nothing about them.
- Do: run a fresh agent with only the shipped instructions on each path against a fake activity source; save transcripts under the PR's evidence folder.
- Evidence: <transcript paths; checklist ticks with quoted lines>

### T16 — Whole-suite, type check and CI
serves: US-5/AC-2, US-5/AC-3, US-6/AC-1
- Test first: run both commands before the change on fresh origin/main, record the baseline counts.
- Do: from the worktree venv, `.venv/bin/python -B -m pytest -q -p no:cacheprovider tests skills/daily/tests` (exit 0, `N passed`), `.venv/bin/pyright` (`0 errors`), and the neutrality and redaction pair from US-6/AC-1. Push; wait for CI "Checks" on windows-latest and ubuntu-latest to finish green.
- Evidence: <command output; CI run URL and head SHA>

### T17 — Record the decision and keep the docs in step
serves: D13
- Test first: the vocabulary test fails until `CONTEXT.md` has **Check-in question**; the distribution tests list the new files.
- Do: ADR-0009 (an answer is a question, not a block; extends ADR-0008), `docs/skills/daily/decision-log.md` entry with the T1 observations, `CONTRIBUTING.md` instrument row, `README.md` mention, `CHANGELOG.md` in the in-progress section per AGENTS.md § Releasing (check `git tag --list` first; no tag, no version bump).
- Evidence: <git diff --stat; test output>

### T18 — Cleanup and maintenance
serves: D13, D1
- Test first: list every temporary artifact before removing it: the T1 scratch venv, the scratch clone, the throwaway `aw-server` process and its data directory, any fixture dumps.
- Do: after the T1 observations are copied into the decision log and the PR, stop the throwaway server and remove those scratch artifacts, nothing else; confirm with `ls` and `ps` that none remains. Name the owner of the pinned watcher version: dev, re-checked when atlas next reviews the plugin; a dated action to look at the upstream release state is added to the decision log. Health check the user can run: `checkin_answers.py --probe`.
- Evidence: <ls and ps output after removal; the dated action line>

### T19 — Real-shape fixtures and the E1 overlap fixture
serves: US-1/AC-1, US-1/AC-5, D17
- Test first: a test that the fixture builder emits a check-in bucket exactly as the watcher does: bucket id `aw-watcher-ask-away_<host>`, type `afktask`, one event over the away gap, `data` holding `message` (and any other key the pinned watcher writes). The expected shape is copied from the watcher's source at the version pinned in T1, and the source file and line are named in the test. A second test builds the E1 day: a stretch overlapping an uncorroborated calendar event, and asserts exactly one question citing both.
- Do: add the fixture builders to `skills/daily/tests/scenarios.py` (synthetic ACME / BETA names, `example.*` hosts) and use them in T3, T4, T5, T10 and T14.
- Evidence: <pytest output; the watcher source path and line the shape was copied from>

### T20 — Final verification on the PR head
serves: US-5/AC-2, US-5/AC-3, D15
- Test first: none new; this task is the gate command set.
- Do: from the build worktree's own venv run `.venv/bin/python -m pytest -q tests skills/daily/tests` and `.venv/bin/pyright`. Push. Wait for `Checks` (windows-latest, ubuntu-latest, and the Windows end-to-end job) to finish green on the PR head, and record its `headSha`.
- Evidence: <command output; `gh run` URL and headSha>

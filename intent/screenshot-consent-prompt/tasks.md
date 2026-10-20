# Tasks: Ask before each screenshot, so confidential screens aren't captured

**Plan:** [plan.md](plan.md)  **Spec:** [spec.md](spec.md)
Check: `python3 /home/ubuntu/.hermes/sdd-skills/sdd-plan-and-tasks/scripts/trace_check.py intent/screenshot-consent-prompt` must print OK.

Rules for every task: tests first (write the failing test, run it, see it fail, then build). Tests use fakes for `consent` and `grab` and `pytest`'s `tmp_path`; no test shows a dialog except the T1 smoke test, which uses a 1 ms timeout; no test touches a real capture folder. Run from the worktree's own venv: `.venv/bin/python -m pytest -q tests skills/daily/tests` and `.venv/bin/pyright`, and finish with `Checks` green on the PR head. Build starts from fresh `origin/main` (spec merged at 41b5670) and after the other four builds (this lands last, after retention). Read `docs/CONTRIBUTING.md` before the skill and reference edits. Evidence is filled in at build time and is the command with its observed output, never a claim.

### T1 — Spike: does MessageBoxTimeoutW time out and close on windows-latest? (H1, H2)
serves: D1, US-1/AC-3
- Test first: write H1 and H2 and the expected observation (plan, "Research and spike") in this card's Evidence before running anything. Add a `skipif(sys.platform != "win32")` test that calls the export with a 1 ms timeout and `MB_YESNO|MB_DEFBUTTON2`, and asserts the return is 32000 within 2 s.
- Do: run it in CI on `windows-latest`. If it passes, keep it. If it fails (wrong code, hang, no desktop, no export), delete it, record why, and either switch ask_consent to the documented `MessageBoxW`-in-a-thread fallback (D1, export missing or wrong code) or keep only the fake-based tests (no desktop). Either way what CI cannot drive is stated as not verified for Atlas's ship decision (T8).
- Evidence: <CI log line with the returned code and elapsed time, or the failure and the decision taken>

### T2 — The ask and the gate (seam), grab only after yes
serves: US-1/AC-1, US-1/AC-2, US-2/AC-1, D2, D7
- Test first: in `skills/daily/tests/test_screenshot_capture.py`, with a fake `consent` and a fake `grab` that records calls and fails the test if called before consent returned: (a) consent False gives zero `grab` calls and no files in a `tmp_path` dest; (b) consent True gives exactly one `grab(dest)` call and the result is what `take_screenshots` returns, so names and folder are today's; (c) `ask=False` never calls `consent` and calls `grab` once; (d) an exception inside the real `ask_consent` (patched `ctypes`) returns False; (e) the call passes default button No, a 20 s timeout and not `MB_DEFAULT_DESKTOP_ONLY`; (f) a timeout (32000) and No (7) return False, only 6 returns True.
- Do: add `ask_consent(timeout_s=20)` and `capture_once(dest, ask, consent=ask_consent, grab=take_screenshots)`; wire `__main__` to call `capture_once`.
- Evidence: <failing run, then passing run of the new tests; the ordering test shown failing when `grab` is moved before the consent call>

### T3 — Skip lines in the log, and the daily capture line
serves: US-2/AC-2, US-2/AC-3, US-1/AC-1, D4, D5
- Test first: (a) a skip writes exactly one line matching `^\[\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\] skipped$` to `capture.log` and nothing else anywhere under `dest`; a failed prompt writes `prompt-error`, not `skipped`; (b) `captures(date)` returns `skipped` counted for that date only; (c) `render_text` prints `none for this date, N skipped by you  <- not a dead task` for zero ticks with skips, appends `, N skipped by you` for ticks with skips, and the existing dead-task line for zero ticks with no skips; (d) every existing golden is byte-identical.
- Do: add the log lines in `capture_once`; extend `captures()` and the `captures:` line in `render_text`. Change nothing else in the skeleton.
- Evidence: <test output; existing `test_afk_blocks` goldens unchanged>

### T4 — Setup script switch, dry run unchanged when off
serves: US-3/AC-2, US-4/AC-2, D3
- Test first: a test (existing setup-script test style) that the `-DryRun` output without `-AskFirst` is identical to main's, byte for byte (capture the main output first and store as a fixture); with `-AskFirst` the arguments gain `--ask` and one extra `DRYRUN Prompt before capture` line; `-AskFirst` with `-IntervalSeconds 30` throws; and a hook test that `repaired_arguments` keeps a trailing `--ask`. Argument filtering: `resolve_screenshots_dir` still takes the directory when `--ask` is present, and an omitted (blank) directory plus `--ask` still falls through.
- Do: add the `-AskFirst` switch, the `--ask` argument, the dry-run line and the interval guard; filter `--ask` out of the positional list in `screenshot_capture.py`. No new package, task or service.
- Evidence: <dry-run outputs with and without the switch, diff showing the off case equals main's; test output>

### T5 — Setup offer and verify, daily and reconcile guidance
serves: US-3/AC-1, US-2/AC-3, D5
- Test first: a distribution/instrument check per `docs/CONTRIBUTING.md` that fails while Step 5 has no offer sentence, no per-mode verify, no E3 note, or while the `captures: none` guidance and reconcile's capture-less-days rule do not mention `skipped`. Run the `daily` SKILL.md word count: it must stay under 5,000.
- Do: edit setup Step 5 (offer in one plain sentence, record by `-AskFirst`, verify per mode, E3 note, interval note, add `--ask` to the pass-through arguments list); one pointer sentence in daily SKILL.md and the rule in `references/first-run.md`; the rule and the `Select-String ... skipped` command in `skills/reconcile/SKILL.md`. Run the fresh-agent evaluation CONTRIBUTING requires for a skill change.
- Evidence: <word count; evaluation outcome; diff of the shipped text>

### T6 — Fixture-day evidence for the two judged bars
serves: US-2/AC-2, US-2/AC-3, US-1/AC-2
- Test first: build two fixture days in `tmp_path`: day A with captures and no skips, day B identical activity with all captures skipped (log lines only, no dated folder). Write the expected result before running: breaks, work start/end, active spans and ratios equal between A and B, the `captures:` line differs and says `skipped by you`, never the dead-task wording.
- Do: run `afk_blocks.py` on both and diff the full text; run the daily/reconcile guidance on B as the reviewer's probe does.
- Evidence: <the diff showing only the `captures:` line differs; the all-skipped day's output>

### T7 — Size, scope and record
serves: US-4/AC-1, US-4/AC-2, US-4/AC-3, D6
- Test first: write the size budget before building (80 production lines) and the scope check: the diff adds no daemon, service, scheduled task or package.
- Do: after T2 to T5, measure `git diff --stat origin/main -- skills/ hooks/` excluding tests and docs; record in `docs/skills/daily/decision-log.md` the research finding (prompt kept, mechanism, the fail-closed rules, the follow-up suggestion of a pause control for atlas, no replacement); add to the in-progress CHANGELOG section (check `git tag --list`; no release, no tag, no version bump beyond AGENTS.md § Releasing). If production lines exceed 80, write why for the reviewer.
- Evidence: <diff stat; production line count; the decision-log and CHANGELOG diff>

### T8 — Real-Windows walk (PENDING-REAL-WINDOWS)
serves: US-1/AC-3, D10
- Test first: write the job assertions first and see them fail without the feature. The job is the one on `windows-latest` in `.github/workflows/checks.yml` created by the earlier builds; extend it with new named steps. Do not create a second job; if it is not on main when this build starts, stop and `kanban_block(needs_input)` to atlas.
- Do: on the runner (1) run the real capture script with the prompt on and the dialog auto-answered yes through the test hook (D10): assert one image per monitor with today's names in the dated folder; (2) auto-answered no: assert no file for that time and one `skipped` log line; (3) call the real `MessageBoxTimeoutW` with a short timeout and assert it returns 32000 and the script then skips (fail closed); (4) assert `capture.log` and the folder listing after each.
- Not verified by CI, stated in the PR and decision log for Atlas's ship decision: a person's click on the real dialog, whether it steals typing focus, and a locked-screen tick. Never marked passed; no step for Connor.
- Evidence: <windows-latest run URL, head SHA, job output lines per assertion>

### T9 — Suite and type check
serves: US-5/AC-1, US-5/AC-2, D11
- Test first: run both on a fresh `origin/main` worktree and record the baseline counts.
- Do: after the build, from the build worktree's own venv run `.venv/bin/python -m pytest -q tests skills/daily/tests` and `.venv/bin/pyright | grep -E '^[0-9]+ errors?'`; push; confirm `Checks` (windows-latest, ubuntu-latest and the shared Windows job) green on the PR head and record its `headSha`.
- Evidence: <both outputs and the CI run link>

### T10 — Consent paths with the dialog mocked: yes, no, timeout, dialog failure
serves: US-1/AC-1, US-1/AC-2, D8, D9
- Test first: a table-driven test of `capture_once` with `ask_consent`'s `ctypes` call mocked to return each of: 6 (yes), 7 (no), 32000 (timeout), 2 (closed), an `OSError` and an `AttributeError` (missing export), and with the `MessageBoxW`-in-a-thread fallback mocked to hang past the timeout. Assert: only yes writes images (same names and folder as an unprompted capture); every other outcome writes no file, no temp file and one log line with the time and `skipped` or `prompt-error` only; `grab` never runs before the answer; the default button is No and the timeout is at most 20 s and below the capture interval.
- Do: add the table to `skills/daily/tests/test_screenshot_capture.py`; the shipped code has no test-only branch (the D10 hook is a seam argument, not a shipped switch).
- Evidence: <pytest output; each row's outcome>

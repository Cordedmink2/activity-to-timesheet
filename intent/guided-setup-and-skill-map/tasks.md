# Tasks: Hands-off setup, and one front door for every non-daily job

**Plan:** [plan.md](plan.md)  **Spec:** [spec.md](spec.md)
Check: `python3 /home/ubuntu/.hermes/sdd-skills/sdd-plan-and-tasks/scripts/trace_check.py intent/guided-setup-and-skill-map` must print OK.
Verify from the repo root of the build worktree with its own venv: `.venv/bin/python -m pytest -q tests skills/daily/tests` and `.venv/bin/pyright`, and finish with `Checks` green on the PR head. Spec is merged at 41b5670.

### T1 — Preflight: fresh base, baselines, worktree
serves: US-6/AC-3, D9
- Test first: confirm #106 and t_b703f6a8 are merged (`git log origin/main`); create the worktree from fresh origin/main and the venv; run the suite and pyright green; record `wc -w skills/*/SKILL.md`; run the BEFORE arm of every T16 scenario against unmodified instructions (3 reps each).
- Do: nothing is changed in this task. Add a `hotspot: skills/setup/SKILL.md` comment on the build card.
- Evidence: word counts, green suite output, baseline transcripts' paths.

### T2 — Spike S1: what does setup still ask a person to do
serves: US-2/AC-1
- Test first: write the hypothesis and expected table (step, human-only? Y/N, source line) before reading step bodies.
- Do: read-only audit of steps 1-6 and "Before you start", plus the ActivityWatch and extension docs; classify; write the human-only list (browser-store Add click, admin prompt, consent page, credential in the harness store) and the agent-doable changes it finds. Exit when every step is classified or marked PENDING-REAL-WINDOWS. Installs nothing; touches no host.
- Evidence: the table committed in the human-only section's source and quoted in the PR.

### T3 — Guard: one home for category terms (red first)
serves: US-6/AC-1
- Test first: define "shipped" as the export set: all files included by `install/export_agent_skills.py` (`skills/*/SKILL.md` and their exported references/scripts); `skills/*/tests/` are excluded because they are not exported. Write `tests/test_one_home_for_terms.py` so it detects (1) definitions and (2) any instruction in shipped files to build candidates from Category terms. Permit only the explicit `--candidates` adopt-existing-rules route cited as such; do not exempt generic candidate-transcription wording. Plant a second definition and a generic transcription instruction separately in scratch exported trees; each must fail. Then run against actual export set after T4/T7/T22 (until then baseline failures are expected).
- Do: allow-list `references/context.md.example` and `scripts/category_rules.py`; detect term literals/lines/constants and generic instructions that transcribe context Category terms into candidates files across the export set, with only the explicit adopt-existing-rules exception.
- Evidence: red on both planted violations, then green on actual export set; record commands and outputs.

### T4 — `category_rules.py --from-context`
serves: US-6/AC-1, US-4/AC-1
- Test first: tests in `skills/daily/tests/test_category_rules.py`: client sections with free text; two clients in file order; a client with no terms line (left out, reported); a malformed line (refused, nothing written); `--adopts` mapping; compile result identical to the equivalent `--candidates` run; fingerprint unchanged.
- Do: add the parser and mode; update module docstring and "Files in this skill" flag list entry (daily SKILL.md entry must stay word-neutral).
- Evidence: failing then passing test output.

### T5 — `category_rules.py --data-days`
serves: US-3/AC-1, US-3/AC-2
- Test first: with `aw_server` fixtures: two workdays → `COLLECTING` with come-back date and nothing written; five → `READY`; weekend days and sub-30-min days not counted; `--min-days` honoured; AFK-only day not counted; stderr/exit code contract; a zero-client context file does not make `--status` loop.
- Do: implement; `say:` line in Simplified Technical English.
- Evidence: test output.

### T6 — Extract the install checks once
serves: US-6/AC-2, US-5/AC-1
- Test first: rewrite the structure tests in `tests/test_setup_skill.py` to assert the same facts (every step verified; every step has a failure answer; one copy of the elevated-registration fix; credential-printing bans) against `skills/setup/references/checks.md`, and add a test failing if any probe text appears in two shipped files. Watch them fail.
- Do: move each step's Verify and If-it-fails into `checks.md` in setup order, with ids; steps cite by id; move the package-manager table to `install-commands.md`. Rebase onto latest main first.
- Evidence: tests red then green; `wc -w` of setup before/after.

### T7 — Category stage: one reference, wait gate, no candidates by hand
serves: US-3/AC-1, US-6/AC-1, US-6/AC-2
- Test first: tests that setup's category step runs `--data-days` before `--inspect`, runs `--from-context` to write, and carries no `"terms":` example; `choosing-terms.md` is the only home of the term rules.
- Do: move step 4's interview and term-choosing into `choosing-terms.md`; step 4 becomes: check data (wait or go), choose terms, write the context file, run `--from-context`, verify. Keep the adopt-existing-rules route (`--candidates` with `adopts`) cited from one place.
- Evidence: tests; diff.

### T8 — Front door: menu, human-only list, routing
serves: US-1/AC-1, US-2/AC-1
- Test first: tests that the menu (five choices in plain words) precedes the first install step, each choice names a distinct target, the human-only list is present in one section and cited by others, and no step asks the user to type a command, regex or path.
- Do: add the menu and the human-only section to `setup/SKILL.md`; wire routing; keep the step count prose test true.
- Evidence: tests; opening-turn transcript (T16).

### T9 — Existing-machine path
serves: US-1/AC-3, US-7/AC-1
- Test first: test that the path reads each `checks.md` entry, skips passing ones, and requires a shown diff plus yes before changing any existing file (context file, rules).
- Do: write the path in `setup/SKILL.md` (cites `checks.md`; no copied probe text).
- Evidence: tests; brownfield transcript (T16).

### T10 — `onboard-client` skill
serves: US-4/AC-1, US-4/AC-2, US-1/AC-2
- Test first: `tests/test_onboard_client_skill.py` (shape, trigger phrase in description, sibling resolution on both install shapes, runs `--from-context` after a yes, reports unrecorded terms as "not yet seen" not failure, no copy of term rules or probes, under 5,000 words, no `disable-model-invocation`).
- Do: write `skills/onboard-client/SKILL.md`: ask decisions only; find facts via `--inspect`; show the context-file diff; on yes write file and run `--from-context` in the same step; cites `choosing-terms.md` and `checks.md`.
- Evidence: tests; transcripts (T16).

### T11 — `troubleshoot` skill
serves: US-5/AC-1, US-1/AC-2
- Test first: `tests/test_troubleshoot_skill.py`: runs `checks.md` entries in order, stops at the first failure, cites `endpoint-security.md` and `first-run.md` rather than copying, trigger phrase "stopped working", sibling resolution, under 5,000 words.
- Do: write `skills/troubleshoot/SKILL.md`.
- Evidence: tests; fixture transcript with a scheduled task pointing at a missing interpreter (T16).

### T12 — Feedback path (hand-over only)
serves: US-5/AC-2
- Test first: test that the menu's feedback choice cites `daily/references/reporting-issues.md`, the reference carries the menu entry, and the menu path has no `gh issue create` run by the agent; the redaction wording remains. Q1 is ruled (Atlas): hand-over only, never posts; do not re-ask.
- Do: edit the reference per D8: add the menu entry and the user-sends paragraph for that entry; leave Step 11's own route untouched.
- Evidence: tests; transcript showing no client name, host or answer from the fixture in the draft (T16).

### T13 — Daily relays the reminder without growing
serves: US-3/AC-2, US-6/AC-3
- Test first: T1 records the measured `skills/daily/SKILL.md` word count at the build start base; size test fails above that exact ceiling. Test Step 2 invoking `--data-days` only when status reports rules never written, relaying `say:` once maximum, no offer after a decline-for-good line under `## Preferences`, and no offer once managed rules exist. The test establishes that daily reads the decline line; rule-existence is supplied by `--status`.
- Do: add one bullet; cut the `BROKEN` and `STALE` prose to pointers at the references; keep every guard in `tests/test_daily_skill.py` green.
- Evidence: T1 baseline and before/after word count; each of the four reminder assertions red then green; pytest output.

### T14 — Size, export, install shape
serves: US-6/AC-3, US-6/AC-2
- Test first: `tests/test_skill_size.py` (each new skill under 5,000 words; daily no larger than the recorded ceiling); extend `NEEDS_A_SIBLING` with both new skills for `daily`/`billables-daily` and `setup`/`billables-setup`; check the export test lists both.
- Do: any fix the tests expose; run `install/export_agent_skills.py` into a scratch directory and read the prefixed directories.
- Evidence: test output; the exported directory listing.

### T15 — Credentials never touch chat, in every skill
serves: US-2/AC-3, D12
- Test first: add a guard test over every shipped setup path (all shipped skills, `checks.md`, the setup references) that fails if any path asks the user to type or paste a password, token or API key into chat, or if any check prints a credential. Prove the guard by a planted violation: add one (an instruction line asking the user to paste an API key into chat, and `echo $HARVEST_API_KEY` in a check), run the guard and see it fail naming the line, then remove the plant and see it pass. The planted-violation run is kept as a test that builds the violation in a temp copy, so the proof stays in the suite.
- Do: fix any new-skill text that trips the guard.
- Evidence: pytest output showing the red run on the plant and the green run after it; the guard test's name.

### T16 — Fresh-agent evaluation (after arm) and grading
serves: US-1/AC-1, US-1/AC-2, US-1/AC-3, US-3/AC-1, US-3/AC-2, US-4/AC-1, US-4/AC-2, US-5/AC-1, US-5/AC-2, US-7/AC-1
- Test first: scenarios and grading bars written from the spec before the after arm runs: opening turn on a clean machine; "I've got a new client"; "screenshots stopped working" (missing-interpreter fixture); brownfield fixture; two-day fixture then daily; past-threshold daily; feedback with the redaction fixture; unrecorded new client; a non-matching prompt that must not trigger the new skills. Neutral fixtures under `docs/skills/setup/eval/`.
- Do: three reps per arm, hand-graded; record in the decision log per CONTRIBUTING.
- Evidence: transcript paths and grades.

### T17 — Docs, ADR, changelog
serves: D7, US-6/AC-1
- Test first: `tests/test_distribution.py` and the vocabulary checks stay green after the edits.
- Do: ADR-0009 (names, one front door); amend ADR-0005's ownership line; update `docs/CONTRIBUTING.md` tree and the rules-with-more-than-one-copy rows (the new guard is an instrument); README pointer; CONTEXT.md terms if coined; add to the in-progress CHANGELOG section per AGENTS.md § Releasing (`git tag --list` first; no version bump unless the newest heading is tagged, then stop).
- Evidence: diff; tests.

### T18 — Whole-repo verification
serves: US-7/AC-2, US-7/AC-3
- Test first: n/a (verification).
- Do: from the build worktree's own venv run `.venv/bin/python -m pytest -q tests skills/daily/tests` and `.venv/bin/pyright | grep -E '^[0-9]+ errors?'`; push; wait for `Checks` (windows-latest, ubuntu-latest and the shared Windows end-to-end job) to finish green on the PR head and record its `headSha`.
- Evidence: pass counts, `0 errors`, CI run URLs.

### T19 — Extend the shared Windows end-to-end CI job
serves: US-2/AC-2, US-3/AC-3, D10
- Test first: write the job's assertions first and see them fail without the feature. The job is the one on `windows-latest` in `.github/workflows/checks.yml`; the check-in build creates it (serial order 1). Extend it with new named steps; do not create a second job. If it does not exist yet when this build starts, create it per D10 and let check-in extend it.
- Do: (1) US-2/AC-2: on the runner, run each install check from `skills/setup/references/checks.md` against a real `aw-server` and the watchers installed as setup installs them; assert every step prints its own verify line and the run ends in the stated "collecting data" state. (2) US-3/AC-3: inject a week of real-shape events through the real buckets (`aw-watcher-window_<host>` events with `app` and `title`, `aw-watcher-afk_<host>` events with `status`, copied from the watchers' source and named in the test), run the category stage after the threshold, and assert the candidate terms come from the injected titles and hosts and the written rules match each client in a synthetic context file (ACME / BETA).
- Not verified by CI, stated in the PR and decision log for Atlas's ship decision: the browser-store Add click, the admin prompt, the consent page, a real person's week of titles, the runner is an administrator, and a person's first-run experience. Never marked passed; no step for Connor.
- Evidence: <windows-latest run URL, head SHA, job output lines per assertion>

### T20 — Cleanup
serves: D9
- Test first: list what this task created (worktree, venv, eval scratch dirs, fixture servers); none is a scheduled task or service.
- Do: after the PR has the evidence, remove those scratch artefacts and the worktree (`git worktree remove`); leave the shared checkout untouched; record any leftover with owner and date.
- Evidence: `git worktree list` and a listing of the scratch directory.

### T21 — Real-shape fixtures for the category stage and setup checks
serves: US-2/AC-2, US-3/AC-3, D10
- Test first: tests that the fixture builders emit the exact bucket and event shape the real watchers write: bucket ids `aw-watcher-window_<host>` and `aw-watcher-afk_<host>`, event `data` keys, durations and timestamps, each copied from the watcher source at the pinned version, with the source file and line named in the test.
- Do: add the builders to the shared test scenarios (synthetic ACME / BETA, `example.*` hosts) and use them in T5, T7 and T19.
- Evidence: pytest output; source path and line for each shape.

### T22 — Daily rebuild routes use context as the only term home
serves: US-6/AC-1
- Test first: check the four named daily routes/references for no candidates-file transcription and for `--from-context`; verify the daily SKILL.md word count is unchanged from T1's start-base baseline. Plant a generic Category-terms-to-candidates instruction in the exported fixture and prove T3 fails; remove plant before commit.
- Do: update STALE rebuild instruction in `skills/daily/SKILL.md` and `references/day-reading.md`, and Step 10 yes-to-diff instruction in `skills/daily/SKILL.md` and `references/review-and-posting.md` to invoke `--from-context`; keep daily word-neutral by replacing equivalent text, not adding prose. Keep one explicitly cited adopt-existing-rules route on `--candidates`.
- Evidence: red-then-green tests; exact word count comparison; diff of all four locations.

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
- Test first: write `tests/test_one_home_for_terms.py` and plant a second definition in a scratch copy of a skill; the test must fail on it. Then confirm it passes on the real tree after T4/T7 (until then it fails on the existing candidates examples: that failure is the baseline).
- Do: allow-list `references/context.md.example` and `scripts/category_rules.py`; flag `"terms":` literal lists, filled `**Category terms**:` lines and term constants anywhere else shipped.
- Evidence: red on the plant, then green, both commands and outputs.

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
- Test first: size test fails if `daily/SKILL.md` words exceed the post-#106 baseline; test that Step 2 runs `--data-days` when `--status` reports rules never written and relays its `say:` line once.
- Do: add one bullet; cut the `BROKEN` and `STALE` prose to pointers at the references; keep every guard in `tests/test_daily_skill.py` green.
- Evidence: before/after word count; tests.

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
- Not verified by CI, stated in the PR and decision log for Atlas's ship decision: the browser-store Add click, the admin prompt, the consent page, and a person's first-run experience. Never marked passed; no step for Connor.
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
- Evidence: <pytest output; source path and line for each shape>

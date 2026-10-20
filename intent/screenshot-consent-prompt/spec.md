# Spec: Ask before each screenshot, so confidential screens aren't captured

**Intent:** [intent.md](intent.md), Accepted 2026-10-20 (Connor, in conversation with Hermes: "Yeah I think that sounds good"; recorded in the intent's Status line)
**Author:** atlas  **Date:** 2026-10-20  **Status:** Draft (spec re-gate pending)
**Serves:** O1–O3, S1–S4, B1–B4, A1 (inventory below)

## Summary
A user who opts in gets a small "is it safe to take a screenshot?" prompt before each capture. Yes
captures as today; no or an ignored prompt captures nothing at all. Users who do not opt in see no
change. It is built from existing operating-system or library features with as little code as possible.

## Intent inventory (labels used below)
- O1 opt-in prompt before a capture; a refused capture writes nothing at all.
- O2 yes is quick; an ignored prompt skips the capture.
- O3 opt-in; off means today's behaviour exactly.
- S1 prompt on: "no" leaves no file for that capture time; "yes" writes the normal capture; ignored writes no file.
- S2 prompt off: captures unchanged.
- S3 small amount of code; reviewer judges it maintainable.
- S4 `pytest` and `pyright` green.
- B1 KISS: existing OS/library features over new UI; no new long-running process if avoidable.
- B2 a refused capture leaves no image, even temporarily.
- B3 a refused or missing capture is not evidence of idle (refusal 5).
- B4 nothing leaves the machine.
- A1 researcher compares the per-capture prompt with lighter options (pause control, app-based skip);
  replacing the per-capture prompt is an amendment brief for Connor, not a silent swap.

## Problem → benefit → stories
Users avoid screenshots, or worry while they run, because a capture can record confidential client, HR
or personal material; today the choice is all or nothing. The benefit is that cautious users can keep
captures on and veto any one, so more users have screenshot evidence. US-1 is the prompt, US-2 the
protections, US-3 the opt-in and setup, US-4 simplicity, US-5 no regression.

## User stories

```yaml
id: US-1
as: a consultant who handles confidential material
want: a small prompt before each screenshot that I can answer yes or no, where ignoring it means no
so_that: a confidential screen is never captured without my say (O1, O2, S1)
criteria:
  - id: AC-1
    text: With the prompt on, answering no, or not answering before the prompt times out, writes no image file for that capture time. Serves O1, O2, S1.
    check: judged
    bar: Automated tests driving the capture with the dialog mocked to answer no, to time out, and to fail to open find no file for that time in the dated folder; the timeout is short enough not to overlap the next capture.
    probe: Reviewer reads the tests and their output; spot-checks on the real Windows machine at build gate.
    expect: {}
  - id: AC-2
    text: With the prompt on, answering yes writes the normal capture (one image per monitor, same names and folder as today). Serves O1, S1.
    check: judged
    bar: The yes path produces files identical in naming and location to an unprompted capture, pinned by a test.
    probe: Reviewer reads the test and its output.
    expect: {}
  - id: AC-3
    text: On a real Windows machine the prompt appears, is quick to answer with one click or key, does not steal typing focus in a way that sends keystrokes into it, and its yes/no/ignore outcomes match AC-1 and AC-2. Serves O2, S1.
    check: usage
    probe: Windows evidence from the windows-latest end-to-end CI job where it can drive the step, otherwise the Atlas logged ship decision plus post-release monitoring (a short session log with three prompts answered yes, no and ignored, and the dated folder listing).
    expect: {}
```

```yaml
id: US-2
as: a consultant relying on the prompt for confidentiality
want: a refusal to leave nothing behind and not to count against me
so_that: the prompt really protects me and does not make my timesheet worse (B2, B3, B4)
criteria:
  - id: AC-1
    text: The screen is not grabbed until after a yes; a no or timeout leaves no image in memory-backed temp files, the capture folder or anywhere else. Serves B2.
    check: judged
    bar: The code path grabs pixels only after the prompt returns yes, verified by reading the code and by a test that fails if the grab runs before consent.
    probe: Reviewer reads the capture code and the ordering test.
    expect: {}
  - id: AC-2
    text: The daily run treats a refused capture exactly as a missing one ("no screenshot"), never as idle, and the capture log records only that a capture was skipped, with no content. Serves B3, B4.
    check: judged
    bar: For a fixture day with skipped captures and the same day with captures, the skeleton's breaks, work start, work end, active spans and every active ratio are identical; only the captures line may differ (US-2/AC-3 requires it to). The log line names the time and "skipped" only.
    probe: Reviewer compares skeleton outputs and reads the log line.
    expect: {}
  - id: AC-3
    text: A day with many skipped captures is not reported by daily or reconcile as a dead capture task when the log shows the skips were the user's. Serves B3.
    check: judged
    bar: On a fixture day whose captures are all skipped, the run reports "captures skipped by you", not the dead-task maintenance finding.
    probe: Reviewer reads the daily run on the all-skipped fixture.
    expect: {}
```

```yaml
id: US-3
as: a consultant deciding whether to use screenshots
want: the prompt offered at setup as a choice, explained plainly, and changeable later
so_that: I can keep screenshots on with confidence, and users who do not want the prompt see no change (O3, S2)
criteria:
  - id: AC-1
    text: Setup's screenshot step offers the prompt in one plain sentence, records the user's choice, and verifies it with one test capture in the chosen mode. Serves O3.
    check: judged
    bar: The shipped setup instructions carry the offer and a verify step for each mode; declining leaves today's task unchanged.
    probe: Reviewer reads the shipped setup instructions.
    expect: {}
  - id: AC-2
    text: With the prompt off (the default, and every existing install), the capture task and its output are unchanged from today. Serves O3, S2.
    check: judged
    bar: The registered task's command line and the capture output with the prompt off are identical to main's, pinned by a test (including the setup script's dry-run output).
    probe: Reviewer compares dry-run output and capture tests at main and the build branch.
    expect: {}
```

```yaml
id: US-4
as: the maintainer
want: the prompt built from existing operating-system or library features with very little code
so_that: it is cheap to maintain and has few ways to break (B1, S3, A1)
criteria:
  - id: AC-1
    text: Before planning, researcher's comparison of the per-capture prompt against a pause control and app-based skip is recorded with a recommendation; if it recommends replacing the per-capture prompt, atlas brings Connor an amendment brief instead of changing this spec silently. Serves A1.
    check: judged
    bar: A researcher note exists in the repo or the card thread comparing the three options on code size, failure modes and user burden, and the plan cites it.
    probe: Reviewer reads the researcher note and the plan's citation of it.
    expect: {}
  - id: AC-2
    text: The prompt adds no new long-running process and no new third-party dependency beyond what capture already installs, unless the plan records why none of the existing means works. Serves B1.
    check: judged
    bar: The diff adds no daemon, service or scheduled task and no new package to the setup script, or the plan records the justification and reviewer accepts it.
    probe: Reviewer reads the diff and the plan.
    expect: {}
  - id: AC-3
    text: The change is small and the reviewer judges it maintainable. Serves S3.
    check: judged
    bar: The production code change is under about 80 lines (tests and docs excluded) or the reviewer records why more is justified; reviewer's verdict says maintainable.
    probe: Reviewer reads the diff stat and the code.
    expect: {}
```

```yaml
id: US-5
as: the maintainer
want: the suite and type check green
so_that: the change is verified per AGENTS.md (S4)
criteria:
  - id: AC-1
    text: The repository suite is green from the repo root. Serves S4.
    check: auto
    probe: {kind: command, timeout: 60, argv: [gh, run, list, -R, Cordedmink2/activity-to-timesheet, --workflow, Checks, --branch, main, --status, completed, --limit, "1", --json, conclusion, --jq, ".[0].conclusion"]}
    expect: {exit: 0, regex: "^success$"}
  - id: AC-2
    text: Pyright reports zero errors from the repo root. Serves S4.
    check: auto
    probe: {kind: command, timeout: 60, argv: [gh, run, list, -R, Cordedmink2/activity-to-timesheet, --workflow, Checks, --branch, main, --status, completed, --limit, "1", --json, conclusion, --jq, ".[0].conclusion"]}
    expect: {exit: 0, regex: "^success$"}
```

## Edge cases
- E1: The user is away (screen locked) when a capture fires → the prompt cannot be answered and times out; no capture. Covered by US-1/AC-1.
- E2: A prompt from the previous capture is still open when the next one fires → no second prompt stacks; the earlier one's timeout ends it first. Covered by US-1/AC-1 (timeout shorter than the interval).
- E3: Presenting or screen-sharing → the prompt is a small window and may be visible to the audience; documented plainly in setup. Covered by US-3/AC-1.
- E4: Multiple monitors → one prompt per capture, covering all monitors. Covered by US-1/AC-2.
- E5: The scheduled task runs without a visible desktop session → treated as ignored; no capture. Covered by US-1/AC-1.
- E6: macOS or Linux → no capture pipeline ships; not applicable. Out of scope.

## Non-goals
- No automatic detection of confidential content.
- No replacement of the per-capture prompt by a lighter option without Connor's amendment decision.
- No change for users who do not opt in.
- No release is cut (AGENTS.md § Releasing).

## Open questions
- Mechanism (Windows toast vs message box from the existing capture script) and timeout → researcher and dev, recorded in plan.md. Does not change scope.

## Changes
<!-- YYYY-MM-DD: <IDs changed> — <reason>; linked updates: plan/tasks/tests; re-review: <card> -->
- 2026-10-20: US-5/AC-1, AC-2 — F1: auto probes now read the `Checks` workflow conclusion on main (pytest + pyright on windows-latest and ubuntu-latest) instead of bare python/pyright in a shared checkout; US-2/AC-2 bar scoped so only the captures line may differ (F4); US-1/AC-1 bar names mocked dialog no/timeout/failure. Reason: spec gate t_a6ab865c CHANGES REQUIRED. Linked updates: plan/tasks re-point on the plan PRs. Re-review: spec re-gate (Atlas, t_3c4f0453).

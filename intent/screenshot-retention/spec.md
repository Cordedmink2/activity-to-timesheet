# Spec: Screenshots don't pile up after they've done their job

**Intent:** [intent.md](intent.md), Accepted 2026-10-20 (Connor, in conversation with Hermes: "Yeah I think that sounds good"; recorded in the intent's Status line)
**Author:** atlas  **Date:** 2026-10-20  **Status:** Draft (spec gate pending)
**Serves:** O1–O3, S1–S2, B1–B3, D1–D2 (inventory below)

## Summary
Once a period's captures have done their job — the days are billed, and the month is reconciled or the
days are past a fixed age — the user is offered a clean-up and confirms it. The record of which days the
machine was used survives, so reconcile still works. Nothing is ever deleted silently, and unbilled
evidence is never deleted.

## Intent inventory (labels used below)
- O1 a finished period's screenshots are deleted (billed and past the point of reasonable revisit).
- O2 the record of days used survives deletion; month-end reconcile still works.
- O3 the user can see and change when deletion happens; nothing deleted without having been told.
- S1 60 days of captures, first month billed and reconciled → after clean-up that month's images are
  gone, its dates still appear in reconcile's index, and every unbilled day's images remain.
- S2 `pytest` and `pyright` green.
- B1 never delete captures for a day still unbilled, partly billed, or flagged by reconcile.
- B2 deletion stays on the machine and touches only the plugin's capture folder.
- B3 a day's evidence must not vanish mid-run.
- D1 default eligibility: after the month is reconciled, or 35 days for days fully billed, whichever first.
- D2 deletion is an ask the user confirms; never silent, for new or existing users.

## Problem → benefit → stories
Captures hold everything that was on screen and are never removed: a growing privacy risk and disk cost
the user never chose. The benefit is that evidence lives only as long as it is useful, with no loss of
unbilled evidence or of the days-worked index. US-1 is the offered clean-up, US-2 the protections, US-3
the index, US-4 visibility and settings, US-5 no regression.

## User stories

```yaml
id: US-1
as: a consultant whose past days are billed
want: to be offered a clean-up of screenshots that are no longer needed, and confirm it
so_that: confidential captures do not pile up on my machine (O1, D1, D2)
criteria:
  - id: AC-1
    text: When eligible days exist (a reconciled month, or fully billed days older than the configured age, default 35), the user is offered one clean-up naming the date range, the number of days and the space it frees, and nothing is deleted until they say yes. Serves O1, D1, D2.
    check: judged
    bar: On the 60-day fixture, the offer names the first month's dates, its day count and size; without a yes no file is removed; after a yes exactly the eligible days' images are removed.
    probe: Reviewer runs the offer and the confirmed clean-up against the 60-day fixture capture folder and lists it before and after.
    expect: {}
  - id: AC-2
    text: A no, or no answer, deletes nothing and the offer is not repeated in the same run; it may be offered again on a later run. Serves D2.
    check: judged
    bar: After a no, the fixture folder is unchanged and the same run does not ask again.
    probe: Reviewer reads the transcript and lists the fixture folder.
    expect: {}
```

```yaml
id: US-2
as: a consultant with days still unbilled or under question
want: those days' captures never to be deleted
so_that: I never lose the evidence I still need (B1, B2, B3)
criteria:
  - id: AC-1
    text: A day that is unbilled, partly billed, or flagged by reconcile is never eligible, whatever its age, and eligibility is decided from the timesheet provider's entries and the workspace records rather than assumed. Serves B1, S1.
    check: judged
    bar: On the 60-day fixture, every unbilled, partly billed and reconcile-flagged day keeps all its images after a confirmed clean-up; an automated test pins this with the fake provider.
    probe: Reviewer lists the fixture folder after the clean-up and reads the eligibility test.
    expect: {}
  - id: AC-2
    text: When eligibility cannot be established (provider unreachable, credentials missing), nothing is offered or deleted, and the user is told why. Serves B1.
    check: judged
    bar: With the fake provider failing, no offer is made and the reason is stated in one line.
    probe: Reviewer runs the offer against the failing-provider fixture.
    expect: {}
  - id: AC-3
    text: Deletion touches only image files inside dated folders of the configured capture folder; any other file there (logs, the user's own files) and anything outside it are left alone, and a path outside the folder is refused. Serves B2.
    check: judged
    bar: On a fixture folder containing a log, a non-image file in a dated folder and a symlink pointing outside, the clean-up removes only the eligible images and refuses to follow the symlink; an automated test pins this.
    probe: Reviewer runs the clean-up on the hostile-folder fixture and reads the test.
    expect: {}
  - id: AC-4
    text: The clean-up never runs while a daily or reconcile run is still reading the days it would delete; today and the day being drafted are never eligible. Serves B3.
    check: judged
    bar: The clean-up is offered only at the end of a run, after posting or after reconcile's verdicts; the day the run drafted and today are excluded by rule, pinned by a test.
    probe: Reviewer reads the shipped instructions and the exclusion test.
    expect: {}
```

```yaml
id: US-3
as: a consultant reconciling a month whose screenshots were cleaned up
want: reconcile to still know which days the machine was used
so_that: month-end reconciliation works after the clean-up (O2, S1)
criteria:
  - id: AC-1
    text: After a clean-up, reconcile's date index for the cleaned month lists exactly the dates it listed before. Serves O2, S1.
    check: judged
    bar: On the 60-day fixture, reconcile's index before and after the clean-up is identical for every date, pinned by an automated test.
    probe: Reviewer compares reconcile's index before and after the clean-up and reads the test.
    expect: {}
  - id: AC-2
    text: The daily run's no-date day picker, which also uses the capture folders as a date index, still finds the same candidate days after a clean-up. Serves O2.
    check: judged
    bar: The daily run's candidate-day selection on the fixture is unchanged by the clean-up.
    probe: Reviewer runs the no-date selection on the fixture before and after.
    expect: {}
```

```yaml
id: US-4
as: a consultant who wants control over my screenshots
want: to be told during setup that clean-up exists, and to see and change when it is offered
so_that: nothing about deletion surprises me (O3, D2)
criteria:
  - id: AC-1
    text: Setup tells the user in one plain sentence when clean-up will be offered and that it always asks first; existing users are told the same the first time it is offered. Serves O3, D2.
    check: judged
    bar: The shipped setup instructions and the first offer each carry that sentence in plain Simplified Technical English.
    probe: Reviewer reads the shipped setup instructions and the first-offer text.
    expect: {}
  - id: AC-2
    text: The age threshold is a user setting with the documented default of 35 days, and the user can turn the offer off entirely. Serves O3.
    check: judged
    bar: The setting is documented where the plugin's other settings are, its default is 35, and "off" stops all offers in a fixture run.
    probe: Reviewer reads the settings documentation and a fixture run with the offer off.
    expect: {}
```

```yaml
id: US-5
as: a maintainer and every existing user
want: nothing else about capture, daily or reconcile to change
so_that: the clean-up is the only difference (S2)
criteria:
  - id: AC-1
    text: The repository suite is green from the repo root. Serves S2.
    check: auto
    probe: {kind: command, timeout: 120, cwd: /home/ubuntu/Projects/Billables, argv: [python, -m, pytest, -q, tests, skills/daily/tests]}
    expect: {exit: 0, regex: "[0-9]+ passed"}
  - id: AC-2
    text: Pyright reports zero errors from the repo root. Serves S2.
    check: auto
    probe: {kind: command, timeout: 120, cwd: /home/ubuntu/Projects/Billables, argv: [pyright]}
    expect: {exit: 0, regex: "(^|\\n)0 errors"}
```

## Edge cases
- E1: A day billed to the provider then edited by the user so it is now partly billed → not eligible. Covered by US-2/AC-1.
- E2: The configured capture folder changed since the old captures were taken → only the currently configured folder is cleaned; the user is told an old folder exists. Covered by US-2/AC-3.
- E3: A weekend or evening folder with captures but no billable work → treated as eligible only if the day has no unbilled activity per the run's own day check; otherwise kept. Covered by US-2/AC-1.
- E4: macOS or Linux, where no capture pipeline ships → no offer. Covered by US-1/AC-1.
- E5: A partly failed delete (file locked by a viewer) → reported; the day's index is still kept; retried on a later offer. Covered by US-3/AC-1.
- E6: The user wants to keep a specific day → they say no to the offer or exclude it; it stays. Covered by US-1/AC-2.

## Non-goals
- No silent or scheduled deletion; no deletion at the end of every daily run (rejected in the intent).
- No deletion of anything outside the plugin's capture folder; no cloud or remote storage.
- No release is cut (AGENTS.md § Releasing).

## Open questions
- None that change scope. The day-index mechanism (empty dated folder or small manifest) is dev's in plan.md.

## Changes
<!-- YYYY-MM-DD: <IDs changed> — <reason>; linked updates: plan/tasks/tests; re-review: <card> -->

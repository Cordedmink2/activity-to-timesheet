# Spec: Check-in answers bill work the computer couldn't see

**Intent:** [intent.md](intent.md), Accepted 2026-10-20 (Connor, in conversation with Hermes: "Yeah I think that sounds good"; recorded in the intent's Status line)
**Author:** atlas  **Date:** 2026-10-20  **Status:** Draft (spec re-gate pending)
**Serves:** O1–O4, S1–S5, B1–B5 (inventory below)

## Summary
A user who steps away to take a phone call can say in a few words what they were doing when they come
back. The daily run then asks, under the table, whether to bill that stretch, quoting their words and
naming the client they point to. Answers given while working help attribute an unclear stretch. A user
who never installs a check-in watcher sees exactly today's behaviour.

## Intent inventory (labels used below)
- O1 return-from-away answer → a question under the table quoting it and naming the client.
- O2 opt-in in-work prompts whose answers help attribute an unclear stretch.
- O3 setup offers both, explains plainly, installs and verifies, records a decline as off.
- O4 no watcher installed → today's behaviour exactly.
- S1 Windows: step away 10 min, answer "call with <client>", `daily` lists it as a question (not a
  block); yes adds it for that client; nothing posts until the table is confirmed.
- S2 answer "lunch" → the stretch stays a break.
- S3 uninstall both watchers → same day's output unchanged from today's release.
- S4 clean machine: setup offers both, verifies an accepted one by finding its data, records a declined one as off.
- S5 `pytest` and `pyright` green per AGENTS.md.
- B1 the AFK watcher alone settles idle (refusal 5). B2 nothing billed unconfirmed; answers stay on the
  machine (refusals 1–3). B3 personal answers never become billable. B4 both watchers optional.
  B5 no user words or client names ship (refusal 4).

## Problem → benefit → stories
Phone calls and site visits are real billable work that leaves no trace, so the AFK watcher correctly
shows a break and the work is lost. The benefit is that the user's own words, captured at the moment,
turn that break into a **question they can say yes to**, without the run ever pretending the break was
active time. An answer cannot show switches between clients inside the stretch, so it is never a block
on its own (Connor's correction). US-1 to US-3 deliver the benefit; US-4 delivers the setup; US-5 and
US-6 protect today's users and the refusals.

## User stories

```yaml
id: US-1
as: a consultant who stepped away from the desk to take a client call
want: the daily run to list that stretch as a question quoting my check-in answer, its times and the client my words point to
so_that: work the computer couldn't see is billed when I say yes, and never without it (O1, S1, B2)
criteria:
  - id: AC-1
    text: For a recorded day whose check-in data holds a work answer over a break, the run lists one question under the table giving the stretch's start and end, the answer in the user's own words, and the client the words point to (by the client terms in the workspace context file). Serves O1, S1.
    check: judged
    bar: On the fixture day, the question appears under the table (not in it), quotes the answer verbatim, gives start and end times matching the check-in event clipped to the break, and names the client whose context-file terms the answer contains. Where the answer points to no known client, the question asks which client instead of naming one. On a second fixture day where the stretch overlaps an uncorroborated calendar event (E1), exactly one question is listed, citing both the event and the answer. Fixture data copies the real aw-watcher-checkin bucket shape (`aw-watcher-ask-away_<host>`, answer in `data.message`).
    probe: Reviewer runs the daily workflow against the recorded fixture day that carries a check-in answer over a break, and reads the rendered review.
    expect: {}
  - id: AC-2
    text: The stretch is not drafted as a block, is not passed to the coverage check, and is not covered by batch-accept; it takes its own answer, as an uncorroborated calendar event does today. Serves O1, S1, B2.
    check: judged
    bar: The drafted table and the coverage check input contain no entry for the stretch until the user answers yes to that question specifically; "accept all" leaves it unbilled.
    probe: Reviewer reads the drafted table, the coverage invocation and the review question for the fixture day.
    expect: {}
  - id: AC-3
    text: A yes adds a block for the named (or user-chosen) client over the stretch, which then goes through the normal posting confirmation; a no adds nothing. Either answer is recorded where the run records calendar-question rulings, and binds on any later run for that date. Serves O1, S1, B2.
    check: judged
    bar: After yes, the posting question lists the new entry and nothing posts before the user confirms the table; after no, no entry exists. A re-run of the same date does not ask the same question again and honours the recorded answer.
    probe: Reviewer walks the fixture day through review, posting confirmation (against the test provider, not a live account) and a second run of the same date.
    expect: {}
  - id: AC-4
    text: The day skeleton is identical with and without check-in data — breaks, work start, work end and every active ratio. Serves B1.
    check: judged
    bar: The skeleton output for the fixture day with the check-in bucket present is byte-identical to the output with it removed.
    probe: Reviewer compares the two skeleton outputs for the fixture day (and the automated test that pins this).
    expect: {}
  - id: AC-5
    text: On a real Windows machine with the check-in watcher installed, stepping away about 10 minutes and answering "call with <client>" makes `daily` for today list that stretch as a question quoting the answer, not a drafted block; yes adds it for that client; nothing posts until the table is confirmed; answering "lunch" instead leaves the stretch a break. Serves O1, S1, S2, B2.
    check: usage
    probe: Windows evidence from the repo's Windows end-to-end CI job (windows-latest, real aw-server and check-in watcher, the away answer injected through the watcher's own bucket) — the daily review text for the test day and the test provider showing no entry before confirmation. Steps CI cannot drive (a person answering the dialog) are decided ship-or-hold by Atlas in the decision log and monitored after release.
    expect: {}
```

```yaml
id: US-2
as: a consultant who answered a check-in with something personal
want: the stretch to stay a break with no billing question
so_that: lunch, the school run or a dismissed prompt never become billable (S2, B3)
criteria:
  - id: AC-1
    text: An answer matching a personal word (a short generic list shipped with the plugin, extended by the exclusions in the user's workspace context file), an empty answer, or a dismissed prompt leaves the stretch a break and produces no question. Serves S2, B3.
    check: judged
    bar: On fixture days whose answers are "lunch", "school run", an exclusion term from the fixture context file, an empty string and a dismissed prompt, the review shows the break unchanged and no check-in question.
    probe: Reviewer runs the daily workflow against each personal-answer fixture day.
    expect: {}
  - id: AC-2
    text: An answer that is neither personal nor matched to a client becomes a question that asks whether it was work and for which client; it is never billed or attributed without the user's yes. Serves B2, B3.
    check: judged
    bar: For the fixture answer "meeting", the question asks whether to bill it and for whom, names no client, and adds nothing to the table.
    probe: Reviewer runs the daily workflow against the ambiguous-answer fixture day.
    expect: {}
```

```yaml
id: US-3
as: a consultant who answers short prompts while working
want: my own description of the work to help the run attribute a stretch it found unclear
so_that: fewer unclear stretches need me, without my answer overruling what the machine recorded (O2)
criteria:
  - id: AC-1
    text: For a stretch the run has flagged as unclear, a check-in answer overlapping it (from the check-in watcher, or from aw-watcher-ask where the user already runs it) is offered as an attribution hint, cited with its words and time. Serves O2.
    check: judged
    bar: On the fixture day, the unclear block's resolution cites the overlapping answer; the hint ranks below a work-item reference and below the activity evidence.
    probe: Reviewer runs the disambiguation step on the in-work-answer fixture day.
    expect: {}
  - id: AC-2
    text: An in-work answer never creates, splits, moves or re-attributes a block the activity evidence already settled with confidence, and never changes the skeleton. Serves O2, B1.
    check: judged
    bar: On a fixture day where the answer names client B over a stretch confidently attributed to client A, the block stays client A; at most a 🔸 note mentions the disagreement as a question.
    probe: Reviewer runs the daily workflow against the conflicting-answer fixture day.
    expect: {}
  - id: AC-3
    text: An unanswered aw-watcher-ask prompt (recorded as unsuccessful) is ignored. Serves O2.
    check: judged
    bar: The fixture day's unanswered prompt contributes nothing to any block, hint or question.
    probe: Reviewer reads the run's handling of the unanswered-prompt fixture event.
    expect: {}
```

```yaml
id: US-4
as: a consultant running setup
want: setup to offer the check-in watcher in plain words, install and verify it if I say yes, and record a no as off
so_that: I get the benefit with the least effort and a decline is never reported as a failure (O3, S4, B4)
criteria:
  - id: AC-1
    text: Setup explains in plain Simplified Technical English what the check-in watcher will ask and when, and offers it on every platform; aw-watcher-ask is offered on Linux and macOS only and on Windows is described as not recommended (it needs a separate third-party program). Serves O3, S4.
    check: judged
    bar: The setup instructions a fresh agent follows produce one plain offer per watcher with what it asks and when; the Windows path does not recommend aw-watcher-ask or any Zenity port.
    probe: Reviewer reads the shipped setup instructions and a fresh-agent dry run of the offer on a Windows and a Linux path.
    expect: {}
  - id: AC-2
    text: An accepted watcher is installed by setup, keeps running after a reboot or sign-in, and is verified by finding its data for this host in the activity source after a test away period. Serves O3, S4.
    check: usage
    probe: Windows evidence from the windows-latest end-to-end CI job where it can drive the step, otherwise the Atlas logged ship decision plus post-release monitoring (the setup transcript showing install, the bucket found with an event after a test away, and the watcher still running after sign-out and sign-in).
    expect: {}
  - id: AC-3
    text: A declined watcher is recorded as off, reported as a deliberate choice at the finish, and never re-asked as a failure by setup or the daily run. Serves O3, S4.
    check: judged
    bar: A fresh-agent run that declines both reports both as off at the finish and the daily run raises nothing about them.
    probe: Reviewer reads a fresh-agent setup transcript with both declined, and the next daily run.
    expect: {}
  - id: AC-4
    text: Where a stale activity bucket from an old host name would stop the check-in watcher starting, setup detects it, explains it, and resolves it without deleting the user's activity history unless the user confirms that specific deletion. Serves O3, B2.
    check: judged
    bar: On a fixture bucket list holding two AFK buckets from different hosts, setup names the condition in plain words and proposes a fix; no bucket is deleted without an explicit yes naming it.
    probe: Reviewer reads setup's handling of the two-AFK-bucket fixture.
    expect: {}
```

```yaml
id: US-5
as: a consultant who installs neither watcher, or uninstalls them
want: the daily run, reconcile and setup to behave exactly as in today's release
so_that: the feature costs nothing to anyone who does not want it (O4, S3, B4)
criteria:
  - id: AC-1
    text: For a recorded day with no check-in data, the daily run's scripts produce output identical to today's release. Serves O4, S3.
    check: judged
    bar: Script outputs for the existing recorded fixture days are byte-identical before and after the change, pinned by an automated test.
    probe: Reviewer diffs the fixture-day outputs at main versus the build branch, and reads the pinning test.
    expect: {}
  - id: AC-2
    text: The repository suite and type check are green from the repo root. Serves S5.
    check: auto
    probe: {kind: command, timeout: 60, argv: [gh, run, list, -R, Cordedmink2/activity-to-timesheet, --workflow, Checks, --branch, main, --status, completed, --limit, "1", --json, conclusion, --jq, ".[0].conclusion"]}
    expect: {exit: 0, regex: "^success$"}
  - id: AC-3
    text: Pyright reports zero errors from the repo root. Serves S5.
    check: auto
    probe: {kind: command, timeout: 60, argv: [gh, run, list, -R, Cordedmink2/activity-to-timesheet, --workflow, Checks, --branch, main, --status, completed, --limit, "1", --json, conclusion, --jq, ".[0].conclusion"]}
    expect: {exit: 0, regex: "^success$"}
```

```yaml
id: US-6
as: a consultant whose answers name clients and personal matters
want: my answers to stay on my machine and out of everything the plugin ships or drafts for others
so_that: the check-in feature does not leak what I said (B2, B5)
criteria:
  - id: AC-1
    text: No shipped file contains a user answer, client name or host; the existing neutrality and redaction guards cover the new fixtures and instructions. Serves B5.
    check: auto
    probe: {kind: command, timeout: 60, argv: [gh, run, list, -R, Cordedmink2/activity-to-timesheet, --workflow, Checks, --branch, main, --status, completed, --limit, "1", --json, conclusion, --jq, ".[0].conclusion"]}
    expect: {exit: 0, regex: "^success$"}
  - id: AC-2
    text: Answers are read only from the local activity source and are not copied anywhere except the user's own workspace record of their rulings; a drafted bug report redacts them. Serves B2.
    check: judged
    bar: The instructions and scripts read answers from the local activity source only, write them only to the workspace rulings record, and the bug-report path redacts answer text.
    probe: Reviewer reads the shipped instructions and scripts touched by this change.
    expect: {}
```

## Edge cases
- E1: A check-in stretch overlaps an uncorroborated calendar event → one question citing both the event and the answer, not two. Covered by US-1/AC-1 (second fixture day in its bar).
- E2: A check-in stretch lies inside a corroborated calendar block already drafted → the answer is context only; no extra question. Covered by US-1/AC-2.
- E3: The check-in gap is shorter than the skeleton's break threshold, so the skeleton calls it active → treated as an in-work answer (US-3), never as a question. Covered by US-3/AC-2.
- E4: The answer names two clients → the question names both and asks which (or whether to split); never guessed. Covered by US-1/AC-1.
- E5: The stretch crosses midnight or the day boundary in the configured zone → clipped to the day being read. Covered by US-1/AC-1.
- E6: The date is already billed → the already-covered branch honours any recorded ruling and does not re-ask. Covered by US-1/AC-3.
- E7: Check-in buckets exist for several host names → only this host's bucket is read, as for the other watchers. Covered by US-1/AC-1 (fixture) and US-4/AC-4.
- E8: The check-in watcher is installed but has recorded nothing yet → behaves as US-5. Covered by US-5/AC-1.
- E9: End-of-block check-ins (upstream PR #5) are not yet released → US-3 works from whatever in-work answers exist; outcome 1 alone is the accepted fallback. Out of scope to run PR #5 for users before independent review (Reserved).

## Non-goals
- No change to how idle is decided: no answer turns away time into active time or moves a break (refusal 5).
- No answer is ever drafted as a block, batch-accepted or posted without its own yes.
- No new watcher is written by this project; improvements go upstream to aw-watcher-checkin.
- Setup does not recommend any Windows binary outside Python packaging, and does not run the unmerged
  checkin PR #5 for users (Reserved decisions).
- No release is cut (AGENTS.md § Releasing).

## Open questions
- Windows evidence for US-4/AC-2 and US-1/AC-5 comes from a Windows end-to-end CI job
  (windows-latest, real aw-server, the watcher installed as setup installs it). No Windows host is
  reachable from this box. What CI cannot drive (a person clicking a dialog) is a ship-or-hold
  decision Atlas records in the decision log and monitors after release. Nothing goes to Connor.
- In-work prompt cadence defaults (cooldown, daily cap, quiet hours) → dev, by "rarely enough that
  users keep it on", user-adjustable. Does not change scope.

## Changes
<!-- YYYY-MM-DD: <IDs changed> — <reason>; linked updates: plan/tasks/tests; re-review: <card> -->
- 2026-10-20: US-5/AC-2, AC-3, US-6/AC-1 — F1: auto probes now read the `Checks` workflow conclusion on main (pytest + pyright on windows-latest and ubuntu-latest) instead of bare python/pyright in a shared checkout; US-1/AC-5 added (F2, S1 real-Windows usage); US-1/AC-1 bar names the E1 fixture and real checkin bucket shape (W1). Reason: spec gate t_a6ab865c CHANGES REQUIRED. Linked updates: plan/tasks re-point on the plan PRs. Re-review: spec re-gate (Atlas, t_3c4f0453).

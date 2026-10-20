# Spec: Hands-off setup, and one front door for every non-daily job

**Intent:** [intent.md](intent.md), Accepted 2026-10-20 (Connor, in conversation with Hermes: "Yeah I think that sounds good"; recorded in the intent's Status line)
**Author:** atlas  **Date:** 2026-10-20  **Status:** Draft (spec re-gate pending)
**Serves:** O1–O4, S1–S4, B1–B3 (inventory below)

## Summary
A user who opens setup is first asked what they want to do, and is taken straight to that path: first
install, an existing install, onboarding a new client, fixing something, or reporting a bug or idea.
Setup does the installing itself wherever it safely can. Category rules are written only once the
machine has recorded about a week of real work, and every path reads and writes each fact in one place.

## Intent inventory (labels used below)
- O1 the user says what they want and reaches the right path (five paths).
- O2 setup does everything it safely can; the user acts only where only a human can.
- O3 category rules wait for enough recorded work (default about a week of workdays); daily still
  works meanwhile; the user is told when to come back, or reminded.
- O4 each fact has one home: client terms in the workspace context file, rules compiled from it,
  every path reads and writes that one place.
- S1 clean Windows: setup reaches "collecting data" with the user doing only human-only steps, each recorded as verified.
- S2 after a week, the category stage runs from real titles, its rules match the context file's
  clients, and a grep of the shipped plugin finds category terms defined in one place.
- S3 "I've got a new client" reaches onboarding in one step and updates context file and rules together.
- S4 `pytest` and `pyright` green per AGENTS.md.
- B1 foundational refusals hold (nothing billed unconfirmed; a bug report is drafted for the user to
  send, client names redacted; no user facts shipped). B2 install/security-setting/scheduled-task
  changes only after a plain what-and-why. B3 no password in chat.

## Problem → benefit → stories
People come back to setup for different jobs and must find their own way; category rules are written on
day one from memory instead of evidence; several steps make the user do what the agent could. The
benefit is less effort, rules that fit what the machine actually records, and no drift between copies of
the same fact. US-1 is the front door, US-2 the hands-off install, US-3 the evidence-based category
stage, US-4 onboarding, US-5 troubleshoot and feedback, US-6 one source of truth, US-7 no regression.

## User stories

```yaml
id: US-1
as: a consultant opening the plugin's setup for any reason
want: to be asked what I want to do and taken straight to that path
so_that: I do not have to find my own way through a first-install walk (O1)
criteria:
  - id: AC-1
    text: The first thing setup does is offer, in plain words, five choices — set up on a new machine, set up on a machine that already has some of it, add a new client, fix something that stopped working, report a problem or ask for a change — and routes to the matching path. Serves O1.
    check: judged
    bar: A fresh agent following the shipped instructions presents those five choices before any install step, and each choice leads to a distinct documented path.
    probe: Reviewer reads the shipped instructions and a fresh-agent transcript of the opening turn.
    expect: {}
  - id: AC-2
    text: A user who names their job up front ("I've got a new client", "my screenshots stopped") reaches that path in one step, without the menu being re-asked. Serves O1, S3.
    check: judged
    bar: In fresh-agent transcripts for "I've got a new client" and "screenshots stopped working", the agent's first substantive action belongs to the onboarding or troubleshoot path.
    probe: Reviewer reads two fresh-agent transcripts started with those phrases.
    expect: {}
  - id: AC-3
    text: The existing-machine path detects what is already installed and verified and does only what is missing, without overwriting the user's context file or rules. Serves O1, O2.
    check: judged
    bar: On a fixture machine state with the activity source, extensions and context file present, the path verifies each, skips them, and offers only the missing items; no existing file is overwritten without a shown diff and a yes.
    probe: Reviewer reads a fresh-agent transcript on the brownfield fixture state.
    expect: {}
```

```yaml
id: US-2
as: a non-technical consultant installing on a clean Windows machine
want: setup to install and configure everything it safely can for me
so_that: I only click where only a person can, and each step is checked (O2, S1, B2, B3)
criteria:
  - id: AC-1
    text: Setup lists the human-only steps (browser-store Add clicks, an administrator prompt for an install that already needs one today, a consent page, a credential in the harness's own store) and asks the user for nothing else; every other step it performs itself after one plain what-and-why. Any new install that would need administrator rights is a Reserved decision and is not added by this change. Serves O2, S1, B2.
    check: judged
    bar: The shipped instructions name the human-only steps explicitly; for every other step the agent acts after stating what and why; no step asks the user to type a command, a regular expression or a path.
    probe: Reviewer reads the shipped instructions against the human-only list.
    expect: {}
  - id: AC-2
    text: On a clean Windows machine, setup reaches a stated "collecting data" state with each step recorded as verified by its own check. Serves S1.
    check: usage
    probe: Windows evidence from the windows-latest end-to-end CI job where it can drive the step, otherwise the Atlas logged ship decision plus post-release monitoring (setup transcript ending in collecting data, with the verify output of each step).
    expect: {}
  - id: AC-3
    text: Setup never asks for or handles a password or token in chat, and no check it runs prints a credential; a repo guard test fails if any shipped setup path asks the user to type or paste a password, token or API key into chat, and the guard is shown to catch a planted violation. Serves B3.
    check: auto
    probe: {kind: command, timeout: 60, argv: [gh, run, list, -R, Cordedmink2/activity-to-timesheet, --workflow, Checks, --branch, main, --status, completed, --limit, "1", --json, conclusion, --jq, ".[0].conclusion"]}
    expect: {exit: 0, regex: "^success$"}
```

```yaml
id: US-3
as: a consultant whose machine has only just started recording
want: the category stage to wait until about a week of my real work is recorded, and to tell me when to come back
so_that: my category rules come from what my machine shows rather than what I remember (O3, S2)
criteria:
  - id: AC-1
    text: Setup reports how many workdays of activity are recorded; under the threshold (default five workdays, user-adjustable) it skips the category stage, says plainly when to come back, and leaves the daily run working without rules. Serves O3.
    check: judged
    bar: On a fixture source with two recorded workdays, setup ends in "collecting data", names the date to come back, writes no category rule, and the daily run still drafts a day (with more 🔸 blocks).
    probe: Reviewer reads a fresh-agent setup transcript and a daily run against the two-day fixture.
    expect: {}
  - id: AC-2
    text: The user is reminded when enough data exists — by the daily run noticing the threshold has passed and offering the category stage — without a new background process. Serves O3.
    check: judged
    bar: On a fixture source past the threshold with no managed rules, the daily run offers the category stage once per run in one line, and stops offering once rules exist or the user declines for good.
    probe: Reviewer reads a daily run against the past-threshold fixture.
    expect: {}
  - id: AC-3
    text: Run after the threshold, the category stage draws its candidate terms from the recorded titles and hosts, and its written rules match the clients in the context file. Serves S2.
    check: usage
    probe: Real machine evidence after a week of recording (the inspect output, the candidates written, and the verify lines matching each client in the context file).
    expect: {}
```

```yaml
id: US-4
as: a consultant who has a new client
want: to say so and have the client added to my context file and category rules together
so_that: the new client's work is recognised on my next run with no other place to update (O1, O4, S3)
criteria:
  - id: AC-1
    text: The onboarding path asks only for decisions (client name as the provider spells it, code, terms, profile tag if any), finds facts itself from recorded titles and hosts, shows the context-file diff, and on a yes writes the file and rebuilds the rules in the same step. Serves S3, O4.
    check: judged
    bar: A fresh-agent onboarding transcript on a fixture workspace ends with the context file holding the new client section and the rule-rebuild verify lines including the new client; no separate list of terms is kept anywhere else.
    probe: Reviewer reads a fresh-agent onboarding transcript and the resulting fixture workspace.
    expect: {}
  - id: AC-2
    text: Onboarding a client whose work has not been recorded yet still writes the client section and is honest that its terms are unverified, as the category script already reports. Serves O3, O4.
    check: judged
    bar: The transcript reports the new client's terms as not yet seen and does not call it a failure.
    probe: Reviewer reads the fresh-agent transcript for an unrecorded new client.
    expect: {}
```

```yaml
id: US-5
as: a consultant whose capture or timesheet stopped working, or who found a bug or wants a change
want: a path that diagnoses the fault with the plugin's existing checks, or drafts a report I can send
so_that: I get unstuck without knowing where to look, and nothing leaves my machine without me (O1, B1)
criteria:
  - id: AC-1
    text: The troubleshoot path runs the same verify checks setup uses, in order, stops at the first failing one, and reuses the existing diagnosis references rather than duplicating them. Serves O1, O4.
    check: judged
    bar: For a fixture with a scheduled capture task pointing at a missing interpreter, the troubleshoot path names that check as failing and gives the existing documented fix; its instructions reference rather than copy the first-run and endpoint-security material.
    probe: Reviewer reads the shipped instructions and a fresh-agent troubleshoot transcript on the fixture.
    expect: {}
  - id: AC-2
    text: The feedback path drafts an issue for the user to send themselves, through the existing reporting reference, with client names, hosts and answers redacted; from the setup menu it never sends or posts it (the daily run's existing file-after-explicit-yes route is unchanged). Serves B1.
    check: judged
    bar: The drafted report contains no client name, host or user answer from the fixture context file, and the agent hands it to the user rather than creating it.
    probe: Reviewer reads a fresh-agent feedback transcript on the fixture workspace.
    expect: {}
```

```yaml
id: US-6
as: the maintainer and every skill in the plugin
want: each fact defined in exactly one place
so_that: changing a client, a term or a step changes it everywhere (O4, S2)
criteria:
  - id: AC-1
    text: Category terms have one home, the workspace context file; every path that needs them (setup, onboarding, daily, reconcile) reads and writes that file and compiles rules from it, and no shipped skill or script defines its own list of terms. Serves O4, S2.
    check: judged
    bar: A grep of the shipped plugin for the places category terms are read or written finds only the context-file parser and the rule compiler; an automated guard fails if a second definition appears.
    probe: Reviewer greps the shipped tree and reads the guard test.
    expect: {}
  - id: AC-2
    text: Steps shared between paths (probes, verify checks, install commands) live once and are referenced, not copied, by each skill that uses them. Serves O4.
    check: judged
    bar: No verify check or install command text appears in two shipped skill files; shared material sits in one reference or script that each path cites.
    probe: Reviewer reads the shipped skill files and references for duplicated step text.
    expect: {}
  - id: AC-3
    text: The daily skill is no larger after this change than before it, and any new skill stays within the plugin's skill-size ceiling (issue #57). Serves O4.
    check: judged
    bar: Word counts of each shipped SKILL.md before and after are reported; daily's does not grow; new skills are under 5,000 words.
    probe: Reviewer runs a word count on each shipped SKILL.md at main and at the build branch.
    expect: {}
```

```yaml
id: US-7
as: an existing Billables user
want: my installed setup, context file and daily runs to keep working through this change
so_that: the redesign costs me nothing (O4, S4)
criteria:
  - id: AC-1
    text: An existing workspace and rule set are read as they are; any file migration is shown as a diff and needs a yes. Serves O4.
    check: judged
    bar: On the existing fixture workspace, the existing-machine path changes no file without a shown diff and a yes, and the daily run drafts the fixture day as before.
    probe: Reviewer reads the transcript and the fixture workspace before and after.
    expect: {}
  - id: AC-2
    text: The repository suite is green from the repo root. Serves S4.
    check: auto
    probe: {kind: command, timeout: 60, argv: [gh, run, list, -R, Cordedmink2/activity-to-timesheet, --workflow, Checks, --branch, main, --status, completed, --limit, "1", --json, conclusion, --jq, ".[0].conclusion"]}
    expect: {exit: 0, regex: "^success$"}
  - id: AC-3
    text: Pyright reports zero errors from the repo root. Serves S4.
    check: auto
    probe: {kind: command, timeout: 60, argv: [gh, run, list, -R, Cordedmink2/activity-to-timesheet, --workflow, Checks, --branch, main, --status, completed, --limit, "1", --json, conclusion, --jq, ".[0].conclusion"]}
    expect: {exit: 0, regex: "^success$"}
```

## Edge cases
- E1: The user's answer to the opening menu fits two paths ("new laptop, same clients") → the existing-machine path, which detects what is missing. Covered by US-1/AC-3.
- E2: The machine already has a week of recorded data on first install → the category stage runs straight away. Covered by US-3/AC-1.
- E3: A user who already has rules written on day one by the old setup → they are left alone; the daily run's existing staleness check governs rebuilds. Covered by US-7/AC-1.
- E4: An install the agent cannot perform without administrator rights → told plainly as a human-only step; never weakened security. Covered by US-2/AC-1 (Reserved: anything needing administrator rights or weakening endpoint security).
- E5: An exported (non-Claude-Code) install, where skills are prefixed → every path resolves its siblings the way setup already does. Covered by US-6/AC-2.
- E6: Onboarding a client whose code is an ordinary word → the existing term rules apply. Covered by US-4/AC-1.
- E7: macOS or Linux → the screenshot and calendar steps report as not applicable, as today. Covered by US-7/AC-1.

## Non-goals
- No new long-running process or scheduler for reminders; the daily run is the reminder.
- No change to what the daily run bills or how it decides idle.
- No automatic sending of bug reports, telemetry or anything off the machine.
- No installs needing administrator rights, and nothing that weakens endpoint security, without Connor (Reserved).
- No release is cut (AGENTS.md § Releasing).

## Open questions
- Real-Windows evidence for US-2/AC-2 and US-3/AC-3 needs an interactive Windows session with about a
  week of data; atlas arranges it at the build gate. Does not change scope.
- Whether the paths are separate skills or one skill with a menu → dev in plan.md, judged on US-6.
  The intent's proposed starting point (setup keeps install + menu; small `onboard-client` and
  `troubleshoot` skills; feedback reuses the reporting reference) is atlas's default. Does not change scope.

## Changes
<!-- YYYY-MM-DD: <IDs changed> — <reason>; linked updates: plan/tasks/tests; re-review: <card> -->
- 2026-10-20: US-2/AC-3, US-7/AC-2, AC-3 — F1: auto probes now read the `Checks` workflow conclusion on main (pytest + pyright on windows-latest and ubuntu-latest) instead of bare python/pyright in a shared checkout; US-2/AC-3 names a password-ask guard proved by a planted violation (W2); US-2/AC-1 keeps new admin installs Reserved (W3); US-5/AC-2 scoped to the setup menu (plan Q1). Reason: spec gate t_a6ab865c CHANGES REQUIRED. Linked updates: plan/tasks re-point on the plan PRs. Re-review: spec re-gate (Atlas, t_3c4f0453).

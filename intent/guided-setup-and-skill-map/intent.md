# Intent: Hands-off setup, and one front door for every non-daily job

**Author:** Connor  **Date:** 2026-10-20
**Status:** Accepted — 2026-10-20 (Connor, in conversation with Hermes: "Yeah I think that sounds good")
**Type:** improvement
**Origin:** Connor, 2026-10-20.
**Appetite:** not set

## As raised
> "The setup skill should actually install and setup more for the user to make it a more hands off
> process for them. Also, maybe before running the aw category creation stage of the skill, skill
> should make the user have aw run in the background for a few days or a week so that Claude can
> have a good amount of examples … Also, add to the start of the setup skill a question … whether
> it's onboard new clients to their aw categories and their .context.md or whether it's
> troubleshooting or whether it's reporting a bug/change request/feature request or whether it's
> greenfield or brownfield setup required. Actually, maybe we should just make more skills for the
> billables plugin? I just don't want to have multiple sources of truth — for example, aw categories
> should have one file to maintain that multiple skills can use."

## Problem
Setup does one long first-install walk. People come back to it for other reasons — a new client, a
broken capture task, a bug to report, a machine that already has ActivityWatch — and have to find
their own way through. Category rules are written on day one, from little or no recorded activity,
so they are built from what the user remembers rather than what their machine actually shows.
Several steps still ask the user to do by hand what the agent could do for them.

## Desired outcome
1. The user says what they want and is taken to the right path: first install on a clean machine,
   setup on a machine that already has some of it, onboarding a new client, fixing something that
   stopped working, or reporting a bug / requesting a change or feature.
2. Setup does everything it safely can itself; the user is asked to act only where only a human
   can (clicking a browser store button, an admin prompt, a consent page, a credential).
3. Category rules are written once the machine has recorded enough real work to learn from
   (default about a week of workdays); until then the daily run still works, and the user is told
   when to come back, or reminded.
4. Each fact has one home. Client terms live in the workspace context file; category rules are
   compiled from it; every path (setup, onboarding, daily, reconcile) reads and writes that one
   place rather than keeping its own copy.

## Boundaries
- Foundational refusals hold, especially: nothing billed unconfirmed; nothing sent off the machine
  (a bug report is drafted for the user to send, with their client names redacted); no user facts
  shipped in the plugin.
- Installing software, changing security settings or registering scheduled tasks happens only
  after the user has been told what and why in plain words.
- Never asks for or handles a password in chat; credentials go through the harness's own store.

## First-version decisions
- Whether the paths become separate skills or stay one skill with a menu is the implementer's
  choice, judged on: one source of truth per fact, the daily skill staying within its size ceiling
  (issue #57), and the user being able to say "onboard a client" and get there directly.
  Proposed starting point: `setup` keeps install (clean and existing machine) with the menu at its
  start; new small skills for `onboard-client` and `troubleshoot`, with feedback reusing the
  existing reporting reference; all of them call the same scripts rather than duplicating steps.

## Autonomy envelope
The implementer may decide alone: skill boundaries and names, how the wait-for-data stage is
scheduled or reminded, what setup automates, migration of existing users' files, tests, docs, ADRs.
Priorities: one source of truth; user effort; plain language for non-technical users.

## Reserved decisions
- Anything setup would install with administrator rights or that weakens endpoint security.
- Cutting a release (AGENTS.md § Releasing).

## Success check
- On a clean Windows machine, setup reaches "collecting data" with the user doing only the steps
  listed as human-only, and records each one as verified.
- After a week of recorded work, the category stage runs from real titles and its rules match the
  clients in the context file; a grep of the shipped plugin finds category terms defined in one place.
- Saying "I've got a new client" reaches the onboarding path in one step and updates the context
  file and rules together.
- `pytest` and `pyright` green per AGENTS.md.

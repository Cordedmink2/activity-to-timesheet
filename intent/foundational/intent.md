# Intent: Reconstruct work activity into a trustworthy timesheet

Status: Accepted — 2026-10-19 (Atlas for Connor, under #42). Created 2026-08-31; refusals drafted
2026-09-07 and agreed under #42.

## Problem

Consultants working across multiple clients have to reconstruct their timesheets from memory.

Evidence of what they worked on already exists in their computer activity, but it is fragmented. Rebuilding the day manually is slow, error-prone, and makes legitimate billable work easy to forget.

An agent should be able to do most of this reconstruction itself. It should not need the user to repeatedly explain the same people, projects, signals or billing conventions, and a normal run should not require loading an entire workday's raw evidence into one large context.

## Proposed outcome

A user asks their agent to reconstruct a workday and receives a timesheet that is as close to correct as the available evidence allows, with the goal that a routine day requires no manual reconstruction or correction.

The agent should use recorded activity together with retained user context to resolve the day by itself. When genuinely necessary context is missing, it should ask the user a focused question rather than guess. Useful answers should be retained and maintained so the same ambiguity can be resolved automatically in future sessions.

The workflow should remain context-efficient as the amount of activity grows. The main agent should work from the evidence and conclusions it needs rather than carrying the whole day's raw activity in one context.

Nothing is billed until the user explicitly approves it. A consultant bills several clients from
one machine and cannot honestly reconstruct Tuesday from memory; this reconstructs the workday from
local activity data, proposes per-client billable blocks, and posts them once the user confirms. It
does the remembering; the user does the confirming.

## Affected users and systems

Consultants working across multiple clients from one computer.

Today the workflow uses ActivityWatch as the activity source, an agent to interpret the evidence, retained workspace context to capture user-specific knowledge, and Harvest as the timesheet provider.

## Constraints

- Recorded activity is evidence, not the authoritative timesheet.
- Human input should be the exception for missing context, not a routine classification step.
- Missing or conflicting evidence must be surfaced rather than hidden behind a confident guess.
- Context learned from the user should be reusable across sessions and maintained as reality changes.
- Personal or non-billable activity must not silently become billable work.
- User-specific clients and billing conventions must remain separate from the generic product.
- A run should keep its working context bounded rather than accumulating all raw activity in one agent context.
- The product should not depend conceptually on ActivityWatch or Harvest, even though they are the current implementations.

## Open questions

- What evidence is sufficient to resolve a period automatically, and when should the agent ask the user?
- What learned context should be retained, and how should stale or conflicting context be corrected over time?
- What decomposition approach best keeps each run context-efficient without losing evidence needed to reconstruct the day accurately?
- ~~How far should the product extend beyond reconstructing a normal workday?~~ Answered by
  "What it will not become" below (#42).

## What it will not become

These are refusals, not a backlog. A feature request that requires one of them is declined, and
the refusal is the answer rather than a deferral. Agreed under #42: the union of the refusals in
that issue and the draft reconstructed from spec issue #2.

1. **A thing that bills on its own.** Every write to the provider carries the confirmation gate in
   the invocation. No auto-post, no batch mode, no "just bill it" setting that turns the gate off:
   the gate is the product, not a safety feature on it. The same holds for distribution — the
   frontmatter that stops a harness invoking the skill unprompted is kept, and a channel that
   rejects it is declined rather than accommodated.
2. **A monitoring tool.** One person's own machine and their own timesheet. No employer, team or
   manager view of anyone's activity.
3. **A thing that sends activity anywhere.** The product runs no service of its own: no cloud
   backend, no telemetry, no upload of activity or screenshots. Activity is read only by the
   user's own agent, and the only thing written outward is the entries the user confirms to their
   own provider.
4. **A carrier of one user's facts.** Client names, project codes, task names, colleagues and
   machine specifics live in the user's workspace. A shipped file that names them is a defect;
   `tests/test_provider_neutrality.py` and the redaction guard hold it.
5. **A thing that decides whether the user was working.** Idle is settled by the AFK watcher and
   nothing re-infers it — not a screenshot, not a window title, not a calendar event. A source that
   disagrees becomes a question to the user, never a block.
6. **A second front end to the provider.** Raw provider data beyond a day's entries — project
   lists, monthly totals, reports — is the provider's own interface's job.
7. **A product that is conceptually ActivityWatch-to-Harvest.** Both are the current adapters. A
   rule that could only be true of one of them is written wrongly.

**Not now** — not refused, so a request for one is triaged rather than declined: start/stop time
tracking, and invoicing, quoting or rates.

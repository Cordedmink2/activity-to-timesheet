# Intent: Screenshots don't pile up after they've done their job

**Author:** Connor  **Date:** 2026-10-20
**Status:** Accepted — 2026-10-20 (Connor, in conversation with Hermes: "Yeah I think that sounds good")
**Type:** improvement
**Origin:** Connor, 2026-10-20.
**Appetite:** not set

## As raised
> "Screenshots should be deleted at the end of the /daily run or maybe at the end of the month
> actually because they shouldn't be needed anymore."

## Problem
The capture task writes one image per monitor every ~2.5 minutes on workdays and nothing ever
removes them. They hold everything that was on screen, so keeping them indefinitely is both a disk
cost and a privacy risk the user never chose.

## Desired outcome
1. Screenshots for a period are deleted once that period is finished with: billed, and past the
   point where the user might reasonably revisit it.
2. The record of which days the machine was used survives the deletion, so month-end
   reconciliation still works.
3. The user can see and change when deletion happens, and nothing is deleted without them having
   been told it will be.

## Boundaries
- Never delete captures for a day that is still unbilled, partly billed, or flagged by reconcile.
- Deletion stays on the user's machine and touches only the plugin's own capture folder.
- A day's evidence must not vanish mid-run.

## First-version decisions
- Deleting at the end of each `/daily` run was considered and rejected as the default: the
  reconcile skill uses the per-day screenshot folders as its index of days worked, and a user
  correcting a posted day later would have lost the evidence. Default: after the month is
  reconciled, or a fixed age (proposed 35 days) for days already fully billed, whichever is first.
- Deletion is an ask (Connor, 2026-10-20): the user is offered the clean-up and confirms it; it
  never runs silently, for new or existing users.

## Autonomy envelope
The implementer may decide alone: the mechanism, the exact default age, how the day index is kept
(e.g. an empty dated folder or a small manifest), how setup explains it, tests and docs. Priorities:
never lose unbilled evidence; privacy; least user effort.

## Reserved decisions
- Cutting a release (AGENTS.md § Releasing).

## Success check
- A test machine with 60 days of captures, the first month billed and reconciled: after the
  clean-up, that month's images are gone, its dates still appear in reconcile's index, and every
  unbilled day's images remain.
- `pytest` and `pyright` green per AGENTS.md.

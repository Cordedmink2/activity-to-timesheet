# 0009. A check-in answer is a question, not a block

Status: accepted. Extends [ADR-0008](0008-the-calendar-is-evidence-of-intent-not-activity.md).

## Context

A check-in watcher asks the user, when they return from away, what they were doing. The
answer is the user's own words about time the computer could not see. A plain reading of "an
answer says what I did" invites drafting a block from it.

## Decision

An answer is context. It is never a block on its own. A work answer over a break becomes a
**check-in question**, put to the user at review by the same path as a calendar question:
listed apart from the table, own answer, not covered by batch-accept, never passed to
`--cover`. A yes makes a user-dictated block. A no or a silence leaves the time unbilled. Both
rulings are recorded in `Timesheets/<date>_harvest_responses.json` under `checkin_questions`
and bind on re-run.

A personal word always wins over a client term ("lunch with <client>" stays a break). Only
check-in answers over a break create questions; answers from the ask watcher are hints.

## Why

It is the first priority of the product that nothing is billed that the user has not
confirmed and that personal time is never mistaken for work. An answer typed in a hurry on
return, possibly days later, is weaker evidence than a calendar entry. Putting it through the
existing question path adds no new way to bill.

## Cost

A client lunch is missed unless the user dictates a block. That is recoverable at review.

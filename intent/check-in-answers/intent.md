# Intent: Use check-in answers to bill work the computer couldn't see

**Author:** Connor  **Date:** 2026-10-20
**Status:** Accepted — 2026-10-20 (Connor, in conversation with Hermes: "Yeah I think that sounds good")
**Type:** improvement
**Origin:** Connor, after reviewing ActivityWatch community watchers (aw-watcher-checkin,
aw-watcher-ask) against complaints from Billables users.
**Appetite:** not set

## As raised
> "Some issues that my users have had is that they're saying when they take phone calls and stuff,
> they're not recorded, and like sometimes they're away from desk, but still working."
> "Let's add aw-watcher-ask and aw-watcher-checkin to the setup skill and update the plugin to have
> support. … All this will have to be planned and reviewed carefully."

## Problem
Phone calls, site visits, whiteboard sessions and corridor conversations leave no trace on the
computer. The AFK watcher correctly calls that time "away", so the daily run shows a break, and the
work is either forgotten or rebuilt from memory days later — exactly what the product exists to stop.
The calendar helps only when the work was scheduled.

## Desired outcome
1. When a user comes back to their desk after time away, they can say in a few words what they were
   doing, and the daily run asks whether to bill that stretch, quoting their answer and naming the
   client their words point to.
2. A user can opt in to short periodic prompts ("what are you working on?") whose answers help the
   run attribute an unclear stretch to the right client.
3. Setup offers both, explains plainly what each will ask and when, installs and verifies them, and
   records a decline as off rather than a failure.
4. A user who installs neither sees today's behaviour exactly.

## Who it is for
Consultants using Billables whose billable work happens partly away from the keyboard. Connor
decides product behaviour.

## Boundaries
- Foundational refusal 5 holds: the AFK watcher alone decides whether the user was at the machine.
  A check-in answer labels away time; it never turns it into active time or moves the day skeleton.
- Foundational refusals 1–3 hold: nothing is billed without confirmation, the prompts and answers
  stay on the user's machine, and nothing about the answers is visible to anyone else.
- Personal answers ("lunch", "school run") must never become billable.
- Both watchers are optional third-party tools; the plugin works fully without them.
- No user's own words or client names ship in the plugin (refusal 4).

## First-version decisions
- Both kinds of prompt matter: answers after time away fill gaps, and answers while working give the
  agent the user's own description of the work, which is strong context for attribution (Connor,
  2026-10-20). Return-from-away ships first because it already works; in-work prompts follow.
- Preferred means: one watcher, aw-watcher-checkin, for both. Its return-from-away check-in is
  released; its end-of-block check-ins (upstream PR #5) attach an answer to a whole stretch of work
  rather than a single moment. If a plain timed prompt is still wanted after that, add it as a
  checkin trigger (upstream contribution) rather than a second watcher.
- aw-watcher-ask: the plugin reads its answers if the user already runs it (cheap, same kind of
  evidence), but setup does not recommend it on Windows, where it needs a separately installed
  Zenity port. Setup may offer it on Linux/macOS.
- A check-in answer is **context, never a block on its own** (Connor, 2026-10-20). One answer covers
  a whole stretch but says nothing about switches between clients or projects inside it, so it can't
  be trusted to draw a timesheet row. The run uses it two ways:
  - **While working:** as an attribution hint for an unclear stretch, ranked below a work item and
    never overriding the activity evidence.
  - **Away time with a work answer:** listed under the table as a question quoting the user's words
    ("You said 'call with Acme', 2:10–2:45. Bill it?"), the way an uncorroborated calendar event is.
    It becomes a block only when the user says yes. Without this, the phone-call case would still go
    unbilled.

## Autonomy envelope
The implementer may decide alone: which build or fork of each watcher to install and from where
(PyPI release, the ActivityWatch-org repository, or a pinned commit); how the plugin finds and reads
their data; prompt thresholds and defaults; how setup verifies them; whether to contribute fixes
upstream; tests, docs, ADRs and the decision-log entries. Priorities in order: never bill what the
user didn't confirm; never mistake personal time for work; least setup burden; richest attribution.
Good-enough fallback: outcome 1 alone, Windows first.

## Reserved decisions
- Recommending Windows users install a third-party binary outside Python packaging (e.g. a Zenity
  port for aw-watcher-ask).
- Running a not-yet-merged upstream change (checkin PR #5) for users before it has had an
  independent review.
- Cutting a release: the maintainer names the version (AGENTS.md § Releasing).

## Assumptions
- Most users are on Windows (the screenshot and calendar paths are Windows-first); both watchers
  must be proven on Windows, not only Linux.
- aw-watcher-checkin's unreleased org changes may be needed; the 2023 PyPI build is the fallback.
- aw-watcher-ask records a moment, not a span, so it attributes nearby work rather than filling a gap.

## Open questions
- If checkin's block check-ins stall upstream → implementer chooses between a pinned reviewed fork
  and contributing the trigger, and brings Connor an amendment brief only if outcome 2 can't be met
  on Windows without a reserved choice.
- How often in-work prompts may interrupt (cooldown, daily cap, quiet hours) → implementer, by
  "rarely enough that users keep it on"; defaults are user-adjustable.

## Success check
- On a Windows test machine with the check-in watcher installed: step away 10 minutes, answer
  "call with <client>", run `daily` for today, and see that stretch listed as a question quoting
  the answer, not drafted as a block; saying yes adds it for that client, and nothing posts until the
  table is confirmed.
- Answer "lunch" instead and the stretch stays a break.
- Uninstall both watchers and the same day's output is unchanged from today's release.
- Setup run on a clean machine offers both, verifies an accepted one by finding its data, and
  records a declined one as off.
- `pytest` and `pyright` are green per AGENTS.md.

## Clarifications
### Session 2026-10-20
- Q: Draft a check-in answer as a block, or list it as a question? → A: Connor first said "You
  decide" (Hermes proposed draft-as-block), then corrected it: answers are extra context only,
  because an answer doesn't show switches between clients or projects inside the stretch it covers.
- Q: One watcher or two for in-work prompts? → A: Connor: "You decide"; noted periodic asks are
  valuable context. Hermes chose aw-watcher-checkin for both, aw-watcher-ask read-only support.

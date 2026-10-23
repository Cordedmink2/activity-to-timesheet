# Check-in answers

A check-in watcher asks the user, on return from away, what they were doing. The words land in the activity source. `scripts/checkin_answers.py` reads them. **An answer is context. It is never a block, and nothing is billed without its own yes** (ADR-0009).

## Run it (Step 2)

Write three small files from what you already hold, then run:

```
python scripts/checkin_answers.py <date> --terms <file> --skeleton <file> --calendar <file> --rulings <file>
```

- `--terms`: `{"exclusions": [...], "off": [...]}`. The clients and their terms are read by the script from `Timesheets/.context.md`, the one home of the terms; do not copy them here. `exclusions` are the user's own personal words from `.context.md`. Put `"checkin"` or `"ask"` in `off` when `.context.md` says `Check-in watcher: off` or `Ask watcher: off` under `## Preferences`.
- `--skeleton`: the output of `afk_blocks.py <date> --json`.
- `--calendar`: the output of `calendar_day.py <date>`, if the calendar is on. Leave it out if not.
- `--rulings`: `Timesheets/<date>_harvest_responses.json`, if it exists.

Read `status`. `off`, `absent` and `empty` are settled: say nothing, raise no failure, do not ask to install. `ok` gives `questions`, `hints` and `ruled`.

## Questions

A **check-in question** is a work answer over a break. Put each one under the table, after the calendar questions. Say the time range and the user's own words. If `clients` has one name, ask about that client. If it has several, ask which, or whether to split. If it is empty ("meeting"), ask whether it was work and for which client. If `calendar` is set, the same question cites that calendar event too: one question, not two.

Rules, the same as for a calendar question:

- It is not drafted and not billed unless the user says yes. It is not in the block counts, never in `--cover`, and batch-accept does not cover it.
- A yes makes a user-dictated block over the question's span. The three Step 6 guards leave it alone. Declare it with the draft, naming the answer. Step 8 lists it and passes it to `--cover`.
- A no, or no answer, leaves it unbilled. Ask once.
- Step 10 records the answer under `checkin_questions` in `Timesheets/<date>_harvest_responses.json`: `{"start": "12:00:00", "end": "12:40:00", "ruling": "yes", "words": "..."}`. Keyed by start and end. A recorded ruling binds: a re-run lists it under `ruled`, not `questions`, and the already-covered branch of Step 1 does not ask again.

**The span is the answer clipped to the break**, never the whole break: from the later of the answer's start and the break's start, to the earlier of the answer's end and the break's end. Two answers in one break give two questions that do not overlap, and a personal stretch (lunch) is in no question. An answer over two breaks gives one question per break, each clipped to its break. The ruling is keyed by that span, so a ruling on one question leaves the others open.

A personal answer (lunch, school run, an exclusion) stays a break and gets no question. A personal word wins over a client name: "lunch with ACME" is a break.

## Hints

`hints` are answers that cannot explain a break: a gap shorter than the break threshold, or any answer from the ask watcher (a point in time). Use them in Step 5's ladder as one more rung. They rank below a work-item reference and below the activity evidence. A hint never settles a block the evidence settled with confidence.

## Context only

An answer inside a corroborated calendar block (`placement: context` in `answers`) adds nothing: the calendar path already asks.

## What stays on the machine

Answers are the user's words. They never leave the machine, and `reporting-issues.md` redacts them before any report. The script reads only the local activity source and writes nothing.

# ADR-0007: Two boundaries — the provider writes, the sources read

**Status:** Proposed — drafted 2026-09-07 under #44, for Connor to accept or amend. The rule it
records is already enforced; what is proposed is the write-up.
**Context:** whole repo. Related: [`CONTEXT.md`](../../CONTEXT.md) § "The services", which states the
rule; [ADR-0006](./0006-keep-the-provider-in-plugin-but-behind-a-command-contract.md), which keeps the
written side inside this plugin behind a command contract; [ADR-0008](./0008-the-calendar-is-evidence-of-intent-not-activity.md),
which added a fourth service on the read side; issues #37, #44.

## Context

Four services are in play. ActivityWatch records what the machine saw. Dataverse holds the work
items it was busy with. The user's calendar, when enabled, records what they were scheduled to do.
Harvest holds the billed time. Three are read; one is written to.

The tempting shape is one abstraction for all four — a *service adapter* with credentials, a
confirmation step and an error contract handled the same way everywhere. It reads as tidy and it
misprices the two kinds of mistake. A mistake at a read boundary yields an empty catalog or a
refused day: visible at once, costing a re-run. A mistake at the write boundary posts an entry to a
client's invoice: out in the world, and undoing it is a second write the user has to approve again.
Guarding both sides the same way either burdens every read with a gate nothing needs, or guards the
write with no more than the reads get.

## Decision

**Two boundaries, drawn on direction rather than on service.** The activity source, the work-item
source and the calendar sit on the *read* boundary. The timesheet provider sits alone on the *write*
boundary. A new service joins whichever side its direction puts it on; it does not get a boundary of
its own.

**Credentials belong at the write boundary and nowhere else.** The provider's credentials are
declared in the plugin manifest and marked sensitive. The read sources need none: the activity
source is local, the work-item catalog is read through a tool the user already authenticated, and
the calendar adapter reads through an application already signed in. A read source that would need
a token of its own — a Microsoft Graph calendar adapter, say — is a decision for its own ADR, because
it puts a secret on the side of the line where a leak buys an attacker nothing to bill with today.

**The confirmation gate belongs at the write boundary, in the invocation.** Every script that writes
to the provider requires `--confirm` and prints a preview without it. The gate is implemented once,
in `skills/daily/scripts/harvest_write.py`, and both writers declare their bodies to it. No read
script carries a gate, because nothing a read does needs undoing.

**A read boundary fails loudly and cheaply.** An unreachable source or an adapter that cannot read
is a non-zero exit with a reason, never a quiet empty result that a run would bill against as if it
were a day with nothing in it.

## Consequences

- "Everything but the provider is read", as ADR-0008 put it when the calendar arrived. Adding a read
  source is an adapter with no credentials and no gate; ADR-0008 is the worked example.
- Adding a second provider is a second writer behind the same command contract, not a second design;
  ADR-0006 holds that side.
- `skills/daily/tests/test_module_boundaries.py` holds the import direction: no provider script
  imports the activity-source client, and the shared zone module imports neither half.
  `tests/test_provider_neutrality.py` holds the vocabulary consequence: the provider's strings never
  ship as defaults.
- The read/write asymmetry is why a forgotten `--confirm` is a preview rather than an error, and why
  a `WOULD POST` line is the expected output of an unconfirmed run rather than a failure to fix.
- `CONTEXT.md` today carries a paragraph of status about how far each side of the line is abstracted
  ("the provider half is done to that line; the other halves are not"). That is this ADR's subject,
  not the glossary's, and moves here once this is accepted.

## Alternatives considered

**One adapter abstraction for all services**, with credentials and a confirmation step handled
uniformly. Rejected: a gate on a read costs every run a question that has no answer but yes, and a
credential on a read source widens what a leaked token can reach for no protection the read needed.

**One boundary per service** — four. Rejected: the distinction that changes how a boundary is
guarded is direction, not which product sits behind it. Four boundaries invite four gate
implementations, which is the "five loose scripts" ADR-0006 already rejected.

**No boundary at all — trust the prose.** The state before the `--confirm` flag: the instruction
said "never post without confirmation" and the scripts posted when called. Rejected on observation:
a frontmatter guard is honoured by some harnesses and dropped by others, and a rule that lives only
in text is a rule a run can skip. The gate moved into the invocation, where no harness can drop it.

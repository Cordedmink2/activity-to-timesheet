# ADR-0003: Named billables, not timesheet

**Status:** Accepted (recovered), **rationale not recovered.** The decision was enacted 2026-08-28
by `e074d13` ("Convert the repo into the billables plugin"). The original body was lost on 28
August (`docs/RECOVERY.md`). This was rewritten 2026-10-20 under #43 from what survives: the
decision and its consequences. The reason the name was chosen is not stated in that commit, in
#2, in #6 or in PR #16, and is not invented here. **Maintainer: if you remember why, add it under
Context and drop "rationale not recovered" from the status.**
**Context:** distribution and vocabulary. Related: [`CONTEXT.md`](../../CONTEXT.md),
[ADR-0001](./0001-the-plugin-is-the-only-copy.md), issues #2, #6 and #43.

## Context

The repository and its marketplace are named `activity-to-timesheet`, which describes the
mechanism: activity in, timesheet out. When the repo became a Claude Code plugin, the plugin needed
a name of its own, and that name is not free to change later. It is the namespace of every command
(`/billables:daily`), part of the install slug a user types once (`billables@activity-to-timesheet`)
and the key of the plugin cache on every machine.

Why `billables` rather than `timesheet`: **not recovered.**

## Decision

**The plugin is named `billables`.** Its skills are invoked as `/billables:<skill>` —
`/billables:daily`, `/billables:reconcile`, `/billables:setup`.

**The marketplace keeps the repository's name, `activity-to-timesheet`.** So the install is
`/plugin install billables@activity-to-timesheet`: the part before the `@` is the plugin and the
part after it is the marketplace it comes from. The two names are different things, and the split
is deliberate, not an inconsistency to tidy.

## Consequences

- **The name is hard to reverse.** Renaming the plugin renames every command, changes the install
  slug and moves the plugin cache, so every installed user must reinstall, and every document,
  issue template and test that names `/billables:` must change with it.
- **A reader will trip on the two names.** `activity-to-timesheet` is the repository and the
  marketplace; `billables` is the plugin and the commands. The README's install section shows both
  in one command so the relationship is visible where it is first met.
- **The vocabulary sits downstream of it.** `CONTEXT.md`'s terms (entry, block, work kind) describe
  billable work rather than a timesheet document, which is consistent with the name, whatever the
  original reason for it.

## Alternatives considered

**`timesheet`**, the name this ADR's filename sets against. Not chosen; the reason is not
recovered. The alternative is recorded so that a future rename is weighed against the cost above
rather than made because the other name once looked obvious.

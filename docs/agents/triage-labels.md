# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the actual label strings used in this repo's issue tracker.

| Label in mattpocock/skills | Label in our tracker | Meaning                                  |
| -------------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`             | `needs-triage`       | Maintainer needs to evaluate this issue  |
| `needs-info`               | `needs-info`         | Waiting on reporter for more information |
| `ready-for-agent`          | `ready-for-agent`    | Fully specified, ready for an AFK agent  |
| `ready-for-human`          | `ready-for-human`    | Requires human implementation            |
| `wontfix`                  | `wontfix`            | Will not be actioned                     |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label string from this table.

Edit the right-hand column to match whatever vocabulary you actually use.

## The other labels in use

Not triage roles, and not drift either:

- `bug`, `enhancement`, `documentation` — what the ticket is about. The two issue forms apply
  `skill` (a problem reported through a skill's own reporting path) and `enhancement`.
- `wayfinder:map` and `wayfinder:<type>` — the wayfinding infrastructure in
  [`issue-tracker.md`](./issue-tracker.md) § "Wayfinding operations".

The GitHub defaults `duplicate`, `invalid`, `question`, `good first issue` and `help wanted` are
unused and are to be deleted (#46); one still present is a deletion not yet run, not a label to
use. `wontfix` stays because it is a triage role above.

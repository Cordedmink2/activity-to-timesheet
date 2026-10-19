# ADR-0001: The plugin is the only copy

**Status:** Accepted (recovered) — the decision was enacted 2026-09-02 by #14 (`d5c99ed`, "Retire
the old install path"; `8acb1ed`, "Send a hand install to the plugin, not to the export"). The
original body was lost on 28 August (`docs/RECOVERY.md`); this was rewritten 2026-10-20 under #43
from that ticket, those commits and ADR-0004.
**Context:** distribution. Related: [ADR-0004](./0004-generate-the-shared-agent-skills-export.md)
(the export is generated from the plugin, never edited), [ADR-0005](./0005-the-setup-skill-replaces-llms-txt.md)
(the plugin is the only way in), issues #2 and #14.

## Context

Before the plugin, the skill reached a user by being copied: a hand install under
`~/.claude/skills/`, kept current by a publish script and a release checklist. Once the plugin
existed, keeping that path as a fallback looked free — someone who could not or would not install
the plugin still had a way in.

It was not free. Two installed copies of one skill means either can answer a `/daily`, and the
harness does not say which one did. A hand-installed copy does not update: it keeps working,
looks healthy and drifts further from the plugin with every release. This repo had already
shipped a public copy that ran two weeks behind the live one, and the only way to find out was to
notice the behaviour was old.

## Decision

**The plugin is the only copy of the skills a user installs.** There is one install path, the two
`/plugin` commands, and the old one is deleted rather than kept as a fallback: its install scripts,
its publish script, its separate version file and the checklist that kept the copies in step.

A harness that cannot install a plugin gets the shared Agent Skills export, which is *generated*
from the plugin (ADR-0004) — a build product with no edits of its own, not a second source. A user
who asks for a hand install is sent to the plugin, not to the export (`8acb1ed`).

## Consequences

- A fix ships by bumping the plugin version and nowhere else; `/plugin update` moves every user to
  it. There is no second place a release can forget.
- The guard is a test, not a habit. `tests/test_distribution.py::test_the_retired_install_path_is_gone`
  fails if a retired file comes back, and
  `::test_no_instruction_names_the_retired_install_path` fails if a document tells a reader to use
  it.
- A user on the old hand install has to remove it once; until they do, the stale copy can still
  answer. The README and the setup skill say so rather than leaving it to be discovered.
- Anyone who wants the skills outside Claude Code depends on the export being regenerated, which
  is why ADR-0004 makes that a script and a test rather than a step.

## Alternatives considered

**Keep the hand install alongside the plugin, as a fallback.** Rejected: it is the two-copies
failure this decision exists to remove, in a different shape. Each copy can answer, and the one
that is wrong looks exactly as healthy as the one that is right.

**Keep the hand install, generated from the plugin.** Rejected for Claude Code users: the plugin
already is that copy, with updates. The generated form is kept only for harnesses that have no
plugin system (ADR-0004).

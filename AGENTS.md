# AGENTS.md

Steering for agents **working on this repo**. Installing the billables plugin is a different job:
the two `/plugin` commands in [`README.md`](./README.md) install it — or, on a harness that cannot
install a plugin, `install/install_skill.{sh,ps1}` generates the shared Agent Skills export from a
clone — and the plugin's own `setup` skill walks the manual steps from there, verifying each one.

## Before reporting a change complete

Both of these, from the repo root, and paste what they print:

```
python -m pytest -q tests skills/daily/tests
pyright
```

Healthy is a single `passed` line and `0 errors`. The root matters: `skills/daily/pytest.ini`
collects the skill's own suite alone, so a run started in that folder skips every repo-level guard
and still reports green.

## Where a thing goes

- **Changing a skill, a reference or a script** → read
  [`docs/CONTRIBUTING.md`](./docs/CONTRIBUTING.md) first.
- **A finding from a run or a test** — a failure watched, a hazard measured, an option rejected →
  [`docs/skills/daily/decision-log.md`](./docs/skills/daily/decision-log.md), graded on its evidence
  rungs.
- **A decision that is hard to reverse, surprising without context and a real trade-off** → an ADR
  in `docs/adr/`. Fail one of the three and it stays in the log or the conversation.
- **A feature idea** → `intent/<feature>/intent.md`, paired with its spec issue. What the product is
  for and refuses to become is [`intent/foundational/intent.md`](./intent/foundational/intent.md).
- **A test** → `tests/` holds the repo-level guards; `skills/daily/tests/` ships with the skill and
  reads only what ships.

## Seen twice

- Read a configured value in the Bash tool and hand PowerShell the resolved literal. Published
  configuration reaches Bash alone; a PowerShell read comes back empty and nothing fails.

## Agent skills

### Issue tracker

Issues and specs live in this repo's GitHub Issues, via the `gh` CLI. See
[`docs/agents/issue-tracker.md`](./docs/agents/issue-tracker.md).

### Triage labels

The five canonical roles, with label strings unchanged. See
[`docs/agents/triage-labels.md`](./docs/agents/triage-labels.md).

### Domain docs

Single-context: `CONTEXT.md` and `docs/adr/` at the repo root. See
[`docs/agents/domain.md`](./docs/agents/domain.md).

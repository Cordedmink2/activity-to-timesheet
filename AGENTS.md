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

## Releasing

A version bump is the only thing that reaches an installed user — the plugin cache is keyed on
the manifest version, and `/plugin update` has nothing to move to while it is unchanged. Bump
`version` in `.claude-plugin/plugin.json` and add the matching `## [x.y.z]` heading to
`CHANGELOG.md` in the same change; `tests/test_distribution.py::test_every_version_marker_agrees`
holds the pair. Then tag the release commit. See [`docs/CONTRIBUTING.md`](./docs/CONTRIBUTING.md)
§ Releasing for the full steps.

The **maintainer** cuts the tag, by hand, once the `Checks` workflow is green on `main` for the
release commit — an agent bumps the version and writes the changelog entry, and stops there.
Pushing the tag runs `.github/workflows/release.yml`, which publishes the GitHub Release from the
matching `## [x.y.z]` section; a tag with no such heading fails there rather than publishing an
empty note.

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

- Run scripts and tests with an interpreter that answers `--version` with a version. A `python`
  that prints Microsoft Store install help and exits 49 is the Windows app-execution stub, not a
  broken script; the machine's `.context.md` names the real one.
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

# AGENTS.md

Steering for agents **working on this repo**. Installing the billables plugin is a different job:
the two `/plugin` commands in [`README.md`](./README.md) install it — or, on a harness that cannot
install a plugin, `install/install_skill.{sh,ps1}` generates the shared Agent Skills export from a
clone — and the plugin's own `setup` skill walks the manual steps from there, verifying each one.

## Before reporting a change complete

All three from the repo root, and paste what the last two print:

```
python -m pip install -r requirements-dev.txt
python -m pytest -q tests skills/daily/tests
pyright
```

Healthy is a single `passed` line and `0 errors`. Read pyright's verdict with
`pyright | grep -E '^[0-9]+ errors?'` — a version-upgrade notice trails the summary, so a `tail`
shows the notice instead of the answer. The root matters: `skills/daily/pytest.ini`
collects the skill's own suite alone, so a run started in that folder skips every repo-level guard
and still reports green.

## Releasing

A version bump is the only thing that reaches an installed user — the plugin cache is keyed on
the manifest version, and `/plugin update` has nothing to move to while it is unchanged.

Check `git tag --list` before bumping anything: while the newest `## [x.y.z]` heading carries no
tag, that version is still in progress, and a change ships by adding to its sections with the
manifest left alone. Bump when the newest heading is tagged — then bump
`version` in `.claude-plugin/plugin.json` and add the matching `## [x.y.z]` heading to
`CHANGELOG.md` in the same change; `tests/test_distribution.py::test_every_version_marker_agrees`
holds the pair. Then tag the release commit. See [`docs/CONTRIBUTING.md`](./docs/CONTRIBUTING.md)
§ Releasing for the full steps.

The **maintainer** decides when a version is cut, and says so for that version by name. With that
go-ahead an agent tags the release commit and pushes it, once the `Checks` workflow is green on
`main` for that commit. Absent a go-ahead for the version in front of it, an agent bumps the
version and writes the changelog entry and stops there — the decision is the maintainer's every
time, and a previous release's go-ahead does not carry to the next one.
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

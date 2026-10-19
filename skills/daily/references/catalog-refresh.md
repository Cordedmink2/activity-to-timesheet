# Catalog refresh

The skill relies on cached catalogs in the workspace's `.mcp/`. They're cached because the underlying APIs are slow (provider pagination, work-item-store queries) and the data changes slowly. Refresh when stale.

Two catalogs, and they answer different questions. The **assignment catalog** (the provider's, behind `timesheet-provider lookup`) says which projects the user may bill to and which tasks each offers — it is the authority behind every `project_id` / `task_id` / `billable` decision the rubric makes. A **work-item catalog** is optional and user-specific: it turns a work-item number seen in a window title into a description.

## When to refresh

`timesheet-provider refresh --age` says how stale the provider's catalog is without reading the adapter's storage: `AGE <days>` (whole days since it was last written) or `ABSENT`.

- `ABSENT` → refresh
- `AGE` of 7 or more → refresh (surface an `AGE` over 30 to the user first, unless `.context.md` preferences say refresh silently)
- The user mentions a project / work item the catalog doesn't have → refresh
- A classification fails to find a matching project even though the work-item pattern looks valid — `lookup` returns no match for the code → refresh

## The assignment catalog

The provider today is Harvest. What the rest of the skill needs *out* of the catalog is provider-neutral, and it is what `lookup` returns: for each project the user may bill to, its `code`, `project_id`, `name`, its `client`, and its `tasks[]` with each task's `id`, `name` and `billable`. A rule written against those survives a change of provider; one written against a task's literal name does not.

`timesheet-provider refresh` re-reads the user's assignments, **every page**, and rewrites the catalog `timesheet-provider lookup` reads; it prints `OK <n> projects` on stdout and a line per page on stderr. A member-scope token is enough — `refresh` and `lookup` need no admin scope. A failed refresh leaves the existing catalog exactly as it was and says so; a catalog that comes back with no projects at all is a failure, not a catalog written empty.

Where the catalog is stored, its endpoint, its headers, its paging and its page files are the adapter's, and live in the adapter's own notes (`scripts/provider/harvest/`), not here: nothing above the adapter reads them. The credentials come from wherever they were configured (see `references/first-run.md` § "First-run: configuration"); the adapter reads them and nothing else does, so configuring them once covers every command, and a catalog-hit `lookup` needs none.

**Read-replica lag (important).** The provider's catalog is eventually consistent: a just-created project can take minutes to surface, and neither a single refresh nor a row count is reliable for it. To bill against a brand-new project, run `timesheet-provider refresh --wait <code>`: it polls across minutes (`--attempts`, default 20; `--delay` seconds, default 15), writes the catalog it found and prints `OK <code>` once the code surfaces, or exits 6 with `ERR <code> did not appear` if it never does. It posts nothing. Don't treat a one-off miss as failure.

## User-specific work-item catalogs (optional)

If the user maintains a work-item dump (e.g. an active-incidents list from a CRM, a Jira/Linear export), `python scripts/refresh_catalogs.py --dataverse-only` can refresh it — it is the read side's catalog, not the provider's. The exact query is user-specific — see `.context.md` for the user's work-item-source configuration.

The script's design assumes:
- Output goes to `.mcp/<catalog>.txt` or `.mcp/<catalog>.json`
- Format is tabular text or JSON — readable line-by-line by downstream classifiers
- Auth uses whatever CLI the user has configured for their backend (e.g. `pac` CLI for Dataverse, `gh` for GitHub Issues)

### Dataverse (the one adapter that ships)

If you create work tickets in a **Dataverse / Dynamics 365** org that sync to Harvest as projects, you
can enable ticket-number → title lookups by setting two values:

```
DATAVERSE_URL=https://yourorg.crm6.dynamics.com/
PAC_AUTH_PROFILE=YourPacAuthProfileName
```

These two are deliberately **not** declared plugin configuration: they belong to one org's setup
rather than to every install, so `/plugin configure billables` never asks for them. Where they go
depends on which install you have:

- **Plugin install:** set them as ordinary environment variables. Not in a `.env` inside the plugin
  folder — a `/plugin update` overwrites that folder, and the skill's own diagnostic tells you to
  delete any `.env` it finds there, because on a plugin install one silently outranks the
  configuration dialog.
- **Exported install**: the skill root's `.env`, alongside the Harvest keys.

The profile must be a **named** one — the refresh selects it with `pac auth select --name`, and
`pac auth create` without `--name` creates an unnamed profile it can never select. Authenticate with
`pac auth create --name YourPacAuthProfileName --environment https://yourorg.crm6.dynamics.com/`, or
name an existing profile without re-authenticating: `pac auth name --index <N> --name <name>`.

This requires the [Power Platform CLI](https://learn.microsoft.com/power-platform/developer/cli/introduction)
(`pac`) installed and authenticated. **Leave both blank to skip it** — everything else works
Harvest-only.

If you instead connect Dataverse through an MCP server (e.g. via the `dataverse` plugin's `dv-connect` skill), register it **scoped locally to this workspace** — run `claude mcp add -s local …` from this folder, never user scope — so a single-env server can't follow you into your other client repos.

## Creating a backend work item to bill against

A block that belongs to new work with no project yet is `references/new-client-work.md`'s procedure — the work item is created in the user's backend and syncs to the provider as a new project. What this file adds is the read-replica lag above: the new project surfaces in the assignment catalog minutes later, so poll with `refresh --wait <code>` rather than refreshing once.

## Sanity checks after refresh

- `refresh` reports more than 10 projects → looks reasonable for most consultants
- Work-item catalog file has the expected row count and column headers → looks reasonable
- If either looks empty / wrong, restore the previous file from backup before overwriting

`timesheet-provider refresh` does the provider's half in one go, and `refresh_catalogs.py --dataverse-only` the work-item half.

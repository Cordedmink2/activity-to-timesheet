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

## The work-item source (optional)

`python scripts/refresh_catalogs.py` refreshes the catalog of the user's work items into
`.mcp/work_item_catalog.txt` (a header row, then one work item per row). It is the read side's,
not the provider's: no confirmation gate and no credential (ADR-0007). Which system it reads
and every fact about the user's account come from `Timesheets/.context.md` § "Work-item
source" — the plugin ships none of them.

- **Nothing configured** (no section, or only the template's placeholders): the run says no
  work-item source is configured, writes no catalog and exits 0. It never writes an empty
  catalog that looks healthy, and a source that answers with no work items is a failure
  (exit 4) that leaves the existing catalog as it was.
- **The old shape**: `DATAVERSE_URL` and `PAC_AUTH_PROFILE`, in the skill `.env` or the
  environment, were the configuration before #37. With no section in `.context.md` the run
  stops (exit 3) and names each one and the line that replaces it; with a section it carries on
  and says the old ones are ignored. `DATAVERSE_URL` → `Environment URL`, `PAC_AUTH_PROFILE` →
  `Auth profile`.
- **The section** is `- Label: value` lines under `## Work-item source`. `Adapter` selects the
  kind of system. `dataverse` reads a Dataverse / Dynamics 365 table through the Power Platform
  CLI (`pac`) the user has already authenticated, and needs `Environment URL`, `Auth profile`,
  `Entity`, `Number column`, `Title column`, `Modified column` and `State column` (zero while the
  item is open). A missing one is refused by name; none is defaulted.
- The auth profile must be a **named** `pac` one — the refresh selects it with `pac auth select
  --name`, and restores the user's active profile afterwards (and says so if it could not).
  `pac auth create --name <name> --environment <url>`, or name an existing one with
  `pac auth name --index <N> --name <name>`.
- A `### Case creation` subsection of the same section is the user's convention for creating a
  work item: read it with `references/new-client-work.md`.
- Adding another kind of system is one module in `scripts/work_items/adapters/`; nothing else
  changes.

If the user connects Dataverse through an MCP server instead, register it **scoped locally to this workspace** — `claude mcp add -s local …` from this folder, never user scope — so a single-env server can't follow you into your other client repos.

## Creating a backend work item to bill against

A block that belongs to new work with no project yet is `references/new-client-work.md`'s procedure — the work item is created in the user's backend and syncs to the provider as a new project. What this file adds is the read-replica lag above: the new project surfaces in the assignment catalog minutes later, so poll with `refresh --wait <code>` rather than refreshing once.

## Sanity checks after refresh

- `refresh` reports more than 10 projects → looks reasonable for most consultants
- Work-item catalog file has the expected row count and column headers → looks reasonable
- If either looks empty / wrong, restore the previous file from backup before overwriting

`timesheet-provider refresh` does the provider's half in one go, and `refresh_catalogs.py` the work-item half.

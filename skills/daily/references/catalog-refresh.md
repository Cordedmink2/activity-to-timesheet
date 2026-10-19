# Catalog refresh

The skill relies on cached catalogs in the workspace's `.mcp/`. They're cached because the underlying APIs are slow (provider pagination, work-item-store queries) and the data changes slowly. Refresh when stale.

Two catalogs, and they answer different questions. The **assignment catalog** says which projects the user may bill to and which tasks each offers — it is the authority behind every `project_id` / `task_id` / `billable` decision the rubric makes. A **work-item catalog** is optional and user-specific: it turns a work-item number seen in a window title into a description.

## When to refresh

- Cached file is missing → refresh
- `.mtime` is older than 7 days → refresh
- The user mentions a project / work item the catalog doesn't have → refresh
- A classification fails to find a matching `project.code` even though the work-item pattern looks valid → refresh

## The assignment catalog

The provider today is Harvest, and this section describes its API, so it names it. What the rest of the skill needs *out* of the catalog is provider-neutral: for each project the user may bill to, its `id`, `code`, `name`, its `client.name`, and its `task_assignments[]` with each task's name and `billable` flag. A rule written against those fields survives a change of provider; one written against a task's literal name does not.

**Endpoint:** `GET https://api.harvestapp.com/api/v2/users/me/project_assignments?per_page=100&page=<N>`

**Why this endpoint specifically:** many users' Harvest PATs are *member-scope* (`expenses:read:own`, `timers:read:own/write:own`). Admin endpoints like `/projects` and `/clients` return 403 for member-scope tokens. The `/users/me/project_assignments` endpoint is self-scoped and returns the same shape — project + client + task_assignments — for projects the authenticated user is personally assigned to. Works on both member and admin tokens.

**Auth headers:**
```
Harvest-Account-ID: <user's account id>
Authorization: Bearer <HARVEST_API_KEY>
User-Agent: <something descriptive>
```

The credentials come from wherever they were configured — the plugin's declared configuration, or an exported install's `.env` (see `references/first-run.md` § "First-run: configuration"). `scripts/refresh_catalogs.py` resolves them through the same shared `harvest_client.load_creds()` helper the other provider scripts use, so configuring them once covers everything.

**Pagination:** loop pages at `per_page=100` until `next_page` is null. Most consultants have <1000 assignments total.

**Output:** save raw page JSON to `.mcp/harvest_assignments_p<N>.json` (and `harvest_assignments.json` for page 1). Don't reformat — downstream readers expect the provider's own shape.

**Read-replica lag (important).** This endpoint is eventually consistent: identical back-to-back requests can hit a fresh replica or a lagging one, and the lagging one can even report the new `total_entries` while still serving stale rows. So a single refresh — and the row count — are NOT reliable for a *just-created* project. No client-side trick fixes a bulk pull. To bill against a brand-new project, call `refresh_catalogs.wait_for_project(code)`, which polls across minutes (each read re-rolls the replica) and returns the assignment dict once the code surfaces. Don't treat a one-off miss as failure.

## User-specific work-item catalogs (optional)

If the user maintains a work-item dump (e.g. an active-incidents list from a CRM, a Jira/Linear export), `scripts/refresh_catalogs.py` can refresh it. The exact query is user-specific — see `.context.md` for the user's work-item-source configuration.

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

A block that belongs to new work with no project yet is `references/new-client-work.md`'s procedure — the work item is created in the user's backend and syncs to the provider as a new project. What this file adds is the read-replica lag above: the new project surfaces in the assignment catalog minutes later, so poll with `wait_for_project(code)` rather than refreshing once.

## Sanity checks after refresh

- Assignment catalog has >10 entries → looks reasonable for most consultants
- Work-item catalog file has the expected row count and column headers → looks reasonable
- If either looks empty / wrong, restore the previous file from backup before overwriting

`scripts/refresh_catalogs.py` does all the above in one go.

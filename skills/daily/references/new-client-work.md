# Billing a block to brand-new client work (no project yet)

Rare path: a block belongs to new work the timesheet provider has no project for. The user creates a work item in their backend (a case, a ticket, a story) that syncs to the provider as a new project (the project's code is the work-item id).

## Creating the work item

How is the user's own — it is in `Timesheets/.context.md` § "Work-item source", under `### Case creation`: the helper or form, what to supply, what the system assigns, and any naming trap. Read it and follow it; if it is missing, ask the user how they create one rather than guessing at a system. Nothing in this plugin creates a work item.

- Confirm the resolved customer and title with the user before anything is created.
- Authentication that needs an interactive sign-in (a device-code URL) cannot be completed headless. Ask the user to run that one command in their own terminal, take the work-item number it prints, and do the billing yourself — posting to the provider is always headless. Don't loop trying to make silent auth work.
- Don't pipe a run that prompts for sign-in through `head` or `grep`: the filter buffers its output, so the prompt never appears and the run reads as a hang. Redirect to a file, or use `grep --line-buffered`.
- The bulk catalog of work items is a different path: `python scripts/refresh_catalogs.py`, in `references/catalog-refresh.md`.

The replica lag the new project's catalog entry is subject to is `references/catalog-refresh.md` § "The assignment catalog", under **Read-replica lag**.

## After creating

**Mind what the user's convention says about reference fields** — a reference put in both the title and a second field the sync appends to the project name ends up in the client-facing name twice. The convention in `.context.md` records any such trap; follow it.

**Post the other blocks now**, then use `timesheet-provider refresh --wait <code>` to poll for the new project (its catalog entry lags a few minutes and a single refresh isn't reliable), and bill the deferred block once it surfaces.

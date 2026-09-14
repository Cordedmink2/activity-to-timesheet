# Classification rubric

Goal: give each proposed **block** its attribution — `(client, project_id, task_id, billable)` — and a `confidence` rating. A block is local and still redrawable; it becomes an **entry** only when Step 9 posts it.

The provider's own strings never appear here. This rubric decides a **work kind** — one of the seven in "Work kind and task selection" below — and the user's `.context.md` maps that to the task their provider actually offers. Classifying a block needs this file and, once one comes out flagged, `references/disambiguation.md`; the repo's `CONTEXT.md` carries the same vocabulary for whoever is *changing* the skill, and is not something a run has to have.

**`Timesheets/.context.md` is the source of truth.** It holds the per-user facts:
- Active client profiles + signals (Edge profile names, URLs, ChatGPT projects, VS Code workspaces, repo paths, SharePoint subdomains, work-item prefixes)
- Internal-colleague + external-contact names
- The **work kind → task** mapping, and billing-convention *overrides* (per-project conventions, note-style examples in the user's voice)
- User-specific personal-browsing recognizers (on top of the generic exclusion categories below)
- Preferences (AFK threshold, activity floor, active/thin bands, lunch window, etc.) — the timezone is *not* here, it is plugin configuration

This file contains only the **generic heuristics** for *applying* `.context.md` to event data. If a rule below contradicts `.context.md`, `.context.md` wins.

## Signal hierarchy (most → least reliable)

### 1. Work-item match (HIGH confidence)

If any window title, URL, or terminal task name within the block contains a string matching the user's work-item pattern (typically `[A-Z]{2,4}\d{3,}S?` — but check `.context.md` for the exact regex if customised):

1. Look up the prefix under `.context.md` § "Active client projects" — each client's signal list carries its work-item prefixes — to identify the client. A prefix that resolves to more than one client there is settled by grouping the assignment catalog on `project.code` prefix → `client.name`, not by picking the first match.
2. Look up the same string against `project.code` in the assignment catalog (`.mcp/harvest_assignments*.json`) to get `project.id` and `task_assignments[]`.
3. If the user maintains a work-item catalog file (e.g. a dump of active incidents), look up the title there for the description.
4. Direct hit → HIGH confidence.

**Caveat — a work item existing ≠ today's billing target.** A work-item catalog lists *all* known items; thematic match isn't billing match. The user may be supporting a colleague's work item, doing release-level work that bills to a different project, or working on something not yet tracked. When the work item isn't named explicitly in window/URL titles, ask — don't pick the most "thematically matching" row from the catalog.

A trailing `S` (or other suffix) on a work-item number often indicates **Support work** — check `.context.md` for the user's convention. If so, tag the description as `[Support]` but use the same `project_id` / `task_id`.

### 2. Edge profile in window title (HIGH confidence for browser activity)

Windows ending in `… - <ProfileName> - <UserDisplayName> - Microsoft Edge` (or older format `… - <ProfileName> - Microsoft Edge`): the profile name maps directly to a client. (`<UserDisplayName>` is the user's Edge profile display name — discover it from window titles in the first session.) See `.context.md` "Active client projects" sections for the current profile → client mapping. If a profile isn't listed there but window content otherwise indicates a known client, follow the content signal. New profiles → propose adding them to `.context.md`.

### 3. Teams chat / call titles (HIGH confidence for Teams events)

Teams windows follow this pattern: `Chat | <Name>[, <Name>…] | <TenantName> | <user-email> | Microsoft Teams`. A meeting or a call is titled `Meeting | <name> | …` or `Call with <name> | …` instead — the meeting-title pattern `SKILL.md` Step 3 uses as a soft boundary, and the one `scripts/calendar_day.py` uses to decide whether a calendar event was attended; a `Chat | …` window is never that evidence.

- Title contains an **internal-colleague** name (see `.context.md` "Internal colleagues") → *probably* internal, but **don't auto-classify a meeting as internal just because the participants are all colleagues**. Internal teammates regularly hop on calls to discuss client work. Before billing to the internal-admin project, peek at a screenshot during the meeting to check the shared screen / agenda — if it shows a client environment, architecture diagram, work item, or repo, bill the meeting to *that* client's project instead. Only fall back to internal-admin when the screenshot shows internal artefacts (internal wiki, the consultancy's own CRM, AI training material, timesheet work) or is genuinely unrevealing.
- Title contains a **known external contact** (see `.context.md` "Known external contacts") → use the mapped client. The `(External unfamiliar)` Teams flag is often stale; treat it as a soft warning, not a hard rule.
- Title contains an **unrecognised external** with no client signal → ask the user; don't auto-classify.
- **Recurring meeting names** → see `.context.md` "Notes on inference" or "Recurring meetings" for the user's canonical attribution.

### 4. App-stack signal (MEDIUM confidence)

VS Code workspaces, Obsidian vaults, repo paths, ChatGPT project names, and other app signatures map to **codebases** that belong to a client — see `.context.md` for the current mapping.

**Codebase ≠ project.** A single client codebase can serve multiple projects. The repo path tells you the client family; the work-item context (the active item, commit message, who's being supported, what's being released) tells you the specific project.

**Focused window ≠ active attention (autonomous agents + multi-monitor).** The window-watcher logs only the *foreground* window. When a Claude Code agent runs unattended (`auto mode`, a background agent) in a VS Code window, that window counts as "focused" for the agent's whole runtime — while the user's real work is a *different* client's session on another monitor. This inflates the `activity_timeline.py` rollup minutes for the agent's workspace and drops the parallel client work. Signal: a screenshot showing `auto mode on ← 1 agent` or `Waiting for … background agent to finish`. Action: when one workspace dominates the rollup on a multi-monitor day, read the *other* monitors (`_m1`/`_m3`) at that timestamp before trusting the per-category minutes, and treat that day's per-client hours as a user-confirmed split rather than a rollup readout. The same effect has a mirror image on the AFK side: a low `active_ratio` while an agent runs is supervision, not absence. Supervised agent time is billable, so check the other monitors for the agent's output before shrinking a thin block or dropping a stretch on ratio alone.

**Long agent-CLI sessions poison the window title.** A running `claude` session keeps one editor tab in focus (`CLAUDE.md`, `AGENTS.md`, a plan `.md`) for its whole duration while the actual work happens in the terminal, the browser, or on another monitor. The *file name* in such a title is not a work signal and will mis-attribute whole blocks. The VS Code *workspace* tag (`… - <Workspace> - Visual Studio Code`) stays valid, but when a block is titled with these files, resolve the client from screenshots — and check every monitor, not just the one showing the focused app. The same applies to any other `*.md` title that isn't obviously one of these three: confirm the file actually lives in the client's repo (`git log --follow -- <path>` or a plain find) before trusting it — a Claude Code skill's own reference file (methodology docs, checklists) can be open in the editor while a *different* workspace has focus, and its name alone will look like project documentation.

### 5. Environment identifier (MEDIUM confidence)

URLs in browser tabs (Edge / Firefox / Chrome) expose Dynamics environments, Azure DevOps orgs, SharePoint subdomains, ChatGPT project slugs, etc. — see `.context.md` for the user's URL → client mapping. The URL fingerprint is usually unambiguous; if a new URL pattern appears that maps to a known client, propose adding it to `.context.md`.

**A long browser window row is not one unit of work — and it is not evidence about the other monitors either.** Edge and Chrome title a window for its *foreground* tab and append `and N more pages`, so one `uncategorized` window event can span hours while several clients' tabs sit live behind it, and the web-watcher rows inside that span are a sample rather than a complete list of what was open. Two consequences, and the second is the one that costs money. A brief client signal in a single web row inside the span is a **lead to check, not a switch point** — resolve it against the other monitors (§3, "Focused window ≠ active attention") before splitting anything, because a 30-second tab check during a call looks identical in the web rows to the start of a new work run. And a long browser row says nothing about what a *meeting* was doing meanwhile: Teams on another monitor never reaches the window watcher at all, so a span that reads as solo browsing with a thin `active_ratio` can be a call, where a low ratio is expected and no shrink is warranted. (Observed 2026-08-21: a 124.7-min `msedge.exe | ChatGPT and 8 more pages` event ran the whole length of an 85-minute Teams call visible only on another monitor; two brief second-client tab hits inside it were first read as an end-of-block switch and billed as one, both wrongly.)

**The identifier is often not in the window title at all.** Admin tools that connect to a client environment — XrmToolBox, database/API clients, RDP sessions, CLI auth profiles — carry a fixed product name in the title and show the environment only on screen: a connection dropdown, a status bar, a profile list. The connected environment decides the client; the tool name never does, and neither does the workspace behind it. **Flag these on sight** — don't wait for the title to look ambiguous, because it never will. A block titled plain `XrmToolBox` reads as classified, so nothing downstream ever asks about it; the flag raised here is the only thing that gets it looked at. `references/disambiguation.md` is what then resolves it, and a screenshot of the connection is the only thing that can.

### 6. `claude.exe` / terminal adjacency rule

Pure `claude.exe` / `WindowsTerminal.exe` (or other AI-assist clients) — apply the surrounding-context rule:

- Pure terminal time adjacent to a client app stack → attribute to that client.
- Terminal adjacent to timesheet-automation paths (`Claude/Scheduled/`, `Pictures/WorkScreenshots/`, `Timesheets/`) → the user's internal-admin project.
- **Adjacency stops at an admin tool.** Where the neighbouring block is one of §5's tools that shows its environment only on screen, this rule does not reach it: connecting to a different environment is frequently the switch point itself, so the neighbour is the wrong answer by construction.
- Claude Code task names visible in terminal titles (e.g. `✳ <slug>`) are useful signals but **the slug usually names a feature, not a client** — e.g. `hardcode-confidential-team-lookups` tells you *what* is being worked on, not *who* it's for. Triangulate with the surrounding Edge profile, repo path, or open client environment to pin the client. A slug that triangulates against nothing is a 🔸, raised here; `references/disambiguation.md` has what to do with one.

## A day that alternated between two clients

A block whose signals flip between clients is not classified by this file at all: finding the boundary is a procedure, not a signal, and getting it wrong is the costliest misattribution there is. `references/disambiguation.md` § "Interleaved days" owns it — what triggers it, how to spend screenshots on it, and what to do on a day that has no boundary to find.

## Work kind and task selection

**This table owns the activity → work kind mapping**; `SKILL.md` Step 4 points here rather than restating it. It stops at the work kind, because the task's *name* belongs to the user's provider and cannot be shipped: the seven work kinds are the same for everyone, and no two accounts spell their tasks the same way.

Resolution order:

1. **`.context.md` overrides win.** Check the user's "How I bill" / preferences section first — it names a default task for client work, per-project conventions (a specific default task for the internal-admin project, say), and any hardcoded `project · task` pair under a client's section. A per-client hardcoded task beats the mapping below — if the client entry pins the development task, a design-doc-heavy block still bills there, not to documentation.
2. **The work kind follows the block's *dominant* activity**, not its incidental surfaces. A dev block that included reading docs and a 5-min chat is still `Development`. Only give a block `Meeting` when the block *is* a call/meeting.
3. Read the work kind off the evidence:

| Dominant block activity | Work kind |
|---|---|
| A Teams meeting / call | `Meeting` |
| Code / config / build / deploy / bug fixing | `Development` |
| Docs / wiki / SOW writing | `Documentation` |
| Planning, backlog grooming, coordination | `Project management` |
| Testing, QA, smoke tests | `Testing` |
| Sustained pure read-only analysis, **no edits at all** | `Investigation` (rare — any config/code change makes it `Development`) |
| The timesheet itself, internal admin tooling, training | `Internal admin` |

4. **Turn the work kind into a task name.** Three sources, in this order — the first that answers wins, and the order is the whole point of the step:

   a. **The work kind's row in `.context.md` § "Work kinds"**, where that table exists and the row is filled in. The user's own mapping, and the cheapest correct answer.
   b. **Otherwise, the task in *this project's* `task_assignments[]` whose name most nearly means that work kind.** `harvest_lookup.py` returns them. Read the mapping off the account rather than guessing a name — these are the tasks that demonstrably exist.
   c. **Otherwise, `.context.md`'s default task** for client work, or for `Internal admin` its default task for internal/admin time.

   **(b) sits before (c) deliberately, and getting that backwards is the failure this step exists to stop.** An install predating the "Work kinds" table has a default task and no rows — both (a) and (c) are "unanswered" and "answered" at once. Taking the default there would collapse `Meeting`, `Documentation`, `Testing` and `Project management` all onto the development task, which is worse than what the rules did before the table existed. (c) is the catch-all for when (b) finds nothing near, not a shortcut past it.

   If two tasks are equally near under (b) and none is obviously right, flag the block 🔸 and ask.
5. **Whatever the source, the task has to be in this project's `task_assignments[]`** — that list is the authority on what the project offers. A task `.context.md` names but this project doesn't have falls back to (b) against what it does have; say in the presentation that you substituted. **Don't invent tasks** — a name that isn't in `task_assignments[]` doesn't exist as far as the provider is concerned, and posting it fails.
6. **A mapping you had to work out is a fact `.context.md` is missing.** Propose the row at Step 11, so the next run reads it rather than re-deriving it. (b) is how the skill works on day one; the table is how it stops costing anything.

## Billing conventions (defaults — `.context.md` overrides win)

- **Bill by work item, not by window or app.** One sustained block of work on one work item = one entry, even when the surface switched between IDE, browser, Teams, and admin portals. Don't fragment by window-title change.
- **The timesheet run itself lands *after* the last block it can bill.** Doing the timesheet is real `Internal admin` time, but it happens at the end of the day — usually in the dead stretch past `work_end`, which is unbillable anyway. The failure is back-dating it onto the last live block: the day's final 20-30 min get labelled "timesheet & expenses, non-billable" while the screenshots across that window show ordinary client work, and the client silently loses the time. **Before booking — or verifying an already-posted — timesheet-admin entry, read a screenshot inside the window and confirm a timesheet or provider surface is actually on one of the monitors.** Verification is the easier half to skip: Step 1's already-covered branch checks coverage and idle ratio, and both pass on a block that is correctly timed and booked to the wrong project. If it shows client work, bill the client; put the admin time where it really happened, or leave it off if that stretch is already excluded. Observed on 2026-08-18: 17:30-17:54 posted as internal admin, four captures across it showing client access-sync work and no timesheet UI on any monitor.
- **Never silently bill an abandoned-task block.** Setup/sign-in/install work that ended without a client deliverable and a pivot elsewhere → surface it; default to internal-admin non-billable unless the user says otherwise. This is a billing default, not a disambiguation step: such a block is often attributed confidently — you know whose tenant you signed into — so it never gets flagged, and a rule that waited for a flag would never be read.
- **A matching work item older than ~1 week → make a NEW one, don't reuse it.** The old one is likely closed or already invoiced. Create a fresh one (`references/new-client-work.md`) and bill to that; only reuse a genuinely recent / still-open item.

## Writing the entry note (description)

Notes go to clients on invoices — `SKILL.md` carries the hard rule (client-readable, SOW test). Style defaults:

- **5–15 words, outcome-focused.** Lead with the result, not the tools or files: "Resolved the certificate import interface bug", not "Debugged CreateCertificateRequestsHandler.cs".
- **Reference the specific work item** (e.g. `US1031`, `Bug 1127`) over just the parent SOW. The numbers surface in CRM record titles, ADO URLs (`_workitems/edit/<id>`), and PR titles (`feat(SOW15 #1031): …`). Name the parent SOW only as context, never as a substitute for the work item.
- **Internal artefact names leak via the file or tool in focus — translate before writing the note.** Code file names → the client process they serve ("complaint creation process", not `ComplaintRaisedService.cs`); repo/knowledge tooling (wiki scripts, knowledge base) → the project area it serves, or "project documentation"; agent/config files (`AGENTS.md`, `CLAUDE.md`, plan `.md`s) → never named.
- The user's own voice and worked examples: `.context.md` "How I bill".

**Sourcing a work-item number: delegate the dig to a subagent.** A window title rarely names the exact US/Bug number, but `git log` in the client's repos at the block's timestamps often does, and a subagent can search several repos and a project wiki in parallel without spending the main session's context on file listings and commit dumps. Give it: the repo paths, the local-time windows in question, and what each window's window-titles/screenshots showed (so it knows what to corroborate). Tell it explicitly not to invent a number — a wrong ADO number on a client invoice is worse than a generic description — and to report its evidence (commit hash + message, or wiki doc title) alongside each finding so you can judge confidence yourself rather than trust its say-so.
- A subagent finding a file open in a workspace doesn't confirm it's that client's file — have it check the file's actual repo history, not just the window title, before citing anything from it.

**Billable status comes from the task assignment, not the task name.** `task_assignments[N].billable` in the assignment catalog is authoritative. A `(NB)`-style suffix is a naming convention hint — some non-billable tasks (e.g. everything under an internal admin project) don't carry one. When the work kind is `Internal admin`, pick a task whose `billable` is `false` in the catalog.

## Confidence rating

Every block leaves this file with one, so the three stay here rather than with the ladder — a rating that only loaded once something was already flagged could not be what raises the flag.

- **HIGH** — direct work-item hit, OR two corroborating signals (e.g. Edge profile + URL agree).
- **MEDIUM** — single signal (profile, URL, or app), no contradictions.
- **LOW** — conflicting signals, or signal absent but block is non-trivial duration. Mark with 🔸 and ask the user — `references/disambiguation.md` is how.

## Exclusions (NEVER bill)

Generic categories, always excluded:

- Flight/travel searches and holiday planning
- Social media scrolling (FB / IG / X / LinkedIn), news, weather, shopping, personal email
- Pomodoro/timer overlay pages (the timer isn't the work)
- Home admin (router, smart home, NAS)

`Timesheets/.context.md` "Personal browsing patterns to exclude" adds the user's specific recognizers on top and wins on any conflict.

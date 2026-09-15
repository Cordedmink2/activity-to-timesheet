# activity-to-timesheet

A [Claude Code](https://claude.com/claude-code) skill that reconstructs your workday from
[ActivityWatch](https://activitywatch.net/) + periodic screenshots, classifies the activity into
per-client time blocks, shows them to you for review, and (only after you confirm) posts the entries
to [Harvest](https://www.getharvest.com/).

It's built for consultants who bill **multiple clients out of one machine** and are tired of
reconstructing "what did I actually do today?" from memory. ActivityWatch records the raw activity;
this skill turns it into a reviewable, billable timesheet.

> **You stay in control.** Nothing is ever posted to Harvest without an explicit "yes". The skill
> proposes; you approve.

---

## Install

This repo is a plugin marketplace holding one plugin, `billables`. From inside Claude Code:

```
/plugin marketplace add Cordedmink2/activity-to-timesheet
/plugin install billables@activity-to-timesheet
```

Take the **user**-scope install if you are offered the choice, so the plugin is enabled in every
directory you work in. A **local**-scope install is bound to the one folder you installed it from:
start a session anywhere else and the plugin is disabled there, its session hook never runs, and
every command reports your credentials missing however carefully you filled them in.
That one is worth avoiding rather than diagnosing — it looks identical to having configured
nothing, and it is missing in *both* shells, so none of the usual fixes apply.
`claude plugin list` shows which scope you got and whether the plugin is enabled where you are.

That gives you `/billables:daily`, `/billables:reconcile` and `/billables:setup`, and asks you
for your own details, once:

| | |
|---|---|
| **Harvest account ID** and **personal access token** | From https://id.getharvest.com/developers. Both are marked sensitive, so Claude Code keeps them in its own credential store — the OS keychain on macOS, `~/.claude/.credentials.json` elsewhere — rather than in a file inside the plugin or in `settings.json`. |
| **Your timezone** | Optional. An IANA name (`Europe/London`, `Pacific/Auckland`); it decides where your day starts and ends. Blank means your machine's own zone, and every run then says the zone came from the machine — so a wrong one is seen, not billed from. There is no fixed default: a machine whose zone cannot be read stops and asks, because a guess would date someone else's timesheet wrong without anything visibly failing. |
| **ActivityWatch address** | Optional. Leave blank unless AW runs somewhere other than `http://localhost:5600`. |
| **Screenshot directory** | Optional. Blank means `~/Pictures/WorkScreenshots`. |
| **Workspace directory** | Optional. Blank means the folder you run Claude Code from, if it already looks like a workspace (`.mcp/` or `Timesheets/`) — which is the normal case. Set it if you start sessions elsewhere: a plugin is never installed *inside* a workspace, so there is no second place to fall back to. Answer it after step 6, with `/plugin configure billables`. |
| **Read my Outlook calendar** | Optional, off by default. On, the `daily` skill reads your default calendar in classic Outlook (Windows only) as a fourth source — a calendar event your activity corroborates is drafted, one it does not is put to you as a question. Off is exactly today's behaviour. |

To change any of them later: `/plugin configure billables`.

### Then run `/billables:setup`

It walks you through installing ActivityWatch, the browser extension and the title tags for the
profiles that belong to one client, writes your category rules for you, sets up the screenshot task
and settles whether your Outlook calendar is read — and *verifies each one before moving on*, which is the difference
that matters: every one of those
steps can look like it worked and have done nothing, and the symptom arrives days later as an
empty timesheet. It tells you when setup is finished.

That is the whole path — you don't need to clone this repo, read the rest of this file, or run a
script by hand. What is left afterwards is scaffolding your workspace
([step 6](#6-scaffold-your-workspace)) and filling in your `.context.md`
([step 7](#7-fill-in-your-contextmd)), which the `daily` skill's first run does with you.

> **Heads-up on antivirus / EDR.** A scheduled task that silently screenshots every few minutes
> looks like spyware to endpoint security, so it (or `pip install`) may be blocked mid-setup. The
> `setup` skill catches that where it happens, and hands you a request your security team can
> action: the `WorkScreenshots` task plus the interpreter and script paths read back off the
> registered task, never a folder-wide exclusion. It establishes that the step really was blocked
> before sending you anywhere.

Paths below of the form `$HOME\.agents\skills\billables-daily\…` are where the **exported** copy
lives — the shared Agent Skills directory, for harnesses that aren't Claude Code (see
[step 5](#5-install-the-skill-on-a-harness-that-isnt-claude-code)). On a plugin install, substitute
the plugin's own skill directory; the skill itself resolves this at run time and never needs to be
told.

---

## How it works (the short version)

1. **ActivityWatch** runs locally and logs which app/window/browser-tab is in focus, plus when you're
   away from the keyboard (AFK).
2. The **"URL in Title" browser extension** stamps a short **client code** into every tab's title
   in a browser profile you use for one client (e.g. `… - [ACME]`), so browsing that carries no
   other clue still says who it was for.
3. **ActivityWatch category rules**, which the plugin writes and keeps current from the signals you
   declare, label activity per client — the work-item prefixes, environment addresses and workspace
   names your work actually contains, with that profile tag as the fallback.
4. A small **screenshot grabber** takes a periodic screenshot during work hours, used only to
   disambiguate activity that the window title alone can't pin to a client.
5. The **skill** reads all of the above, drafts a timesheet, shows it to you, and posts confirmed
   blocks to Harvest.

---

## Updating

On a **plugin install**, `/plugin update billables` is the whole story.

On the **exported copy**, you update by getting the latest repo files and regenerating it:

- **If you cloned the repo**, from inside your clone:
  ```powershell
  git pull
  pwsh -File install\install_skill.ps1        # macOS/Linux: ./install/install_skill.sh
  ```
- **If you have no local clone**, just ask your agent to *"update the billables skills from the
  latest activity-to-timesheet repo"* — it'll fetch the current version and regenerate the export.

Regenerating never touches your workspace or your `.context.md`, and your `.env` is kept where it
is. Everything else in each `~/.agents/skills/billables-*` directory is **rewritten from the
plugin**, so a file removed upstream leaves your copy too — there is no stale reference left
behind, and nothing to clean out before a reinstall.

> **Updating from an earlier version?** See [CHANGELOG.md](./CHANGELOG.md) for what changed in
> each release and whether you need to act.
>
> **Re-run the screenshot setup afterwards.** The install script only
> copies files — it installs no Python dependencies. Older versions captured a single stitched image
> with Pillow alone; the current per-monitor capture also needs [mss](https://python-mss.readthedocs.io/).
> Because the `WorkScreenshots` task points at the in-place script, it starts running the new code on
> its next tick and will fail with `No module named 'mss'` (silently, into `capture.log`) until `mss`
> is present. Re-run the screenshot setup once to install it (it also safely re-registers the task):
>
> ```powershell
> pwsh -File "$HOME\.agents\skills\billables-daily\scripts\setup_screenshot_pipeline.ps1"
> ```

### Coming from a hand-installed copy

There used to be one way in: clone the repo and run `install/install_skill.ps1`, which copied the
skill to `~\.claude\skills\daily-timesheet`. If that folder is on your machine, that is what you
have — and the instruction it came with, *update by re-running the installer*, no longer reaches
it. Re-running the installer today generates the shared Agent Skills export described above and
leaves your copy exactly where it is: still loading, still answering, permanently at the version
you installed. Moving to the plugin is how you get current.

**Almost nothing you care about is in that folder.** Your workspace is elsewhere — `Timesheets/`
with your `.context.md` and your per-day audit files, `daily_exports/`, and the `.mcp/` catalogs —
and none of it is touched by any of this. Your screenshots stay in `~\Pictures\WorkScreenshots`.
What *is* in the folder is the `.env` you filled in, and one setting you have been passing on the
command line:

| In the hand-installed copy | Where it lives now |
|---|---|
| `HARVEST_ACCOUNT_ID`, `HARVEST_API_KEY` in `.env` | `/plugin configure billables`. Both are declared sensitive, so they go to Claude Code's credential store instead of a file in the skill folder. |
| `--utc-offset 12` (13 in daylight saving) on every command | **Your timezone**, as an IANA name — `Pacific/Auckland`, not `12` — or left blank to use the machine's own zone, which every run then names as derived. This is a change of kind, not a rename: the offset is derived per date, so the twice-yearly edit stops being yours to remember. There is no conversion from your old number — say where you are, or let the machine. |
| `TIMESHEET_WORKSPACE` in `.env` | **Workspace directory** in `/plugin configure billables`. If you left it blank, look at where your workspace actually is before doing the same here: the old copy also searched the folders it was installed under, which from `~\.claude\skills\` reaches your home directory — so a `~\Timesheets` was found from any session. A plugin is never installed inside a workspace, so blank now means *the folder you start Claude Code in*, and nothing else. Blank is right if that is where you work; otherwise set it. |
| `TIMESHEET_SCREENSHOTS_DIR` — in `.env` on later copies, and as `-ScreenshotsDir` on the scheduled task | **Screenshot directory** in `/plugin configure billables`. Blank still means `~\Pictures\WorkScreenshots`. Read the value off the task rather than trusting the `.env`, which the earliest hand installs had no key for: `(Get-ScheduledTask -TaskName WorkScreenshots).Actions.Arguments`. |
| `DATAVERSE_URL`, `PAC_AUTH_PROFILE` in `.env` | Ordinary environment variables — [step 9](#9-optional-dataverse-ticket-catalog). They belong to one org rather than to every install, so the configuration dialog never asks for them. Do **not** put them in a `.env` inside the plugin folder. |

Then, in order:

1. **Install the plugin** ([more at the top of this README](#install)):
   ```
   /plugin marketplace add Cordedmink2/activity-to-timesheet
   /plugin install billables@activity-to-timesheet
   ```
2. **`/plugin configure billables`**, with the old `.env` open beside you, and fill in the
   right-hand column. Start a new session afterwards: the values reach the scripts at session
   start, in commands run through the **Bash** tool — that is the only shell they are published
   to, so a script run through PowerShell will report them missing.
3. **Read your current screenshot task back before touching it**, because the next step replaces it
   with one built from defaults:
   ```powershell
   (Get-ScheduledTask -TaskName WorkScreenshots).Actions.Arguments
   ```
   Anything non-default in there — a capture directory, `-StartTime`, `-EndTime`,
   `-IntervalSeconds` — is yours to carry over, and nothing carries it for you. A task silently
   back on 08:30–20:00 every 2.5 minutes is the kind of thing you notice a fortnight later, in the
   shape of a day with no evidence on it.
4. **Run `/billables:setup`.** The step you specifically need is that screenshot task: it is
   registered against the capture script *inside the old skill folder*, so it keeps running the old
   copy of the script until it is re-registered — and once you delete that folder it stops
   producing anything at all, showing up as a non-zero `LastTaskResult` rather than as an error
   anyone sees. `setup` reads the registered action back and re-registers it against the plugin's
   copy. Pass the values from step 3 through when it does.
5. **Bill a day you have already billed** — `/billables:daily` on a recent date — and compare what
   it proposes against what is in Harvest. That is the confirmation that your credentials, your
   timezone and your workspace all arrived.
6. **Delete `~\.claude\skills\daily-timesheet`.** Not optional and not cosmetic: until it is gone
   you have two skills that both answer *"do my timesheet"*, and no way to tell from the answer
   which one did. If you ever edited anything in there — a classification rule, a reference doc —
   diff it against the plugin's copy first and move the change over or raise it as an issue; the
   old installer copied files in place and never stopped you. Then delete the whole folder, `.env`
   included: everything in it now lives somewhere your next update can't overwrite.

Your `.context.md` needs no edit for any of this. The one line worth revisiting is any note in it
recording your UTC offset: the timezone is plugin configuration now, and a stale offset written
down beside your preferences is something a future run may read as current.

---

## Prerequisites

- **Windows** (the screenshot pipeline + setup scripts target Windows/PowerShell; the skill logic and
  the `.sh` install scripts work cross-platform, but screenshots are Windows-only as shipped).
- **PowerShell 7** (`pwsh`) for the commands below. Windows ships only Windows PowerShell 5.1, where
  `pwsh` doesn't exist — install it with `winget install Microsoft.PowerShell`, or substitute
  `powershell.exe -File …` in every command (the scripts run under 5.1 too).
- **Python 3.10+** that actually runs — verify with `py -m pip --version` rather than
  `python --version`. On Windows a bare `python` is often the Microsoft Store alias, a 0-byte stub
  that prints an install nag instead of running; and an install whose executables have been separated
  from their `Lib\` runs, prints a version, and still can't reach pip or site-packages. Reaching pip
  is the check that rules out both.
- **[Claude Code](https://claude.com/claude-code)** installed.
- A **Harvest** account you can create a personal access token for.
- A Chromium browser (Chrome/Edge) if you want per-client browser classification.

---

## Setup — step by step

> `/billables:setup` does steps 1–4 and 10 for you, checking each one rather than assuming it.
> This is the same ground written out, for reading first or for working without an agent.

### 1. Install ActivityWatch

On Windows, `winget install ActivityWatch.ActivityWatch` is the quickest route — the manifest pulls
the same official installer as the download page. Otherwise (and on macOS/Linux) get it from
**https://activitywatch.net/downloads/**. Then launch it and confirm it's running by opening
**http://localhost:5600** in your browser — you should see the ActivityWatch dashboard. Leave it
running in the background (set it to start on login).

### 2. Install the "URL in Title" browser extension

Install **URL in Title** from the Chrome Web Store:
**https://chromewebstore.google.com/detail/url-in-title/ignpacbgnbnkaiooknalneoeladjnfgb**

This extension rewrites each tab's title to include URL components. ActivityWatch records the window
title, so anything the extension puts in the title becomes a signal the skill can read.

### 3. Tag the browser profiles that belong to one client

In a browser profile you use for **one client and nothing else**, configure the extension to append
that client's short code to every title. In the URL in Title options, set the title format to:

```
{title}-{hostname}{path}{args}{hash} - [ACME]
```

Replace **`ACME`** with a short code for that client (pick your own — `BETA`, `NIMBUS`, whatever),
and do it **separately in each single-client profile**, using that profile's own code.

**Leave your general or default profile untagged.** That is the profile you use for everything —
your own admin, research, tools shared across clients — and a tag on it is worse than no tag at all.
The first matching rule wins, so a general profile's tag swallows every page in it that names a real
client: an hour of Acme's work done in the shared browser bills to whichever client the profile is
tagged for. Untagged, that hour is attributed from what is actually on the page. If you tagged a
general profile under an earlier version of this walkthrough, clear its format string back to
`{title}-{hostname}{path}{args}{hash}`.

The result: every tab in your "Acme" profile ends ` - [ACME]`, your "Beta" profile ` - [BETA]`, and
the shared one carries nothing. That tag is the **fallback** signal — it is what identifies browsing
that carries no other clue — which is why the next step ranks it below every other signal rather
than first.

> Tip: keep the bracketed code distinct and unlikely to appear by accident (the brackets help).
> You do not have to make it agree with anything by hand: the next step writes the matching rule
> from the code you chose.

### 4. The category rules (the plugin writes these)

This step is not yours to type. `/billables:setup` asks which clients you work for and what shows up
in a window title when you are working on each — a work-item prefix like `ACM1234S`, the address of
an environment or site, the name of an editor workspace, the profile tag from step 3 — and then
compiles, checks and writes the ActivityWatch category rules for you. You never see a regular
expression.

Every candidate is gated against your own recent window titles before anything is written, because
a bad rule fails silently rather than loudly — one matching nothing leaves that client's day
uncategorized, and one matching too much takes the label off the rule that should have won. The
demo below runs each failure live, and `/billables:setup` step 4 answers them in the words the gate
prints.

It also copies your existing rules into your workspace before it writes, keeps every category you
made yourself, and offers once to adopt those into the set it manages. Each category it writes is
flat and named for the client — ActivityWatch joins a category's name path with `>`, so a `Work >`
parent would change the label everything downstream matches on.

After that the rules stay current on their own: they are compiled from the signals in your
`Timesheets/.context.md`, and a run rebuilds them when that file changes, so a client you added last
week is matching this week. That file is the source of truth, so a category you edit in the settings
dialog for a client the plugin manages is replaced at the next rebuild — change the file, not the
dialog. Drop a client from the file and its rule goes with it.

**If your ActivityWatch is too old to take the write** — some builds have no settings endpoint at
all — setup says so out loud and walks you through the same rules by hand instead, then verifies
them the same way: **Settings → Categories**, **add a category** named for the client, give it a
**Regex** rule matching that client's bracketed code (`\[ACME\]`), and **save each one as you go**
rather than all at the end.

> **What that machinery is for:** open [`demo/tag-rule-demo.html`](./demo/tag-rule-demo.html) in a
> browser — one self-contained file, nothing to install. Its guided walkthroughs show a mismatched
> tag silently categorising nothing, a bare code claiming incidental prose, a tag on a general
> profile stealing a client's work, and a regex with spaces inside its alternation that only *looks*
> like it works. These are the failures the gate exists to refuse.

### 5. Install the skill on a harness that isn't Claude Code

On Claude Code, the two `/plugin` commands at the top of this README are this step — skip it.

Codex, OpenCode, Hermes and the other Agent Skills clients read `~/.agents/skills/` instead, which
no plugin can install into. From a clone of this repo, generate the export:

```powershell
pwsh -File install\install_skill.ps1
```

(macOS/Linux: `./install/install_skill.sh`. Both hand over to
`install/export_agent_skills.py`, which is where the export is documented; pass a directory to
write somewhere other than `~/.agents/skills`.)

That writes one directory per skill — `billables-daily`, `billables-reconcile` and
`billables-setup` — prefixed, because that directory is flat and a bare `daily` among your own
skills says nothing about where it came from. You get the same three skills a plugin install does,
`setup` included, so the manual walkthrough is available to you too: invoke `billables-setup`
however your harness names skills. It's generated from the plugin every time rather than merged
into, so re-running it is how you update; your `.env` is the one thing kept. A maintainer's `.env`
and build artifacts never leave the repo.

### 6. Scaffold your workspace

Pick (or `cd` into) the folder you want to be your timesheet workspace, then:

```powershell
pwsh -File install\setup_workspace.ps1            # uses the current directory
# or target an explicit folder:
pwsh -File install\setup_workspace.ps1 -Workspace C:\Users\you\Work
```

(macOS/Linux: `./install/setup_workspace.sh [path]`.)

**No clone?** The script is a convenience, not a requirement — ask your agent to create the three
folders below in your chosen workspace and copy `references/context.md.example` out of the
installed skill to `Timesheets/.context.md`. That is everything the script does.

This creates the folders the skill uses:

- **`Timesheets/`** — your `.context.md` (see next step) plus optional per-day markdown audit files.
- **`daily_exports/`** — optional historical ActivityWatch dumps (a fallback when AW isn't running).
- **`.mcp/`** — cached catalogs (your Harvest project list, etc.), refreshed automatically.

It also seeds **`Timesheets/.context.md`** from the template (without overwriting an existing one).

### 7. Fill in your `.context.md`

`Timesheets/.context.md` is the **per-user source of truth** — the skill reads it on every run, and
it's what makes classification accurate. It stays **local** (it's git-ignored). Open it and fill in:

- **Preferences** — the judgement calls: AFK/lunch thresholds, what counts as substantive activity,
  the active/thin bands, the timeline's noise floor, your default task. Each line names the
  flag the skill passes for it, so retuning one never means editing a script an update would
  overwrite. (Your *timezone* is not here — it's plugin configuration, set once at install.)
- **AW buckets** — your machine's hostname suffix (the skill can discover this on first run).
- **Internal colleagues** — names that, in a Teams title, mean internal work rather than a client.
- **Known external contacts** — people who map to a specific client.
- **Active client projects** — one block per client: its code/bracket tag, Edge profile name,
  Dynamics/SharePoint/Azure DevOps URLs, repo paths, VS Code workspace names — every signal that
  identifies "this is client X".
- **Work kinds** — the skill classifies each block as one of seven neutral kinds (`Meeting`,
  `Development`, `Documentation`, `Project management`, `Testing`, `Investigation`,
  `Internal admin`) and this table says what *your* Harvest account calls each one. No task name
  ships with the skill, because no two accounts spell theirs the same way. Easiest filled in after
  step 8, once your catalogs exist — the skill can read the task names off your own projects and
  offer them. Leave it out and it works that out per block and proposes the row back to you.
- **How I bill** — your description style and project-selection conventions.
- **Personal browsing to exclude** — anything that should never be billed.

The skill will also *propose* additions to this file as it learns (showing you the diff first) — it
never edits it silently.

### 8. Set your Harvest API credentials

The [install section](#install) above covers this: an **Account ID** and a **Personal Access
Token** from **https://id.getharvest.com/developers**, entered once with
**`/plugin configure billables`**, then a new session so the values reach the scripts. A
member-scope token is enough. `/billables:setup` checks they arrived and tells you which gap it is
when they haven't.

The reasoning behind each of those steps — the order a setting resolves in, where a sensitive value
actually sits on your platform, why a new session is what delivers it, and the `.env` an exported
install uses in place of the dialog — is in `skills/daily/references/first-run.md`
§ "First-run: configuration", which is also what the skill reads when a run reports a credential
missing.

### 9. (Optional) Dataverse ticket catalog

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
- **Exported install** (step 5): the skill root's `.env`, alongside the Harvest keys.

The profile must be a **named** one — the refresh selects it with `pac auth select --name`, and
`pac auth create` without `--name` creates an unnamed profile it can never select. Authenticate with
`pac auth create --name YourPacAuthProfileName --environment https://yourorg.crm6.dynamics.com/`, or
name an existing profile without re-authenticating: `pac auth name --index <N> --name <name>`.

This requires the [Power Platform CLI](https://learn.microsoft.com/power-platform/developer/cli/introduction)
(`pac`) installed and authenticated. **Leave both blank to skip it** — everything else works
Harvest-only.

If you instead connect Dataverse through an MCP server (e.g. via the `dataverse` plugin's `dv-connect` skill), register it **scoped locally to this workspace** — run `claude mcp add -s local …` from this folder, never user scope — so a single-env server can't follow you into your other client repos.

### 10. Set up the screenshot pipeline

This is a **core part of the skill, not optional.** Screenshots are how the skill disambiguates
generic activity (a bare browser, a terminal, `XrmToolBox`, an IDE with no workspace in the title)
into the right client — the window title alone often can't.

```powershell
pwsh -File "$HOME\.agents\skills\billables-daily\scripts\setup_screenshot_pipeline.ps1"
```

This installs [Pillow](https://pillow.readthedocs.io/) and [mss](https://python-mss.readthedocs.io/)
if needed and registers a single Windows scheduled task (`WorkScreenshots`) that runs every ~2.5
minutes on weekdays from **08:30 to 20:00**, saving to `~/Pictures/WorkScreenshots/<date>/`. Each
tick writes **one PNG per monitor** (`HH-MM-SS_m1.png`, `HH-MM-SS_m2.png`, … in left-to-right order,
at native resolution) rather than a single stitched image. Adjust with `-StartTime`, `-EndTime`,
`-IntervalSeconds`. Re-running safely replaces the task.

The setup probes each Python it can find with a real import and skips broken ones — the 0-byte Store
stub and the "install exists but can't reach its own libraries" case both showed up in the wild. If
it still picks the wrong interpreter, pin one with `-PythonExe C:\path\to\python.exe` (a broken
`-PythonExe` is an error, never a silent fallback).

> **If a previous `WorkScreenshots` task was registered as Administrator**, re-running setup from a
> normal shell fails with `Access is denied`. Running setup *elevated* clears the error and brings
> the trap straight back: the replacement is owned by `BUILTIN\Administrators` too, so the next
> ordinary re-register fails the same way. Break it in two steps instead — remove the task from an
> **elevated** PowerShell, then register the new one from a normal shell, so it ends up owned by
> you and no later update needs elevation:
>
> ```powershell
> Unregister-ScheduledTask -TaskName WorkScreenshots -Confirm:$false   # elevated
> ```

### 11. Use it

In Claude Code, just ask — the skill triggers on natural phrasing:

- *"do my timesheet for yesterday"*
- *"what did I work on Friday?"*
- *"log my Harvest time for 2026-06-17"*
- *"catch up / backfill my timesheets"*

It drafts the blocks, shows you the AFK-derived day skeleton as a reality check, flags anything
uncertain, and asks before posting anything to Harvest.

---

## Customize

- **`Timesheets/.context.md`** (in your workspace) — all your per-user facts. Edit any time.
- **`skills/daily/references/classification-rules.md`** — the generic rubric the skill uses
  to turn signals into a `(client, project, task, billable)` decision.
- **`skills/daily/references/output-format.md`** — the markdown timesheet template.
- **`skills/daily/references/first-run.md`** — first-run setup the skill walks you through.
- **`skills/daily/references/activitywatch.md`** — what the skill reads out of ActivityWatch.
- **`skills/daily/references/new-client-work.md`** — raising a new ticket for unmatched work.
- Thresholds (AFK break length, what counts as substantive activity, the active/thin bands, the
  timeline's noise floor and gap fold, lunch window, default task) are overridable in `.context.md`
  under `## Preferences` — each line names the flag it maps to. Machine and account facts
  (credentials, timezone, ActivityWatch address, screenshot and workspace directories) are plugin
  configuration instead: `/plugin configure billables`.

---

## Security

- **Your Harvest token has full access to your account.** On a plugin install it is declared
  sensitive, so Claude Code holds it in your OS keychain — it is never written into the plugin
  folder or into `settings.json`. On an exported install it lives in a `.env`, which is git-ignored
  at both the repo and skill level: don't commit it, and don't share the skill folder with it inside.
- The skill **never writes to Harvest without explicit confirmation**, and that is enforced rather
  than only promised: the two scripts that create or amend a time entry write nothing unless passed
  `--confirm`, and print what they would have sent instead. So an agent that reached them without
  being asked to bill still bills nothing.
- Screenshots stay **local** on your machine (`~/Pictures/WorkScreenshots/`); nothing is uploaded.
- Your client list, colleagues, and billing conventions live in `Timesheets/.context.md`, which is
  git-ignored — keep it that way.

---

## What's in this repo

```
activity-to-timesheet/
├── README.md                 # you are here
├── .github/ISSUE_TEMPLATE/   # the two forms behind "New issue": a problem, an idea
├── CHANGELOG.md              # what changed in each release
├── LICENSE                   # MIT
├── AGENTS.md                 # for agents working on the repo: how to verify, where a thing goes
├── CONTEXT.md                # the vocabulary the rules are written in
├── intent/                   # what the product is for and refuses to become
├── docs/
│   ├── CONTRIBUTING.md       # how to change the plugin without losing what it knows
│   ├── adr/                  # the decisions that are hard to reverse, with their reasoning
│   ├── agents/               # tracker and label conventions the engineering skills read
│   └── skills/daily/decision-log.md  # the evidence behind the daily skill's rules
├── demo/
│   └── tag-rule-demo.html    # interactive demo of the tag/category-rule failure modes
├── .claude-plugin/           # marketplace + plugin manifests, incl. the configuration it asks for
├── hooks/                    # SessionStart: hands that configuration to the bundled scripts
├── skills/setup/             # /billables:setup — the manual steps, each one verified
├── skills/reconcile/         # /billables:reconcile — days worked but never billed
├── skills/daily/             # /billables:daily — the timesheet run
│   ├── SKILL.md              # the skill's instructions
│   ├── .env.example          # credential + optional-config template
│   ├── references/           # classification rules, first-run, context template, formats
│   └── scripts/              # Harvest + ActivityWatch + screenshot helpers (stdlib Python)
│       ├── activity_timeline.py  # categorized window timeline from AW category rules
│       ├── category_rules.py     # compiles, gates, writes and verifies those rules
│       ├── afk_blocks.py         # AFK-anchored day skeleton (work_start/end, breaks)
│       ├── aw_client.py          # shared ActivityWatch REST helpers for every script that reads a day
│       ├── harvest_lookup.py     # project_id/task_id lookup by code, name or client
│       ├── skill_config.py       # the one seam every script reads a setting through
│       ├── timezone.py           # the zone a day is read in + its clock arithmetic
│       └── ...                   # harvest_post/patch/list, refresh_catalogs, screenshot_capture
├── tests/                    # guards on the install/setup scripts a new user runs first
└── install/                  # export_agent_skills.py (the shared-directory export the
                              #   install_skill wrappers run) + setup_workspace
```

## Reporting a problem

Open an issue — the ["New issue"](../../issues/new/choose) form asks for the version, what you
asked for, and what the skill did instead.

Two things worth knowing before you do:

- **Not everything is a defect.** If the skill didn't know one of *your* clients, signals or
  machine facts, that belongs in your own `Timesheets/.context.md`. If a window title comes back
  `uncategorized`, the plugin has no signal for that client yet — add one to your `.context.md` and
  the next run compiles a rule from it, which `references/first-run.md` covers. Neither is fixed by
  a change here.
- **Redact before you paste.** This tool reads window titles, screenshots and Harvest entries, so
  its output carries client names, project codes and file paths. Issues are public.

The skill can do this for you: at the end of a run it sorts what it learned, and for anything that
looks like a genuine defect it will draft the report and offer to file it. It won't file anything
without you saying yes.

## License

MIT — see [LICENSE](./LICENSE).

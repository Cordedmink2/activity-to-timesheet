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
| **Workspace directory** | Optional. Blank means the folder you run Claude Code from, if it already looks like a workspace (`.mcp/` or `Timesheets/`) — which is the normal case. Set it if you start sessions elsewhere: a plugin is never installed *inside* a workspace, so there is no second place to fall back to. `/billables:setup` creates the workspace and tells you when to answer this. |
| **Read my Outlook calendar** | Optional, off by default. On, the `daily` skill reads your default calendar in classic Outlook (Windows only) as a fourth source — a calendar event your activity corroborates is drafted, one it does not is put to you as a question. Off is exactly today's behaviour. |

To change any of them later: `/plugin configure billables`.

### Then run `/billables:setup`

It offers to install whatever your machine is missing — ActivityWatch, Python, Git Bash — and runs
each install only once you say yes. It walks you through the browser extensions, asks you about
your clients in plain language, tags the profiles that belong to one client, creates your workspace
with a starter `.context.md` naming each client, writes your category rules for you, sets up the
screenshot task and settles whether your Outlook calendar is read — and *verifies each one before
moving on*, which is the difference that matters: every one of those
steps can look like it worked and have done nothing, and the symptom arrives days later as an
empty timesheet. It tells you when setup is finished.

That is the whole path — you don't need to clone this repo, read the rest of this file, or run a
script by hand. What is left afterwards is the rest of your `.context.md` — colleagues, work kinds, how you
bill — which the `daily` skill's first run does with you.

> **Heads-up on antivirus / EDR.** A scheduled task that silently screenshots every few minutes
> looks like spyware to endpoint security, so it (or `pip install`) may be blocked mid-setup. The
> `setup` skill catches that where it happens, and hands you a request your security team can
> action: the `WorkScreenshots` task plus the interpreter and script paths read back off the
> registered task, never a folder-wide exclusion. It establishes that the step really was blocked
> before sending you anywhere.

Paths below of the form `$HOME\.agents\skills\billables-daily\…` are where the **exported** copy
lives — the shared Agent Skills directory, for harnesses that aren't Claude Code (see
[below](#on-a-harness-that-isnt-claude-code)). On a plugin install, substitute
the plugin's own skill directory; the skill itself resolves this at run time and never needs to be
told.

---

## On a harness that isn't Claude Code

On Claude Code, the two `/plugin` commands above are the whole install — skip this.

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

---

## How it works (the short version)

1. **ActivityWatch** runs locally and logs which app/window/browser-tab is in focus, plus when you're
   away from the keyboard (AFK).
2. The **"URL in Title" browser extension** stamps a short **client code** into every tab's title
   in a browser profile you use for one client (e.g. `… - [ACME]`), so browsing that carries no
   other clue still says who it was for.
3. **ActivityWatch category rules**, which the plugin writes and keeps current from a few words you
   choose per client, label activity per client — the client code the profile tag carries, the names
   of that client's own products, the client's name. Each category is flat and named for the
   client. [`demo/tag-rule-demo.html`](./demo/tag-rule-demo.html) — one self-contained file — shows
   the ways a tag or a rule fails silently, which is why setup checks every word against your own
   titles before writing anything.
4. A small **screenshot grabber** takes a periodic screenshot during work hours, used only to
   disambiguate activity that the window title alone can't pin to a client.
5. The **skill** reads all of the above, drafts a timesheet, shows it to you, and posts confirmed
   blocks to Harvest. Ask in plain words — *"do my timesheet for yesterday"*, *"what did I work on
   Friday?"*, *"catch up my timesheets"* — or run `/billables:daily`.

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
| `DATAVERSE_URL`, `PAC_AUTH_PROFILE` in `.env` | **Your `.context.md`**, under `## Work-item source`, as `Environment URL` and `Auth profile` (with `Adapter: dataverse`). They are no longer settings at all — they describe one account, so they live with your other account facts. See the `daily` skill's `references/catalog-refresh.md` § "The work-item source". A run that still finds the old settings says so. |

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
- **PowerShell 7** (`pwsh`) for the `pwsh -File` commands in this file. Windows ships only Windows PowerShell 5.1, where
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

## Customize

Everything about *you* — clients, colleagues, billing conventions, and the thresholds under
`## Preferences` (each line names the flag it maps to) — lives in `Timesheets/.context.md` in your
workspace, and the skill re-reads it on every run. Machine and account facts are plugin
configuration instead: `/plugin configure billables`. Nothing in the plugin folder is yours to
edit; an update overwrites it.

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

## Reporting a problem

Open an issue — the ["New issue"](../../issues/new/choose) form asks for the version, what you
asked for, and what the skill did instead.

Two things worth knowing before you do:

- **Not everything is a defect.** If the skill didn't know one of *your* clients, signals or
  machine facts, that belongs in your own `Timesheets/.context.md`. If a window title comes back
  `uncategorized`, the plugin has no category term for that client yet — add one to your
  `.context.md` and the next run writes a rule from it, which `references/first-run.md` covers. Neither is fixed by
  a change here.
- **Redact before you paste.** This tool reads window titles, screenshots and Harvest entries, so
  its output carries client names, project codes and file paths. Issues are public.

The skill can do this for you: at the end of a run it sorts what it learned, and for anything that
looks like a genuine defect it will draft the report and offer to file it. It won't file anything
without you saying yes.

## License

MIT — see [LICENSE](./LICENSE).

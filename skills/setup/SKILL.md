---
name: setup
description: Walk a first-time user through installing this plugin — offering to install what the machine is missing, installing the activity source and the browser extensions, interviewing them about their clients to tag single-client browser profiles, write a starter workspace context file and write and verify their category rules, getting the screenshot task past endpoint security, settling whether the Outlook calendar is read, and offering the two optional check-in watchers that ask what you were doing while you were away — verifying each one before moving on, in plain language for a non-technical user. User-invoked.
compatibility: Windows-first. Reads a running ActivityWatch server over HTTP (default http://localhost:5600). Step 5 registers a Windows scheduled task and needs PowerShell plus Python 3.10+; on macOS and Linux there is no screenshot capture to set up and that step is skipped. Step 6 reports the calendar off without classic Outlook. Step 7 offers the optional check-in watchers (Python 3.11+). Needs a harness that can execute local commands and make HTTP requests. Posts nothing to any timesheet provider.
disable-model-invocation: true
---

# setup

The other skills in this plugin fail loudly — a script exits non-zero and says why. The install does not. Every step below can look like it worked and have done nothing: an extension added to the wrong browser profile, a category rule that matches no title, a scheduled task registered against an interpreter that no longer exists. The symptom arrives days later as a timesheet with nothing in it, and by then nobody remembers which step it was.

So this skill is not a list of instructions. It is a list of instructions **with a check after each one**, and it does not move on until the check comes back. Run it top to bottom.

Where a step's **Do** carries a block-quoted instruction — steps 1 to 4 — that block is what to give the user, near enough verbatim, and short because they are about to go and do it. The prose around it in those four steps is the reasoning behind it, written for you rather than for them. A user handed the reasoning has to work out which sentence was the instruction. This says nothing about the rest of the file: steps 5 and 6 have things to say to the user, and step 6's verify puts a sentence to them in so many words.

## How to talk to the user

Assume the user is not technical. Everything you say to them — a quoted instruction, an interview question, a recommended answer, why a check failed — is written in plain **Simplified Technical English** (ASD-STE100):

- Give one line of context first: what this step is for and why it matters to their timesheet. Then ask or instruct.
- Short sentences, active voice, one instruction per sentence. Twenty words is a long sentence.
- Use the plugin's own words — *client code*, *profile tag*, *category terms*, *workspace* — and explain each in one plain sentence the first time it comes up. "ActivityWatch" is "the app that records what you work on" until they have met it.
- Show them only what they have to type or click. Regular expressions, JSON, bucket ids, web addresses of the local server and the commands you run yourself stay in your own tool calls.

When the user says they are lost, stop and re-pitch: a little context about where you have got to, then the same point in simpler words. Carry on only once they follow.

## What this covers, and what it does not

It covers what a person has to do, and does for them what a machine can once they agree: the installs "Before you start" offers (#67), the category rules step 4 composes, gates and writes — once a regular expression the user typed into a settings dialog, and the step most often wrong in a way nobody noticed (#69) — and the workspace step 4 writes. Two things belong elsewhere and are not repeated here:

- **The values** — credentials, timezone, paths — are declared plugin configuration, collected once at install. This skill checks whether they are *present* and routes a gap to `/plugin configure billables`. It never asks for one, and never asks the user to type a token into the conversation, which is written to disk in the session transcript. If the user pastes one in anyway, say so at the time and suggest they rotate it before that transcript is shared anywhere — the dialog is the fix going forward, but the token that has already been written down is not fixed by using the dialog next time.

  **The check is the other way a token reaches the transcript, and it is the way that has actually happened.** A command run to find out whether a value is set writes its own output to the same transcript, so *no command in this skill may expand a credential into its output* — the answer is `set` or `MISSING`, never the value. **Use the probe given below rather than composing one.** The version this replaces paired the two default-substitution forms in one string, on the reading that each supplies a word for its own case; in fact only one of the pair substitutes a word, and the other substitutes the variable itself, so the line printed `set` followed by the user's API key. Nothing failed and nothing looked wrong. If a run has already printed a credential, treat it exactly as a pasted token above: say so at the time, and tell the user to rotate it.
- **The rest of the workspace context.** Step 4 scaffolds the workspace and writes the half of `Timesheets/.context.md` this walkthrough learns — the clients, their codes, profile tags and category terms. The half it does not learn — colleagues, external contacts, work kinds (which need the credentials), billing voice, exclusions — stays as template for the `daily` skill's first run. Point at it at the end.

Seven steps, and then a stated finish.

## Finding the files this skill needs

Steps 4, 5 and 6 run scripts that ship with the `daily` skill, in a directory beside this one. Resolve **this** skill's folder from where this `SKILL.md` was read, then look for a sibling named `daily` — or, in the shared export, `billables-daily`, because that directory is flat and every skill in it is prefixed. Check which of the two exists rather than guessing; a wrong prefix fails as "file not found", which reads like a broken install rather than a wrong path.

## Before you start

Five things before step 1 — the first four in parallel, then the fifth from what they found:

1. **Is the configuration set?** Run exactly this, through the **Bash** tool — the declared values are published into the session as a POSIX shell fragment, so PowerShell reports `MISSING` for a machine that is configured perfectly well:

   ```bash
   for k in HARVEST_ACCOUNT_ID HARVEST_API_KEY; do
     if [ -n "${!k:-}" ]; then echo "$k=set"; else echo "$k=MISSING"; fi
   done
   ```

   Two lines of `set` or `MISSING` and nothing else. Do not collect the values here and do not block on them — steps 1 to 6 need neither, so carry on and re-check at the finish. The timezone is not probed: left blank, the scripts read this machine's own zone and label every day as read in it, so a blank one is not a gap — `TIMESHEET_TIMEZONE` is for pinning a zone the machine does not carry. Leave the `:-` in `${!k:-}` alone: under `set -euo pipefail`, which some harnesses wrap every command in, the bare form aborts the shell on the first unset key — so the machine that most needs an answer is the one that gets a shell error instead, and a run that gets a shell error writes its own replacement.

   **If there is no Bash tool on this machine, do not translate the probe into PowerShell.** No PowerShell command can answer this question on any machine: the fragment is POSIX and is applied to Bash calls only, so PowerShell reports nothing set whether or not the user has configured anything (issue #28). And a box with no Git Bash is one where the publishing hook could not run either, so nothing was published to either shell. That makes the answer known in advance — treat both as `MISSING`, skip to the Git Bash question below, and never compose a check to confirm it. Composing one is what leaked a key.

   **An absent value here has two causes and they need different things.** Either it was never filled in, or it was filled in and the session hook that republishes it did not run — on Windows that hook needs Git Bash, and without it the values reach nothing. So do not report "not configured" from an empty environment alone. Ask whether the user has filled in `/plugin configure billables`; if they have, the answer is a new session, and if a new session does not fix it, `references/first-run.md` in the `daily` skill owns that diagnosis. If they have not, that is the thing to ask for — the dialog, never the conversation.

   **On an exported install there is no dialog to send them to.** A harness that is not Claude Code has no plugin manifest to hold configuration, so the same keys live in a `.env` beside the sibling skill's `SKILL.md`, and `/plugin configure billables` is a command that does not exist there. Work out which install this is at the same time as resolving the sibling directory below, and route a gap to copying that skill's `.env.example` to `.env` instead. Either way the value is written to a file by the user, not typed into the conversation.

   The probe above cannot see that file, so on an exported install a `MISSING` means nothing until the `.env` has been checked too — and it is checked by **key name only**, never by reading the file out: `grep -c '^HARVEST_API_KEY=[^[:space:]]' <daily-skill>/.env` and the same for the other key. A count is the whole answer. The trailing character class is the whole point of the pattern rather than a detail of it: `.env.example` ships every one of these keys already present and empty, so a user who copies the template and stops has both key names in the file and no values, and a pattern that counts the name alone reports a fully configured install. Blank is unset everywhere else in this plugin, and it has to be unset here too. `cat`ting a `.env` puts the key in the transcript by a different route than the one above and costs the user the same rotation.
2. **Which address is the activity source on?** `TIMESHEET_ACTIVITY_URL` if it is set, otherwise `http://localhost:5600`. Use that address everywhere below.
3. **Is there a working interpreter?** On Windows, prefer `py` over a bare `python`: the bare name is often the Store app-execution alias, a 0-byte stub whose tell is a help message about installing from the Store and exit code 49. Probe it — `py -c "import sys; print(sys.prefix)"` then `py -m pip --version` — rather than trusting that the name resolves. An interpreter that exists and even imports its stdlib can still be broken: `Could not find platform independent libraries` on stderr is a split install whose `sys.prefix` doesn't resolve, so pip and site-packages are unreachable. Both matter most at step 5, where a broken interpreter and a blocked one look identical, and the first coworker install of this pipeline went to IT over exactly that confusion.
4. **Is there a shell to run step 5's script in?** A stock Windows box has only Windows PowerShell 5.1, so `pwsh` may not exist. It is optional: `powershell.exe -File ...` runs the scripts under 5.1 just as well. Under 5.1, quote home-relative paths as `"$HOME/..."`: a bare `~` is passed through literally to a native command rather than expanded, so the path resolves to a directory named `~` and the failure reads as "file not found".
5. **What is missing, offered once.** Look the rest up yourself rather than asking: whether the activity source answers `GET <activity-url>/api/0/info`, whether the Bash tool runs at all (no Bash tool on Windows means no Git Bash), and which browsers are installed — for each Chromium browser, the profiles in `User Data\Local State` under `profile.info_cache` (each key is a profile's directory, its `name` what the user sees). The profiles feed steps 2 and 3, so keep them. Then put everything missing to the user as **one** list, each item with a plain line on why it matters and the command you would run:

   The commands are in `references/install-commands.md`, one row per item.

   Ask once — "Shall I install these for you?" — and run only what the user says yes to: a machine-wide install is theirs to choose. Say before you start that Windows may show an administrator prompt and that it is theirs to accept. Anything declined falls back to the step's own instruction, as if nothing had been offered.

   **Verify each install by re-running its probe**, not by the installer's exit code. A new Python is not on this session's `PATH` until the shell restarts — probe it by `py` or by the path winget printed. A new Git Bash reaches nothing until a new session starts, because the hook that publishes the configuration runs at session start; say so, and have the user restart and invoke setup again rather than carrying on without it.

## How the interview runs

Steps 3 and 4 settle who the user's clients are and how each one shows up on screen. Settle it as an **interview in rounds**: each decision opens the ones that depend on it, and a round asks every question whose prerequisites are already answered — the **frontier** — and nothing that waits on an answer not yet given.

- **Number each question and give your recommended answer under it**, with one plain line on why. The user can reply "yes to all" or correct a number.
- **Facts are yours to find, never the user's to supply.** Profile names come from `Local State`; client codes already in use from the `SEEN` lines; the addresses each client's work opens from the `HOST` lines; the user's own old categories from the `RULE` lines — all printed by `--inspect` (step 4.2). Ask the user only for decisions: which client a thing belongs to, and what to call it.
- **Done is an empty frontier**: every client has a name, a code and its terms, every work profile is single-client or general, and nothing is left assumed. Then put the one-line-per-client summary (step 4.4), and write once the user confirms it.

The rounds, in the order their prerequisites allow:

1. **Who and where.** The clients they bill, spelled as their timesheet provider spells them. Their own firm's name, and the addresses its own work opens — its SharePoint site, its DevOps org — so none of those is ever offered as a client's term. Which browser profiles are for work, pre-filled from `Local State`. Where the workspace folder goes (recommend the current folder).
2. **Each profile, and each client's code.** For each work profile: one client only (which) or several. A short client code for each client, recommended from a profile name or a `SEEN` tag where one exists.
3. **Each client's terms**, recommended from its code, its own products, its name and its `HOST` lines, in the order that should win a page two clients both match.

## Steps

### 1. The activity source is installed and running

ActivityWatch is the app that records which window is in front and when. Everything else in this plugin reads what it recorded.

**Do** — if "Before you start" installed it, launch it (`aw-qt`, or the ActivityWatch entry in the Start menu) and go straight to the verify. Otherwise give the user this:

> **Install ActivityWatch, then start it.** ActivityWatch records what you work on. Your timesheet is built from what it records.
>
> - Download it here: https://activitywatch.net/downloads/
> - Run the installer. Then start ActivityWatch.
> - Look for its icon near the clock. That icon means it is running.
>
> Tell me when you see the icon.

**Verify** and **If it fails** — run `references/checks.md` (check `activity-source`) and do not move on until it passes.

### 2. The browser extensions are recording

Window titles are the only client signal that survives into the activity stream. Without the **URL in title** extension a browser title is a page name, which says nothing about which client the page belongs to — so it is required. The **ActivityWatch web watcher** records each tab's full address as well, which the `daily` skill reads when it zooms in on an unclear stretch of the day. It is recommended, and the user may decline it.

| Extension | Chrome Web Store (Edge, Chrome, Brave, Vivaldi, Opera) | Firefox |
|---|---|---|
| URL in title — required | https://chromewebstore.google.com/detail/url-in-title/ignpacbgnbnkaiooknalneoeladjnfgb | none this plugin has been tested with |
| ActivityWatch web watcher — recommended | https://chromewebstore.google.com/detail/activitywatch-web-watcher/nglaklhklhcoonedhgnpgddginnjdadi | https://addons.mozilla.org/firefox/addon/aw-watcher-web/ |

**Do** — for each browser and work profile "Before you start" found, offer to open the store pages in that profile for them: `Start-Process "<browser exe>" -ArgumentList '--profile-directory="<profile dir>"', '<store url>'`, with the directory from `Local State`. The profile has to be named: without it the page opens in whichever profile was used last, and the extension lands in the wrong one. The user still clicks **Add** — a store install cannot be done for them without browser policy. Then give the user this:

> **Add two extensions to each browser profile you work in.** They let your timesheet see which website each window shows.
>
> - I have opened the store pages for you. If a page did not open, use the links I gave you.
> - On each page, click **Add to** (or **Get**). Then confirm.
> - **URL in title** is needed. **ActivityWatch web watcher** is recommended. You can skip the second one.
> - Extensions belong to one profile. Add them again in each of your other work profiles.
>
> Tell me which profiles you added them to, and whether you skipped the web watcher.

Where the user works in Firefox, say plainly that there is no Firefox copy of URL in title this plugin has been tested with: its window titles will name the page but not the address, so Firefox work is classified from page words alone. A Chromium browser for client work is the better route; the web watcher still works in Firefox.

The verify below is aggregate, so the profile list is not what it is judged against. Step 3's check is the one that walks the profiles one at a time.

**Verify** and **If it fails** — run `references/checks.md` (check `browser-extensions`) and do not move on until it passes.

### 3. A browser profile dedicated to one client carries that client's tag

**Which browser decides how.** Say which one you are configuring. **Edge** already writes the profile's name into every window title (`… - ClientA - Alex - Microsoft Edge`), so a profile name is a category term with nothing installed: the `PROFILE` lines of step 4.1 list each one with the gate's verdict, and the tag below is an optional upgrade for Edge. **Chrome** writes no profile name — two profiles can show byte-identical titles — so URL in title and its tag are **required** there. **Firefox** has not been verified for either; say so and claim no support. Bracketed codes and rules already written keep working unchanged. Detail: `references/profile-names.md`.

**Do** — run `--inspect` (step 4.2) first, so its lines are in hand, then the interview's rounds 1 and 2. Round 2 decides which of their profiles belongs to exactly one client. **A profile tag goes on those and nowhere else.** A general or default profile — the one they use for everything, their own admin, research, the tools they share across clients — carries none, and its time is attributed from what is on the page instead. A short, collision-resistant **client code** is settled for every client either way; give the user this once per single-client profile, with that profile's own code substituted:

> **Add this client's code to this profile.** The code is a short label, like ACME. It tells your timesheet that everything in this profile is for that client.
>
> - In this profile, open `edge://extensions` (or `chrome://extensions`). Find **URL in title**. Click **Details**, then **Extension options**.
> - Change the title format to: `{title}-{hostname}{path}{args}{hash} - [ACME]`. Put this profile's code where it says `ACME`.
> - Click **Save**.
> - Do the same in each of your other one-client profiles, with that client's code. In a profile you use for more than one client, do not change anything.

**A user with one profile for every client tags nothing**, and this step is only its second check below — that no old tag is left in that profile. Say so plainly: their client work is recognised from the addresses and words on each page, which step 4 chooses with them from the `HOST` lines.

The narrowing is the point, and it is not tidiness. The code in a tag is the first of that client's category terms in step 4, so it labels every window carrying it — and the first matching rule wins, so a tag on a general profile swallows every page in it that names a real client: an hour of Acme's work done in the shared profile bills to whichever client that profile is tagged for. **A user who has already tagged a general profile** — most people migrating from an earlier version of this walkthrough — clears that profile's format string back to `{title}-{hostname}{path}{args}{hash}` in the same options page.

Write down which profile carries which code: step 4 composes a rule from it and writes it into the workspace context file as that client's **Profile tag**.

**Verify** and **If it fails** — run `references/checks.md` (check `profile-tags`) and do not move on until it passes.

### 4. The clients are written down and their category rules verified

This step is yours, not the user's. Each client gets **one** category rule, made from a few words that only that client's work puts in a window title — its **category terms**. You choose them with the user in the interview's round 3, write them into the workspace context file, and hand them to a bundled script that gates, backs up, writes and verifies. **The user sees the terms, never a regular expression or a JSON body.**

**Do** — in this order.

1. **Is there enough to learn from?** Run `python "<daily>/scripts/category_rules.py" --data-days` in the Bash tool and read the `DATA` line. `COLLECTING` means fewer workdays are recorded than the threshold (five by default; the user's `Workdays before the category stage` line under `## Preferences` changes it). **Stop here: write no rule.** Relay the `say:` line as it stands, write the date to come back under `## Preferences`, and end this step as *collecting data* — the daily run still works without rules, with more questions, and offers this step again once the date has passed. `READY` goes on.
2. **Read what is already there.** `python "<daily>/scripts/category_rules.py" --inspect` — again where step 3 tagged profiles, so the new tags show. It prints `RULE`, `SEEN`, `PROFILE` and `HOST` lines, described in `references/choosing-terms.md`.
3. **Choose each client's terms with the user** — adopting their own categories and choosing terms are both in `references/choosing-terms.md`, which is the one home of those rules. This is the interview's round 3.
4. **Say what you are about to do, in one line per client** — "Acme: ACME, AcmePortal, Acme Holdings, the Acme Trust SharePoint site. Beta: BETA, Fabric Orders. Your six other categories stay as they are." — and go on once they say yes. That confirmation is the end of the interview.
5. **Write the workspace and its context file** — before the rules, because the script stamps the rules with a fingerprint of this file, and a file written after them reads as changed on the `daily` skill's next run.
   - **The workspace** is the folder round 1 chose. From a clone of the repo, `install/setup_workspace.ps1 -Workspace <path>` (POSIX: `install/setup_workspace.sh <path>`); otherwise create `Timesheets/`, `daily_exports/` and `.mcp/` in it yourself. A folder other than the one sessions start in also needs `TIMESHEET_WORKSPACE` set to it — through `/plugin configure billables`, or the `.env` on an exported install — once the folder exists; until the next session, pass `--workspace <path>` to the script below.
   - **`Timesheets/.context.md` is never written over.** If it does not exist, copy the `daily` skill's `references/context.md.example` to it, then fill in the **AW buckets** section from step 1's bucket ids and one **Active client projects** section per client: **Client name** as the provider spells it, **Profile tag** where step 3 set one (else delete that line), **Category terms**, and under **Signals** the profile and the addresses behind its host terms. Leave every other section as the template has it: those are the `daily` skill's first run to fill. If the file already exists — a user re-running setup — write the same facts into it as a change, showing the user the diff first, as the `daily` skill does.
6. **Write the rules from the context file.** Run `python "<daily>/scripts/category_rules.py" --from-context` (add `--adopts "Client=Existing name"` for each rule the user chose to adopt) in the **Bash** tool, like every other configured read in this skill. The clients and their terms are read from the file you just wrote, in file order, which is the order that wins a title two clients both match. Nothing is transcribed into a second list. The script backs the existing rules up into the workspace before it writes a thing, so there is no diff to show.

**The user's own internal work gets no category and no client.** Leave it uncategorized: internal time is carried at review by an exclusion and the internal-admin task, and inventing a client name for the user's own firm puts a name in the client field that their timesheet provider does not have.

**Where the activity source will not take the write** — an `ERR` naming the settings endpoint, or one saying the write was refused — this machine needs the rules entered by hand. **Say so out loud**: a step that looks like it worked and did nothing is the failure this whole skill exists to prevent. Then give the user this, with the address from "Before you start" in place of `<activity-url>` and their own codes substituted:

> **Add one category for each client.** I could not add them for you on this computer, so this part is by hand. A category tells ActivityWatch which windows belong to which client.
>
> - Open `<activity-url>` in your browser. Go to **Settings**, then **Categories**.
> - Click **Add a category**. Name it for the client.
> - Set its rule type to **Regex**. Type the client's words with a `|` between each one and no spaces around it, like this: `ACME|AcmePortal`
> - Click **Save**.
> - Do the same for each client.

Save per category rather than once at the end. Keep the category flat and named for the client: the timeline joins a category's name path with `>`, so a grouping parent changes the label every downstream consumer matches on.

**Verify** and **If it fails** — run `references/checks.md` (check `category-rules`) and do not move on until it passes.

### 5. The screenshot task is registered and actually capturing

Screenshots are what disambiguate generic activity into the right client, so this is a required step on Windows, not an optional one. On macOS and Linux there is no capture pipeline shipped: say so, and skip to the finish.

**Do** — if a `WorkScreenshots` task already exists, read it first: `(Get-ScheduledTask -TaskName WorkScreenshots).Actions.Arguments`. Registration replaces it with one built from the script's own defaults, so any non-default `-StartTime`, `-EndTime`, `-IntervalSeconds` or capture directory in there is the user's and has to be passed through again — nothing carries it for you. Someone migrating from a hand-installed copy is the likely case, and a task silently back on 08:30–20:00 every 2.5 minutes surfaces a fortnight later as a day with no evidence on it.

Then run the `daily` skill's `scripts/setup_screenshot_pipeline.ps1`, resolved as described above. It installs Pillow and mss if they are missing and registers one scheduled task: `WorkScreenshots`, firing `screenshot_capture.py` **where it sits in the skill folder** every ~2.5 minutes on weekdays between **08:30** and **20:00**, writing one PNG per monitor into a dated folder it creates itself. Running the script in place is what makes a later skill update take effect with nothing to re-copy. `-StartTime`, `-EndTime` and `-IntervalSeconds` move that schedule, and `-DryRun` prints the task it would register — command line, schedule and capture directory — while installing and registering nothing, which is the cheap way to check a path before committing to it. Re-running the script is safe rather than additive: it registers with `-Force`, so there is one `WorkScreenshots` however many times it is run. Standing a task up is this step; `references/first-run.md` in the `daily` skill diagnoses one that has stopped.

If `TIMESHEET_SCREENSHOTS_DIR` is configured, pass the same path as `-ScreenshotsDir`: the task runs outside any session and never sees the configured value, so passing it explicitly is what keeps the reader and the writer pointed at the same folder.

**Read that value in the Bash tool** — `python "<daily>/scripts/screenshot_capture.py" --where` — and put the result on `-ScreenshotsDir`, **quoted**: `-ScreenshotsDir "C:\My Shots"`, because an unquoted path with a space binds only up to the space and errors. This `.ps1` is necessarily run through PowerShell, and the configuration reaches Bash tool calls alone (the same reason the probe in "Before you start" is a Bash command), so read there it comes back empty, the task registers against `~\Pictures\WorkScreenshots`, and the capture writes where nothing reads — the divergence passing it explicitly is meant to close. Use that command rather than echoing the variable: it applies the full precedence and expands a `~`, and it is the same resolution the capture script itself writes by.

**Verify** and **If it fails** — run `references/checks.md` (check `screenshot-task`) and do not move on until it passes.

### 6. The calendar is settled — on and readable, or off on purpose

The only optional step, and it is entered either way: *off* is an outcome to state, not a step to skip. A user who has never heard of the calendar gets one sentence and a choice; a user who turned it on gets the same live check the other five get, before the `daily` skill starts depending on it.

**Do** — run the `daily` skill's `scripts/calendar_day.py` for **today**, resolved as described above, **in the Bash tool** and for the same reason step 5's `--where` is read there: the configuration reaches Bash tool calls alone, so run through PowerShell this reports the calendar off on a machine that has it on.

```bash
python "<daily>/scripts/calendar_day.py" <today, YYYY-MM-DD>
```

That one command is the whole check, whatever the toggle says. **Do not read the toggle to find out first** — a command written to see whether a configured value is set writes its own answer into the transcript, which is the rule from "Before you start" and the family the 0.5.0 leak came from. This one answers by doing what the `daily` skill will do, which is the only answer that means anything: on a machine with new Outlook alone the toggle is on and the calendar still cannot be read.

**Verify** and **If it fails** — run `references/checks.md` (check `calendar`) and do not move on until it passes.

### 7. The check-in watchers are offered — on and recording, or off on purpose

Optional, and entered either way: *off* is an outcome to state, not a step to skip. Two small watchers can ask the user what they were doing, so time the computer could not see is put back to them as a question at review. Nothing is billed from an answer without the user's own yes.

**Do** — offer each watcher in one plain sentence, and ask once. Details, install and removal are in `references/checkin-watchers.md`.

> **Do you want to be asked what you were doing?** Two small helpers can ask you. Each one is optional.
>
> - **The check-in watcher** asks when you come back after being away for a while. You type a few words, like "call with ACME". It does not bill anything. At review, I ask you if that time was work.
> - **The ask watcher** asks you twice a day, on weekdays, what you are working on. It is for Mac and Linux only.
>
> Do you want the check-in watcher? Do you want the ask watcher?

On Windows, offer only the check-in watcher. The ask watcher needs a program Windows does not have, so it is not offered there. Install only what the user says yes to. On Windows, run `<daily>/scripts/setup_checkin_watcher.ps1` — add `-DryRun` first and read it back; it needs Python 3.11 or newer and no admin rights. On Mac and Linux, follow the reference; for the ask watcher it has the install, the two weekday prompts, the check and the removal. A **no** is written as `Check-in watcher: off` or `Ask watcher: off` under `## Preferences` in `Timesheets/.context.md`, and asked about never again.

**Verify** and **If it fails** — run `references/checks.md` (check `checkin-watchers`) and do not move on until it passes.

## When endpoint security is the answer

`references/endpoint-security.md` holds two things: how to establish that a step was actually blocked rather than merely broken, and the exact allow-list requests to hand over once it has been. Read it at the point a step fails in a way that looks like a block — never earlier, and never instead of the checks above.

## Done

Setup is finished when steps 1 to 7 have each passed their own check on this machine, and the two required configuration values are present. Step 6 passes on a calendar that was read *and* on a calendar deliberately left off; it is unfinished only where the toggle is on and the read failed. If either came back `MISSING` at the start, re-run **the same probe from "Before you start"** — not a new one written for the occasion, which is where the value-printing version came from the first time.

Say so plainly, and say what is now true: the activity source is recording, browser titles carry their addresses and, in a one-client profile, its client code, the rules classify them, the workspace holds a context file naming each client, and screenshots are being captured on a schedule. **Where step 6 left the calendar on, say that too** — the calendar is read as a fourth source, so a meeting sat through without touching the keyboard is drafted as a block rather than lost as a break, and one the activity source cannot corroborate is put as a question at review rather than billed. It is the one thing here whose result is invisible until a day is drafted, so a user not told about it meets it as a surprise in their first timesheet. Leave the sentence out where the calendar is off. Then hand over the two things that are not this skill's:

- The check-in watchers are on, or off by your choice. Say which, in one line each. A watcher that is on only asks; a work answer comes back to the user as a question at review and is never billed without their yes.
- The `daily` skill has its own first run. It finds the sections of `Timesheets/.context.md` step 4 left as template — colleagues, external contacts, work kinds, how they bill, what to exclude — and walks the user through them. Tell the user where the file is, that it is theirs to edit, and that the category rules are rebuilt from its **Category terms** lines, so a new word for a client goes there. Then tell them to invoke that skill next, for a day they have already worked.
- Two things go stale on their own and are worth naming now: a new client needs its **Category terms** adding to `.context.md` — its rule follows on the next run, and a single-client browser profile also wants its own tag — and a screenshot task that stops firing does so silently. The health check is in `references/checks.md`.

Nothing in this skill posts to a timesheet provider, and the `daily` skill will not either without passing the confirmation gate. Say that too — it is the question a new user has and does not always ask.

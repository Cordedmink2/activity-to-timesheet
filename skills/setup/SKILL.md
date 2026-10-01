---
name: setup
description: Walk a first-time user through installing this plugin — offering to install what the machine is missing, installing the activity source and the browser extensions, interviewing them about their clients to tag single-client browser profiles, write a starter workspace context file and write and verify their category rules, getting the screenshot task past endpoint security, and settling whether the Outlook calendar is read — verifying each one before moving on, in plain language for a non-technical user. User-invoked.
compatibility: Windows-first. Reads a running ActivityWatch server over HTTP (default http://localhost:5600). Step 5 registers a Windows scheduled task and needs PowerShell plus Python 3.10+; on macOS and Linux there is no screenshot capture to set up and that step is skipped. Step 6 is entered everywhere, and reports the calendar off on any machine without classic Outlook. Needs a harness that can execute local commands and make HTTP requests. Posts nothing to any timesheet provider.
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

Six steps, and then a stated finish.

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

   | Missing | Windows | macOS | Linux |
   |---|---|---|---|
   | ActivityWatch | `winget install -e --id ActivityWatch.ActivityWatch` | `brew install --cask activitywatch`, where `brew` exists | the downloads page in step 1 |
   | Python 3.10+ | `winget install -e --id Python.Python.3.13` | `brew install python@3.13` | the distribution's own package |
   | Git Bash | `winget install -e --id Git.Git` | — | — |
   | PowerShell 7 (optional) | `winget install -e --id Microsoft.PowerShell` | — | — |

   Ask once — "Shall I install these for you?" — and run only what the user says yes to: a machine-wide install is theirs to choose. Say before you start that Windows may show an administrator prompt and that it is theirs to accept. Anything declined falls back to the step's own instruction, as if nothing had been offered.

   **Verify each install by re-running its probe**, not by the installer's exit code. A new Python is not on this session's `PATH` until the shell restarts — probe it by `py` or by the path winget printed. A new Git Bash reaches nothing until a new session starts, because the hook that publishes the configuration runs at session start; say so, and have the user restart and invoke setup again rather than carrying on without it.

## How the interview runs

Steps 3 and 4 settle who the user's clients are and how each one shows up on screen. Settle it as an **interview in rounds**: each decision opens the ones that depend on it, and a round asks every question whose prerequisites are already answered — the **frontier** — and nothing that waits on an answer not yet given.

- **Number each question and give your recommended answer under it**, with one plain line on why. The user can reply "yes to all" or correct a number.
- **Facts are yours to find, never the user's to supply.** Profile names come from `Local State`; client codes already in use from the `SEEN` lines; the addresses each client's work opens from the `HOST` lines; the user's own old categories from the `RULE` lines — all printed by `--inspect` (step 4.1). Ask the user only for decisions: which client a thing belongs to, and what to call it.
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

**Verify** — `GET <activity-url>/api/0/buckets/` returns JSON holding a key that starts `aw-watcher-window_` and one that starts `aw-watcher-afk_`. Note the hostname suffix on those keys; the buckets are hostname-scoped and the rest of this run needs the window bucket's full id.

**If it fails** — a refused connection means it is not running (the tray icon, not the installer, is the thing to check). HTML or a 404 instead of JSON means something else holds the port. If the user runs the server on another machine or port, that address is `TIMESHEET_ACTIVITY_URL`: have them set it through `/plugin configure billables` rather than passing it per-command forever, and use the new address for the rest of this run.

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

**Verify** — have the user browse for a minute in a work profile, then read recent events: `GET <activity-url>/api/0/buckets/<window-bucket>/events?limit=1000`. Keep the events whose `data.app` is a browser, and check that at least one `data.title` carries a hostname — a `host.tld` pattern such as `example.com`. Do not expect all of them to: a profile without the extension, and any window opened before it was installed, legitimately have none. **Zero across every browser event is the failure**, and it localises to this step rather than to the tagging in step 3.

Where the user added the web watcher, `GET <activity-url>/api/0/buckets/` also holds an `aw-watcher-web-<browser>_<host>` bucket for each browser they added it to, updated in the last few minutes. Edge and Vivaldi report as `chrome`; Brave, Opera and Firefox as themselves. A declined web watcher is recorded as off, not as a failure.

**If it fails** — the usual cause is the extension living in one profile while the user browsed in another. Ask which profile they just used and check it directly. A web watcher with no bucket is usually the same fault, or, in Firefox, the extension's own consent page left unaccepted. A managed browser can also refuse the install outright: on Edge or Chrome under policy, each extension has to be allow-listed by ID — `ignpacbgnbnkaiooknalneoeladjnfgb` for URL in title, `nglaklhklhcoonedhgnpgddginnjdadi` for the web watcher — a precise request, which `references/endpoint-security.md` says how to evidence before making.

### 3. A browser profile dedicated to one client carries that client's tag

**Do** — run `--inspect` (step 4.1) first, so its lines are in hand, then the interview's rounds 1 and 2. Round 2 decides which of their profiles belongs to exactly one client. **A profile tag goes on those and nowhere else.** A general or default profile — the one they use for everything, their own admin, research, the tools they share across clients — carries none, and its time is attributed from what is on the page instead. A short, collision-resistant **client code** is settled for every client either way; give the user this once per single-client profile, with that profile's own code substituted:

> **Add this client's code to this profile.** The code is a short label, like ACME. It tells your timesheet that everything in this profile is for that client.
>
> - In this profile, open `edge://extensions` (or `chrome://extensions`). Find **URL in title**. Click **Details**, then **Extension options**.
> - Change the title format to: `{title}-{hostname}{path}{args}{hash} - [ACME]`. Put this profile's code where it says `ACME`.
> - Click **Save**.
> - Do the same in each of your other one-client profiles, with that client's code. In a profile you use for more than one client, do not change anything.

**A user with one profile for every client tags nothing**, and this step is only its second check below — that no old tag is left in that profile. Say so plainly: their client work is recognised from the addresses and words on each page, which step 4 chooses with them from the `HOST` lines.

The narrowing is the point, and it is not tidiness. The code in a tag is the first of that client's category terms in step 4, so it labels every window carrying it — and the first matching rule wins, so a tag on a general profile swallows every page in it that names a real client: an hour of Acme's work done in the shared profile bills to whichever client that profile is tagged for. **A user who has already tagged a general profile** — most people migrating from an earlier version of this walkthrough — clears that profile's format string back to `{title}-{hostname}{path}{args}{hash}` in the same options page.

Write down which profile carries which code: step 4 composes a rule from it and writes it into the workspace context file as that client's **Profile tag**.

**Verify** — have the user browse for a minute in each profile they tagged, then read recent events as in step 2 and check the browser titles for a bracketed code, `\[[A-Za-z0-9-]{2,12}\]`. Two checks, and the second is new:

1. Go through the codes the user named one at a time: **each has to appear in at least one real title.** A code with zero matches is a profile whose format string was never saved — which is invisible in the options page, because it shows what was typed rather than what was stored.
2. Have them browse for a minute in the **general** profile, if they have one, and check those titles carry **no** bracketed code. A leftover tag there is the failure this step now exists to prevent, and it is silent: everything still classifies, to the wrong client.

**If it fails** — the format was saved in a different profile from the one browsed in; or it was typed and the page left without saving. Re-check per profile, not in aggregate: an aggregate pass hides the one profile that is wrong, and that client's whole day comes back uncategorized. A code appearing in the general profile's titles is the reverse of the same fault — the format string was pasted into the wrong profile's options page, and it is cleared there rather than fixed in step 4.

### 4. The clients are written down and their category rules verified

This step is yours, not the user's. Each client gets **one** category rule, made from a few words that only that client's work puts in a window title — its **category terms**. You choose them with the user in the interview's round 3, write them into the workspace context file, and hand them to a bundled script that gates, backs up, writes and verifies. **The user sees the terms, never a regular expression or a JSON body.**

**Do** — in this order.

1. **Read what is already there.** In the Bash tool, `python "<daily>/scripts/category_rules.py" --inspect` — again where step 3 tagged profiles, so the new tags show. It prints one `RULE` line per category the activity source holds — `[managed]` for the ones this plugin wrote, `[unmanaged]` for the user's own — with the share of recent window titles each matches and an example of what it caught. Above them, one `SEEN` line per profile tag the titles really carry, with the Edge profile it appeared in: those are the client codes as they really appear, so choose from them rather than from what the user remembers. Then one `HOST` line per address the browser titles carry, most-seen first, counted in distinct titles rather than time: these are what a page names its client by when no tag does. A shared host — `dev.azure.com`, `github.com` — is only ever listed with the organisation after it, because bare it is every client's at once.
2. **Offer to adopt the unmanaged ones, once, as a single list.** Read each rule's name and the titles it caught, work out which client it is for and which of its words are really that client's, and put the whole set to the user **in plain words and in one pass** — "you already have six categories; I read them as Acme from the word ACME, Beta from BetaPortal, …" — never one question per rule. They accept the list, correct the parts that are wrong, or skip adoption entirely. Keep the words that name the client and drop the ones any client's work could produce: `Invoice|ACME|Acme Holdings` adopts as `ACME` and `Acme Holdings`, not `Invoice`.

   **An adopted rule names what it takes over.** Put the existing category's name on the candidate as `"adopts": "Work>Acme"` — the name exactly as the `RULE` line printed it, `>`-joined if it is nested. Without that the compiler has no way to know the old rule and the new one are the same rule, and the user ends up with both. `[managed]` rules need no `adopts`: the rebuild replaces them whole, including every rule an older version of this plugin wrote.

   What they accept is written into `Timesheets/.context.md` at 4.5, with every other term — the rules are rebuilt from each client's **Category terms** line, so a term that lives only in this conversation is dropped by the next rebuild.

   What they skip is left exactly as it is and goes on working, below the rules you write. **A rule the inspect marked `OVER the … ceiling` is worth raising by name** while you have their attention: it matches a large share of everything they do, and since the first matching rule wins it is taking the label off whichever rule should have won.
3. **Choose each client's terms with the user — up to eight, and usually two to four.** This is the interview's round 3. In this order:
   - **the client code** — `ACME`. It is in the profile tag, in the name of a browser profile kept for the client, and usually in the workspace or folder the user opened for them, so one term catches all three. Where the code is also an ordinary word — `LEDGER`, `NIMBUS` — use its tag, `[LEDGER]`, instead: the bare word turns up in pages that have nothing to do with the client. A code made up in this interview for an untagged client is in none of those places yet: offer it as a term only where the `HOST` lines or the user's own folders already carry it, and keep it in the context file either way;
   - **the names of the client's own products or apps** — the system you build for them, the name their app goes by (`AcmePortal`);
   - **the client's full name**, where it differs from the code;
   - **the addresses only this client's work opens**, from the `HOST` lines — its SharePoint site (`acmetrust.sharepoint.com`), its DevOps organisation (`dev.azure.com/acme-it`), its Dynamics environment (`acme-uat.crm6.dynamics.com`), its own website. These carry the client for a user whose one profile holds every client, and they are worth offering to a tagged user too, for the pages they open outside that client's profile. Read each one back to the user in plain words — "the Acme Trust SharePoint site" — rather than as an address.

   Nothing any other client's work could produce: no domain words (`Invoice`, `Timesheet`), no product any client could be using (`Dynamics`, `SharePoint`, `Xero`), no application names, and no address shared by every tenant (`go.xero.com`, `app.asana.com`) or opened by the user's own firm (round 1). A client's own tenant on a shared product is theirs; the product's name is not. A term is a literal word, matched without case anywhere in the app name or the title, so write it as the user would say it — never a pattern.
4. **Say what you are about to do, in one line per client** — "Acme: ACME, AcmePortal, Acme Holdings, the Acme Trust SharePoint site. Beta: BETA, Fabric Orders. Your six other categories stay as they are." — and go on once they say yes. That confirmation is the end of the interview.
5. **Write the workspace and its context file** — before the rules, because the script stamps the rules with a fingerprint of this file, and a file written after them reads as changed on the `daily` skill's next run.
   - **The workspace** is the folder round 1 chose. From a clone of the repo, `install/setup_workspace.ps1 -Workspace <path>` (POSIX: `install/setup_workspace.sh <path>`); otherwise create `Timesheets/`, `daily_exports/` and `.mcp/` in it yourself. A folder other than the one sessions start in also needs `TIMESHEET_WORKSPACE` set to it — through `/plugin configure billables`, or the `.env` on an exported install — once the folder exists; until the next session, pass `--workspace <path>` to the script below.
   - **`Timesheets/.context.md` is never written over.** If it does not exist, copy the `daily` skill's `references/context.md.example` to it, then fill in the **AW buckets** section from step 1's bucket ids and one **Active client projects** section per client: **Client name** as the provider spells it, **Profile tag** where step 3 set one (else delete that line), **Category terms**, and under **Signals** the profile and the addresses behind its host terms. Leave every other section as the template has it: those are the `daily` skill's first run to fill. If the file already exists — a user re-running setup — write the same facts into it as a change, showing the user the diff first, as the `daily` skill does.
6. **Write the rules.** Write the candidates to a JSON file with your file-writing tool:

   ```json
   [{"client": "Acme", "terms": ["ACME", "AcmePortal", "Acme Holdings", "acmetrust.sharepoint.com"]},
    {"client": "Beta", "terms": ["BETA", "Fabric Orders"], "adopts": "Work>Beta"}]
   ```

   and pass its path: `python "<daily>/scripts/category_rules.py" --candidates <file>`. One entry per client, in the order that should win a title two clients both match, and each client's terms exactly as its **Category terms** line has them. Run it in the **Bash** tool, like every other configured read in this skill. The script backs the existing rules up into the workspace before it writes a thing, so there is no diff to show.

**The user's own internal work gets no category and no client.** Leave it uncategorized: internal time is carried at review by an exclusion and the internal-admin task, and inventing a client name for the user's own firm puts a name in the client field that their timesheet provider does not have.

**Where the activity source will not take the write** — an `ERR` naming the settings endpoint, or one saying the write was refused — this machine needs the rules entered by hand. **Say so out loud**: a step that looks like it worked and did nothing is the failure this whole skill exists to prevent. Then give the user this, with the address from "Before you start" in place of `<activity-url>` and their own codes substituted:

> **Add one category for each client.** I could not add them for you on this computer, so this part is by hand. A category tells ActivityWatch which windows belong to which client.
>
> - Open `<activity-url>` in your browser. Go to **Settings**, then **Categories**.
> - Click **Add a category**. Name it for the client.
> - Set its rule type to **Regex**. Type the client's words with a `|` between each one and no spaces around it, like this: `ACME|AcmePortal`
> - Click **Save**.
> - Do the same for each client.

Save per category rather than once at the end, which is the order `README.md` § "The category rules" describes for this fallback. Keep the category flat and named for the client: the timeline joins a category's name path with `>`, so a grouping parent changes the label every downstream consumer matches on.

**Verify** — the same evidence either way, and never the UI having appeared to save.

- **The context file** — `Timesheets/.context.md` exists in the workspace, and carries one client section per client with a **Category terms** line matching what the candidates passed. Read it back rather than trusting the write.
- **On the written route**, the script's own output: one `VERIFY` line per client, naming how many sampled titles its terms matched and how many hours **the activity source itself** labels with the rule. The script asks the activity source rather than trusting its own matching: a rule it matched that the activity source labels nothing with fails the run with an `ERR`, as does a rule missing from what reads back. A `WROTE` line with no `VERIFY` lines under it is the same thing.
- **On the manual route**, re-run `--inspect` and read the `RULE` lines. Judge them against **the codes the user demonstrated in this session**, not against every rule on the machine: each of those must match at least one real title. A rule that matches nothing is only a defect if its code is one the user just showed you working — on a machine that has been running a while, a zero usually means that client simply wasn't worked on inside the sampled window, and calling it broken sends the user to fix something that is fine. A leftover placeholder (`New class`, `FILL ME`) is a defect either way.

**If it fails** — the gate refuses in words, and a refusal anywhere means *nothing* was written, so answer every line it printed and re-run. In order of how often each is the answer:

- **`UNVERIFIED … matches none of the sampled titles`** — written, not refused, so the run exits 0 and this is easy to read past. For a code the user demonstrated in this session it is a failure: that word is not in this machine's titles. Usually the code and the tag disagree, or the profile carrying it was never browsed in, which is really a step 3 failure surfacing here; the `SEEN` lines printed under it are the codes really there. `suspect` means the client's other terms matched and this one did not; `dormant` means none of them did, which for a client not worked on lately is fine. For a user with one profile for every client, a code with no `SEEN` line is expected — nothing tags their titles — and their client's addresses are what has to match.
- **`OVERLAP … both match`** — written, but two clients' terms catch the same titles, and the first client in the file takes them. Usually one term is shared, or is a word both clients' work produces: drop it and re-run.
- **`over the … ceiling`** — a term is too broad. The first matching rule wins, so a broad term does not merely add noise, it takes the label off a correct rule. Drop it, or use a longer word only this client's work produces.
- **`over the 8 a client's rule takes`**, **`one candidate per client`**, **`a candidate needs "terms"`** — all three are yours, not the user's. Fix the file and re-run.
- **`ERR … labels none of them`** — the activity source does not match the rule the way the script did. That is a defect in this plugin, not in the user's terms: the backup the run printed is the rule set as it was, and it goes upstream by `<daily>/references/reporting-issues.md`.
- **An `ERR` about the settings endpoint or the write** — the manual route above, loudly.

If this install carries `demo/tag-rule-demo.html`, opening it shows the matching failures live and is faster than explaining them.

### 5. The screenshot task is registered and actually capturing

Screenshots are what disambiguate generic activity into the right client, so this is a required step on Windows, not an optional one. On macOS and Linux there is no capture pipeline shipped: say so, and skip to the finish.

**Do** — if a `WorkScreenshots` task already exists, read it first: `(Get-ScheduledTask -TaskName WorkScreenshots).Actions.Arguments`. Registration replaces it with one built from the script's own defaults, so any non-default `-StartTime`, `-EndTime`, `-IntervalSeconds` or capture directory in there is the user's and has to be passed through again — nothing carries it for you. Someone migrating from a hand-installed copy is the likely case, and a task silently back on 08:30–20:00 every 2.5 minutes surfaces a fortnight later as a day with no evidence on it.

Then run the `daily` skill's `scripts/setup_screenshot_pipeline.ps1`, resolved as described above. It installs Pillow and mss if they are missing and registers one scheduled task: `WorkScreenshots`, firing `screenshot_capture.py` **where it sits in the skill folder** every ~2.5 minutes on weekdays between **08:30** and **20:00**, writing one PNG per monitor into a dated folder it creates itself. Running the script in place is what makes a later skill update take effect with nothing to re-copy. `-StartTime`, `-EndTime` and `-IntervalSeconds` move that schedule, and `-DryRun` prints the task it would register — command line, schedule and capture directory — while installing and registering nothing, which is the cheap way to check a path before committing to it. Re-running the script is safe rather than additive: it registers with `-Force`, so there is one `WorkScreenshots` however many times it is run. Standing a task up is this step; `references/first-run.md` in the `daily` skill diagnoses one that has stopped.

If `TIMESHEET_SCREENSHOTS_DIR` is configured, pass the same path as `-ScreenshotsDir`: the task runs outside any session and never sees the configured value, so passing it explicitly is what keeps the reader and the writer pointed at the same folder.

**Read that value in the Bash tool** — `python "<daily>/scripts/screenshot_capture.py" --where` — and put the result on `-ScreenshotsDir`, **quoted**: `-ScreenshotsDir "C:\My Shots"`, because an unquoted path with a space binds only up to the space and errors. This `.ps1` is necessarily run through PowerShell, and the configuration reaches Bash tool calls alone (the same reason the probe in "Before you start" is a Bash command), so read there it comes back empty, the task registers against `~\Pictures\WorkScreenshots`, and the capture writes where nothing reads — the divergence passing it explicitly is meant to close. Use that command rather than echoing the variable: it applies the full precedence and expands a `~`, and it is the same resolution the capture script itself writes by.

**Verify** — three checks, and the second is the one that catches a stale install:

1. `Get-ScheduledTaskInfo -TaskName WorkScreenshots` returns without error.
2. `(Get-ScheduledTask -TaskName WorkScreenshots).Actions` — read the `Execute` and `Arguments` back and confirm they name **this** install's `screenshot_capture.py` and a current interpreter. A machine that once had a hand-installed copy keeps a task pointing at the old path; it registers, reports `Ready`, and captures into a folder nobody reads. On a plugin install the stored path names a *versioned* cache folder, and the session-start hook re-points it at the current version each time a session starts — so a plugin-install task still naming a superseded version usually means the hook is not running on this machine, which is the same gap as configuration not arriving, and `references/first-run.md` § "When the configuration does not arrive" in the `daily` skill is the route. The other cause is a task the hook could not write, which is the elevated-shell registration under "If it fails" below; the hook gives up on that one until the next release rather than retrying every session.
3. Fire one capture by hand and confirm the files land: run `screenshot_capture.py` from the sibling skill's `scripts/`, **passing the same directory as its first argument**, then list that directory's folder for today and confirm `HH-MM-SS_m1.png` files appeared, one per monitor. The script would fall back to the configured value on its own, but only if the session published it — pass it explicitly so a check that comes back empty means no capture rather than two folders. Multi-monitor machines write `_m1`, `_m2`, `_m3`; a laptop on its own writes only `_m1`.

**If it fails** — decide which of three it is before telling the user anything, because they lead to completely different asks:

- **`Access is denied` on registration** — a previous task was registered from an elevated shell, so the task file is owned by `BUILTIN\Administrators`. Do *not* just have them re-run setup elevated: that succeeds and re-creates the task with the same owner, so the next ordinary re-register fails identically and they are back here. Two steps — `Unregister-ScheduledTask -TaskName WorkScreenshots -Confirm:$false` from an **elevated** PowerShell, then the setup script from a **normal** one, which is what leaves the task owned by the user.
- **`No module named mss` / `No module named PIL`, or the task's `LastTaskResult` is `0x80070002`** — an interpreter problem, not a security one. The stored path is absolute, so a Python upgrade or reinstall breaks every trigger from that moment on. Re-run the setup script, or pin the interpreter with `-PythonExe <path>`.
- **The task registers, reports `Ready`, and no image ever appears** — this is the one that is usually endpoint security. Read `references/endpoint-security.md` before saying so to the user: it has to be evidenced before it is escalated.

### 6. The calendar is settled — on and readable, or off on purpose

The only optional step, and it is entered either way: *off* is an outcome to state, not a step to skip. A user who has never heard of the calendar gets one sentence and a choice; a user who turned it on gets the same live check the other five get, before the `daily` skill starts depending on it.

**Do** — run the `daily` skill's `scripts/calendar_day.py` for **today**, resolved as described above, **in the Bash tool** and for the same reason step 5's `--where` is read there: the configuration reaches Bash tool calls alone, so run through PowerShell this reports the calendar off on a machine that has it on.

```bash
python "<daily>/scripts/calendar_day.py" <today, YYYY-MM-DD>
```

That one command is the whole check, whatever the toggle says. **Do not read the toggle to find out first** — a command written to see whether a configured value is set writes its own answer into the transcript, which is the rule from "Before you start" and the family the 0.5.0 leak came from. This one answers by doing what the `daily` skill will do, which is the only answer that means anything: on a machine with new Outlook alone the toggle is on and the calendar still cannot be read.

**Verify** — the command's own answer, which is one of three. Every refusal you can get here exits 1 — only a malformed date exits 2 — so judge it by the `ERR` line and never by the exit code:

1. **A JSON day, exit 0** — the calendar is on and working. Report **how many events it holds and the first one's subject**, and nothing else out of it: that is enough to show the adapter reached the right calendar, and the rest of the day's meetings are the user's business rather than the transcript's. An empty `events` list passes too — say which it is, though, because "the calendar was read and today has nothing on it" and "the calendar could not be read" look identical if you don't.
2. **`ERR the calendar is off: TIMESHEET_OUTLOOK_CALENDAR is not set to true …`** — the ordinary state, and most installs. Offer it in one sentence: *the plugin can read your Outlook calendar, so a meeting you sat through without touching the keyboard is billed rather than lost as a break, and a meeting it cannot corroborate is put to you as a question instead of billed.* If they want it, the route is `/plugin configure billables` → **Read my Outlook calendar** — or, on the exported install, the `TIMESHEET_OUTLOOK_CALENDAR=true` line of the `.env` beside the sibling skill's `SKILL.md`, the same file "Before you start" routes a gap to. **Then run the same command again — and read the answer by the route they took**, because the two routes reach a running session differently. A `.env` is read by the script itself, so the re-check should now print the day, and a second `off` means the line is wrong: `true` is the one spelling of on. **The dialog will still say off, and that is expected rather than a failure** — declared configuration is published to a session when it *starts*, so a value set now reaches the next one. Say that, and say what closes it: start a new session and run this one command again before the first `/billables:daily`. Don't send them back to the dialog, and don't record step 6 as passed on the strength of the dialog having been filled in — a user who is not told this reads their first drafted day, sees no calendar in it, and concludes the feature does not work. If they don't want it, say the calendar stays off and move on: off is exactly today's behaviour and costs them nothing.
3. **`ERR the calendar stays off: …`, or an adapter failure whose reason names classic Outlook** — the toggle is on and this machine cannot read a calendar. Say so and say why: the shipped adapter drives **classic Outlook**'s object model, which new Outlook (the store app) does not have at all, and which macOS and Linux have no equivalent of. Then **have them turn the toggle back off**, and do not leave this as a note for later — an on-but-unreadable calendar is not a quiet no-op. The `daily` skill stops on a calendar it was told to read and could not, so every run from here would fail on this same line until the toggle goes off.

**If it fails** — the answers that are not about the calendar at all, and are the more likely ones:

- **The re-check still says off in a session that started *after* the dialog was filled in, or straight away on the `.env` route.** That is no longer the expected answer above; it is the same gap as a `MISSING` in "Before you start" — the message names the shell when the configuration cannot have reached the command at all — and `references/first-run.md` in the `daily` skill owns the diagnosis. Check the spelling first: `true`, and nothing else, is on.
- **An `ERR` naming the activity source.** Step 1 passing does not keep the server running, and the corroboration verdict is computed against the day's window events, so there is no calendar day to be had without it. That is step 1 to re-check, not the calendar.
- **An `ERROR:` saying no timezone could be read.** The wrapper needs the zone to know which day it is reading, and takes it from the configuration or from the machine; this machine offered neither, or named a zone this interpreter cannot load — the message says which, and names `tzdata` where that is the cause. Route the user to the configuration dialog for the zone, or to the install the message names; the calendar is untested until one of them is done, so say that rather than reporting step 6 passed.
- **`No such file`, or a `ModuleNotFoundError`.** The sibling path, not the calendar: `daily` on a plugin install and `billables-daily` in the shared export, per "Finding the files this skill needs".
- **`ERR the calendar adapter … is not there: this copy of the skill does not ship it`.** The wrapper is present and the adapter beside it is not, which is a half-copied install rather than anything the user configured. Re-install rather than re-configure — and until it is fixed the toggle has to go off, for the reason in outcome 3.

## When endpoint security is the answer

`references/endpoint-security.md` holds two things: how to establish that a step was actually blocked rather than merely broken, and the exact allow-list requests to hand over once it has been. Read it at the point a step fails in a way that looks like a block — never earlier, and never instead of the checks above.

## Done

Setup is finished when steps 1 to 6 have each passed their own check on this machine, and the two required configuration values are present. Step 6 passes on a calendar that was read *and* on a calendar deliberately left off; it is unfinished only where the toggle is on and the read failed. If either came back `MISSING` at the start, re-run **the same probe from "Before you start"** — not a new one written for the occasion, which is where the value-printing version came from the first time.

Say so plainly, and say what is now true: the activity source is recording, browser titles carry their addresses and, in a one-client profile, its client code, the rules classify them, the workspace holds a context file naming each client, and screenshots are being captured on a schedule. **Where step 6 left the calendar on, say that too** — the calendar is read as a fourth source, so a meeting sat through without touching the keyboard is drafted as a block rather than lost as a break, and one the activity source cannot corroborate is put as a question at review rather than billed. It is the one thing here whose result is invisible until a day is drafted, so a user not told about it meets it as a surprise in their first timesheet. Leave the sentence out where the calendar is off. Then hand over the two things that are not this skill's:

- The `daily` skill has its own first run. It finds the sections of `Timesheets/.context.md` step 4 left as template — colleagues, external contacts, work kinds, how they bill, what to exclude — and walks the user through them. Tell the user where the file is, that it is theirs to edit, and that the category rules are rebuilt from its **Category terms** lines, so a new word for a client goes there. Then tell them to invoke that skill next, for a day they have already worked.
- Two things go stale on their own and are worth naming now: a new client needs its **Category terms** adding to `.context.md` — its rule follows on the next run, and a single-client browser profile also wants its own tag — and a screenshot task that stops firing does so silently. `Get-ScheduledTaskInfo -TaskName WorkScreenshots` with a `LastTaskResult` of `0` is the health check.

Nothing in this skill posts to a timesheet provider, and the `daily` skill will not either without passing the confirmation gate. Say that too — it is the question a new user has and does not always ask.

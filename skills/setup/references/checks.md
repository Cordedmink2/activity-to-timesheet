# Install checks

Every check setup runs, once, in setup order. Each entry has its own **Verify** and **If it fails**. `setup` runs them as it walks; `troubleshoot` runs them in this order and stops at the first one that fails. Nothing else copies a probe from here: cite the entry by its id.

## Check activity-source — The activity source is installed and running

**Verify** — `GET <activity-url>/api/0/buckets/` returns JSON holding a key that starts `aw-watcher-window_` and one that starts `aw-watcher-afk_`. Note the hostname suffix on those keys; the buckets are hostname-scoped and the rest of this run needs the window bucket's full id.

**If it fails** — a refused connection means it is not running (the tray icon, not the installer, is the thing to check). HTML or a 404 instead of JSON means something else holds the port. If the user runs the server on another machine or port, that address is `TIMESHEET_ACTIVITY_URL`: have them set it through `/plugin configure billables` rather than passing it per-command forever, and use the new address for the rest of this run.

## Check browser-extensions — The browser extensions are recording

**Verify** — have the user browse for a minute in a work profile, then read recent events: `GET <activity-url>/api/0/buckets/<window-bucket>/events?limit=1000`. Keep the events whose `data.app` is a browser, and check that at least one `data.title` carries a hostname — a `host.tld` pattern such as `example.com`. Do not expect all of them to: a profile without the extension, and any window opened before it was installed, legitimately have none. **Zero across every browser event is the failure**, and it localises to this step rather than to the tagging in step 3.

Where the user added the web watcher, `GET <activity-url>/api/0/buckets/` also holds an `aw-watcher-web-<browser>_<host>` bucket for each browser they added it to, updated in the last few minutes. Edge and Vivaldi report as `chrome`; Brave, Opera and Firefox as themselves. A declined web watcher is recorded as off, not as a failure.

**If it fails** — the usual cause is the extension living in one profile while the user browsed in another. Ask which profile they just used and check it directly. A web watcher with no bucket is usually the same fault, or, in Firefox, the extension's own consent page left unaccepted. A managed browser can also refuse the install outright: on Edge or Chrome under policy, each extension has to be allow-listed by ID — `ignpacbgnbnkaiooknalneoeladjnfgb` for URL in title, `nglaklhklhcoonedhgnpgddginnjdadi` for the web watcher — a precise request, which `references/endpoint-security.md` says how to evidence before making.

## Check profile-tags — A browser profile dedicated to one client carries that client's tag

**Verify** — have the user browse for a minute in each profile they tagged, then read recent events as in step 2 and check the browser titles for a bracketed code, `\[[A-Za-z0-9-]{2,12}\]`. Two checks, and the second is new:

1. Go through the codes the user named one at a time: **each has to appear in at least one real title.** A code with zero matches is a profile whose format string was never saved — which is invisible in the options page, because it shows what was typed rather than what was stored.
2. Have them browse for a minute in the **general** profile, if they have one, and check those titles carry **no** bracketed code. A leftover tag there is the failure this step now exists to prevent, and it is silent: everything still classifies, to the wrong client.

**If it fails** — the format was saved in a different profile from the one browsed in; or it was typed and the page left without saving. Re-check per profile, not in aggregate: an aggregate pass hides the one profile that is wrong, and that client's whole day comes back uncategorized. A code appearing in the general profile's titles is the reverse of the same fault — the format string was pasted into the wrong profile's options page, and it is cleared there rather than fixed in step 4.

## Check category-rules — The clients are written down and their category rules verified

**Verify** — the same evidence either way, and never the UI having appeared to save.

- **The context file** — `Timesheets/.context.md` exists in the workspace, and carries one client section per client with a **Category terms** line matching what `--from-context` read. Read it back rather than trusting the write.
- **On the written route**, the script's own output: one `VERIFY` line per client, naming how many sampled titles its terms matched and how many hours **the activity source itself** labels with the rule. The script asks the activity source rather than trusting its own matching: a rule it matched that the activity source labels nothing with fails the run with an `ERR`, as does a rule missing from what reads back. A `WROTE` line with no `VERIFY` lines under it is the same thing.
- **On the manual route**, re-run `--inspect` and read the `RULE` lines. Judge them against **the codes the user demonstrated in this session**, not against every rule on the machine: each of those must match at least one real title. A rule that matches nothing is only a defect if its code is one the user just showed you working — on a machine that has been running a while, a zero usually means that client simply wasn't worked on inside the sampled window, and calling it broken sends the user to fix something that is fine. A leftover placeholder (`New class`, `FILL ME`) is a defect either way.

**If it fails** — the gate refuses in words, and a refusal anywhere means *nothing* was written, so answer every line it printed and re-run. In order of how often each is the answer:

- **`UNVERIFIED … matches none of the sampled titles`** — written, not refused, so the run exits 0 and this is easy to read past. For a code the user demonstrated in this session it is a failure: that word is not in this machine's titles. Usually the code and the tag disagree, or the profile carrying it was never browsed in, which is really a step 3 failure surfacing here; the `SEEN` lines printed under it are the codes really there. `suspect` means the client's other terms matched and this one did not; `dormant` means none of them did, which for a client not worked on lately is fine. For a user with one profile for every client, a code with no `SEEN` line is expected — nothing tags their titles — and their client's addresses are what has to match.
- **`OVERLAP … both match`** — written, but two clients' terms catch the same titles, and the first client in the file takes them. Usually one term is shared, or is a word both clients' work produces: drop it and re-run.
- **`over the … ceiling`** — a term is too broad. The first matching rule wins, so a broad term does not merely add noise, it takes the label off a correct rule. Drop it, or use a longer word only this client's work produces.
- **`over the 8 a client's rule takes`**, **`cannot read the \`Category terms\` line`**, **`no client`** — all yours, not the user's. Fix the **Category terms** line in `Timesheets/.context.md` and re-run.
- **`ERR … labels none of them`** — the activity source does not match the rule the way the script did. That is a defect in this plugin, not in the user's terms: the backup the run printed is the rule set as it was, and it goes upstream by `<daily>/references/reporting-issues.md`.
- **An `ERR` about the settings endpoint or the write** — the manual route above, loudly.

If this install carries `demo/tag-rule-demo.html`, opening it shows the matching failures live and is faster than explaining them.

## Check screenshot-task — The screenshot task is registered and actually capturing

**Verify** — three checks, and the second is the one that catches a stale install:

1. `Get-ScheduledTaskInfo -TaskName WorkScreenshots` returns without error.
2. `(Get-ScheduledTask -TaskName WorkScreenshots).Actions` — read the `Execute` and `Arguments` back and confirm they name **this** install's `screenshot_capture.py` and a current interpreter. A machine that once had a hand-installed copy keeps a task pointing at the old path; it registers, reports `Ready`, and captures into a folder nobody reads. On a plugin install the stored path names a *versioned* cache folder, and the session-start hook re-points it at the current version each time a session starts — so a plugin-install task still naming a superseded version usually means the hook is not running on this machine, which is the same gap as configuration not arriving, and `references/first-run.md` § "When the configuration does not arrive" in the `daily` skill is the route. The other cause is a task the hook could not write, which is the elevated-shell registration under "If it fails" below; the hook gives up on that one until the next release rather than retrying every session.
3. Fire one capture by hand and confirm the files land: run `screenshot_capture.py` from the sibling skill's `scripts/`, **passing the same directory as its first argument**, then list that directory's folder for today and confirm `HH-MM-SS_m1.png` files appeared, one per monitor. The script would fall back to the configured value on its own, but only if the session published it — pass it explicitly so a check that comes back empty means no capture rather than two folders. Multi-monitor machines write `_m1`, `_m2`, `_m3`; a laptop on its own writes only `_m1`.

**If it fails** — decide which of three it is before telling the user anything, because they lead to completely different asks:

- **`Access is denied` on registration** — a previous task was registered from an elevated shell, so the task file is owned by `BUILTIN\Administrators`. Do *not* just have them re-run setup elevated: that succeeds and re-creates the task with the same owner, so the next ordinary re-register fails identically and they are back here. Two steps — `Unregister-ScheduledTask -TaskName WorkScreenshots -Confirm:$false` from an **elevated** PowerShell, then the setup script from a **normal** one, which is what leaves the task owned by the user.
- **`No module named mss` / `No module named PIL`, or the task's `LastTaskResult` is `0x80070002`** — an interpreter problem, not a security one. The stored path is absolute, so a Python upgrade or reinstall breaks every trigger from that moment on. Re-run the setup script, or pin the interpreter with `-PythonExe <path>`.
- **The task registers, reports `Ready`, and no image ever appears** — this is the one that is usually endpoint security. Read `references/endpoint-security.md` before saying so to the user: it has to be evidenced before it is escalated.

## Check calendar — The calendar is settled — on and readable, or off on purpose

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

## Check checkin-watchers — The check-in watchers are offered — on and recording, or off on purpose

**Verify** — for a watcher the user said yes to, run `python "<daily>/scripts/checkin_answers.py" --probe checkin` (or `--probe ask`) and read `found`. `true` with a `newest_event` is recording. `true` with none means it is installed and has not yet been answered: say so, and do not call it a failure. For a watcher the user declined, nothing is run, and the finish says "off, by your choice".

**If it fails** — `found` is `false` after an install:

- Run `python "<daily>/scripts/checkin_answers.py" --diagnose`. If it names `two-afk-buckets`, the check-in watcher stops itself because it finds two activity records from two computers. Say that in plain words, name the old one it reports, and offer to export it first. Delete it only after the export is saved and the user says yes to that named record. Never delete without both.
- The watcher needs Python 3.11 or newer. A Python 3.10 install is the next most likely cause: say so, and offer the install table in "Before you start".
- A watcher that is installed but never prompts: on Windows check `Get-ScheduledTask -TaskName CheckinWatcher`. Whether the task starts after the next sign-in cannot be seen from here; say that, and ask the user to tell you after their next sign-in.

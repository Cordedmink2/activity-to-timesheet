# The check-in watchers

Two optional watchers ask the user what they were doing. Both write to ActivityWatch. The `daily` skill reads the answers with `scripts/checkin_answers.py` and puts a work answer to the user as a **check-in question** at review. An answer is context, never a block (ADR-0009).

## The check-in watcher

`aw-watcher-ask-away`, pinned at **0.0.6** (the version on PyPI that setup installs). When the user comes back from being away for five minutes or more, a small window asks what they were doing. The answer is one event over the away gap, in the bucket `aw-watcher-ask-away_<host>`, with the words in `data.message`.

- **Needs Python 3.11 or newer.** An older Python cannot install it.
- **Windows:** run `skills/daily/scripts/setup_checkin_watcher.ps1`. It installs the pinned package for the current user and registers one scheduled task, `CheckinWatcher`, that starts the watcher at logon. No admin rights: logon type Interactive (the window needs the user's desktop), run level Limited, restart on failure. `-DryRun` prints the task and changes nothing. `-Force` replaces an existing task. Check it with `Get-ScheduledTask -TaskName CheckinWatcher`.
- **Mac and Linux:** `python3 -m pip install --user aw-watcher-ask-away==0.0.6`. `aw-qt` starts any `aw-*` program it finds on its path, so the watcher can be added to the `aw-qt` autostart list; otherwise run it from a per-user login item or a user unit. This was read from `aw-qt`'s source, not run on a Mac.
- **Verify:** `python checkin_answers.py --probe checkin`. `found: true` with a `newest_event` is recording.
- **Remove:** on Windows run the removal line the script prints when it finishes, then `python -m pip uninstall aw-watcher-ask-away`. On Mac and Linux, the pip uninstall and the autostart entry. (The two-shell removal rule for a task registered elevated is step 5's; this task is per-user and never elevated.)

### Two activity records from two computers

The watcher finds the AFK record by looking for any name that contains `afk`. With one from an old computer as well, it stops with "too many afk buckets". The watcher has no option to choose one (read from its source), so the only fix is to remove the stale record. `checkin_answers.py --diagnose` names both and says which is stale. The fix is: export the stale record first, save the file, and delete it only if the user says yes to that record by name. Setup never deletes anything on its own.

## The ask watcher

`aw-watcher-ask` asks a short question on a schedule. It is offered on **Mac and Linux only**: it needs a program Windows does not ship, and Billables adds no new program to Windows. A point-in-time answer cannot explain a gap, so its answers are hints for the day, never questions.

It is not on PyPI. It installs from GitHub, pinned to one commit, and it needs `zenity` (the dialog program) and Python 3.9 or newer.

**Install**

1. Check `zenity --version`. If it is missing: Linux `sudo apt install zenity` (or the same with `dnf` or `pacman`); Mac `brew install zenity`. Tell the user first: `sudo` asks for their password, and it is theirs to type.
2. `pipx install "git+https://github.com/bcbernardo/aw-watcher-ask.git@4a4536c3b012d3b681f6dff7d1ab22d0de02a738"`. If there is no `pipx`, use `python3 -m venv ~/.local/share/aw-watcher-ask` and install into it with its own `pip`.
3. Check `aw-watcher-ask run --help` prints the options. If it does not, stop and tell the user.

**Schedule: two prompts on weekdays.** The program stays running and asks at the times of a cron line. The line `0 10,15 * * 1-5 0` means 10:00 and 15:00, Monday to Friday. Ask the user for other times if they want them. The command is:

`aw-watcher-ask run --question-id work.now --question-type entry --title "What are you working on?" --text "A few words, for example: call with ACME" --timeout 120 --schedule "0 10,15 * * 1-5 0"`

Keep it running after sign-in, and ask the user before you write any of these files:

- **Linux:** write `~/.config/systemd/user/aw-watcher-ask.service` with `[Service]`, `ExecStart=<full path from "command -v aw-watcher-ask"> run ...` (the arguments above) and `Restart=on-failure`, plus `[Install]` with `WantedBy=default.target`. Then run `systemctl --user enable --now aw-watcher-ask`.
- **Mac:** write `~/Library/LaunchAgents/local.aw-watcher-ask.plist` that runs the same command with `RunAtLoad` and `KeepAlive`. Then run `launchctl load ~/Library/LaunchAgents/local.aw-watcher-ask.plist`.

**Verify.** Run `python checkin_answers.py --probe ask`. `found: true` means the bucket `aw-watcher-ask_<host>` exists. It appears after the first prompt is answered, so before 10:00 the honest answer is "installed, not yet answered". On Linux also run `systemctl --user is-active aw-watcher-ask`; it must print `active`. An unanswered prompt writes nothing that is used. A person must answer the real dialog; setup cannot do that for them.

**Remove.** Linux: `systemctl --user disable --now aw-watcher-ask`, delete the service file, then `pipx uninstall aw-watcher-ask`. Mac: `launchctl unload` the plist, delete it, then `pipx uninstall aw-watcher-ask`. The old answers stay in ActivityWatch; they are not deleted.

This was read from the program's own help and source and the schedule line was parsed with its `croniter` library. It was not run through a real dialog, a systemd unit or launchd on a Mac.

## Not used: block check-ins (upstream PR #5)

Upstream PR #5 would also ask at the end of each work block. It is not used. An independent review found its own README says to keep those options off for unattended use, it has no quiet hours, cooldown or daily cap, it was never tested on Windows, and it is unmerged and stacked on another open PR. Setup never offers it.

## What setup records

A decline is one line under `## Preferences` in `Timesheets/.context.md`: `Check-in watcher: off` or `Ask watcher: off`. The `daily` skill treats it as a settled choice: it is not asked again and it is not reported as a failure.

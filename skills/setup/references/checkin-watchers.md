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

`aw-watcher-ask` asks a short question on a schedule. It is offered on **Mac and Linux only**: it needs a program Windows does not ship, and Billables adds no new program to Windows. The offer is two prompts a day on weekdays, which the user can change. A point-in-time answer cannot explain a gap, so its answers are hints for the day, never questions.

## Not used: block check-ins (upstream PR #5)

Upstream PR #5 would also ask at the end of each work block. It is not used. An independent review found its own README says to keep those options off for unattended use, it has no quiet hours, cooldown or daily cap, it was never tested on Windows, and it is unmerged and stacked on another open PR. Setup never offers it.

## What setup records

A decline is one line under `## Preferences` in `Timesheets/.context.md`: `Check-in watcher: off` or `Ask watcher: off`. The `daily` skill treats it as a settled choice: it is not asked again and it is not reported as a failure.

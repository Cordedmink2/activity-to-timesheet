---
name: troubleshoot
description: Use when something stopped working — screenshots stopped, a day came back uncategorized or empty, the capture task or a watcher is silent. Runs the same install checks setup uses, in order, stops at the first one that fails, and gives that check's documented fix.
compatibility: Windows-first. Runs the `daily` skill's bundled Python scripts from a sibling directory, so it needs Python 3.10+ on the PATH and a harness that can execute local commands. Reads a running ActivityWatch server (default http://localhost:5600). Posts nothing to any timesheet provider.
---

# troubleshoot

The fault is in the first check that fails. The checks are the ones setup runs, kept once in the sibling `setup` skill's `references/checks.md`, so this skill runs them and copies none.

## Finding the files this skill needs

The scripts ship with the `daily` skill, in a directory beside this one. Resolve **this** skill's folder from where this `SKILL.md` was read, then look for a sibling named `daily` — or, in the shared export, `billables-daily`. The references are in the sibling `setup` skill (`billables-setup` in the export). Check which prefix exists rather than guessing.

## How to talk to the user

Assume the user is not technical. Plain Simplified Technical English: say what you are checking and why in one line, then the result. Commands, patterns and addresses stay in your own tool calls.

## Steps

1. **Start where the user points.** A user who says "my screenshots stopped" starts with the screenshot check (`screenshot-task`); "nothing is categorized" at `category-rules`; "my browser pages are bare" at `browser-extensions`. Otherwise start at the first check. Do not ask a menu.
2. **Run the checks in setup order and stop at the first one that fails.** Open `references/checks.md` and run each entry's **Verify**, in order, from the starting check onward. A check that passes is one line. The first one that fails is the finding: do not run later ones, because a failure upstream (the activity source) explains every failure after it.
3. **Give that check's own fix.** Read its **If it fails** and follow it. A screenshot task whose interpreter is gone (a missing interpreter — a Python upgrade or reinstall) is the `0x80070002` fix inside check `screenshot-task`; re-register it. A fault that looks like a block rather than a break is `references/endpoint-security.md` in the sibling `setup` skill, which says how to evidence it first. A capture task that stopped or the configuration not arriving is `first-run.md` in the sibling `daily` skill, under "When the configuration does not arrive". Cite these; do not copy them.
4. **Say what you found, in plain words,** and what you changed. Re-run the failing check and report it passing. Anything that needs the user — an administrator prompt, a credential in the configuration dialog — is in "What only a person does" in the `setup` skill.
5. **If every check passes**, say so, and that the fault is not in the install. A defect in the plugin itself is a report: hand the user a draft through `daily/references/reporting-issues.md`, "From the setup menu". Never file it for them.

Nothing here posts to a timesheet provider.

---
name: onboard-client
description: Use when the user says they have a new client, or wants to add or change a client's category terms. Asks only for decisions, finds the facts in the recorded titles, shows the context-file diff, and on a yes writes the file and rebuilds the category rules in the same step.
compatibility: Runs the `daily` skill's bundled Python scripts from a sibling directory, so it needs Python 3.10+ on the PATH and a harness that can execute local commands. Reads a running ActivityWatch server (default http://localhost:5600). Posts nothing to any timesheet provider.
---

# onboard-client

A new client touches one place: the client's section in `Timesheets/.context.md`. The category rules are compiled from that file, so this skill writes the file and rebuilds the rules in the same step, and keeps no other list of terms.

## Finding the files this skill needs

The scripts ship with the `daily` skill, in a directory beside this one. Resolve **this** skill's folder from where this `SKILL.md` was read, then look for a sibling named `daily` — or, in the shared export, `billables-daily`, because that directory is flat and every skill in it is prefixed. The references are in the sibling `setup` skill (`billables-setup` in the export): `references/choosing-terms.md` and `references/checks.md`. Check which prefix exists rather than guessing.

## How to talk to the user

Assume the user is not technical. Write in plain Simplified Technical English: one line of context first, short active sentences, one instruction per sentence. Show them only what they have to decide. Patterns, JSON and commands stay in your own tool calls.

## Steps

1. **Ask only for decisions.** The client's name exactly as their timesheet provider spells it, a short client code, and a profile tag if one browser profile is for this client alone. Ask for nothing you can find yourself.
2. **Find the facts yourself.** Run `python "<daily>/scripts/category_rules.py" --inspect` in the Bash tool and read the `SEEN`, `PROFILE` and `HOST` lines. Choose the client's terms from them with the user, by the rules in `references/choosing-terms.md` — that file is the one home of those rules; do not restate them. Terms that no recorded title carries yet are still fine to write: the next step says so honestly.
3. **Show the diff.** Show the change to `Timesheets/.context.md` as a diff: the new `###` client section with its **Client name**, **Category terms**, and the profile and addresses under **Signals**. Never write or overwrite the file without it, and write only after a yes. If the file does not exist, run the setup skill's workspace step first.
4. **On a yes, write the file and rebuild the rules in the same step.** Write the section, then run `python "<daily>/scripts/category_rules.py" --from-context` in the Bash tool. The script reads every client's terms from the file you just wrote, so there is no separate list of terms to keep and nothing to copy.
5. **Read the answer.** One `VERIFY` line per client, including the new one, means the rules match what the machine records. A term with `UNVERIFIED` or `dormant` for the new client means its terms are **not yet seen** in the recorded titles: say that in plain words — "I have not seen this client's work on your computer yet" — and that it is not a failure. The rule works once the work appears. A `REFUSE` line means nothing was written: fix the **Category terms** line and run again. Any other `ERR` goes to the `troubleshoot` skill.

Run the same checks setup uses when a step fails, from `references/checks.md`, by id. This skill copies no check.

The user's own internal work gets no client and no category. Nothing is billed from this skill: the `daily` skill's confirmation gate is unchanged.

# Final verify (Step 6b)

Runs on the **post preview**: the blocks about to be posted, including every edit the user made at Step 6. It exists so the confirmation gate (Step 8) always confirms a table that was checked against the evidence once more, after the last human edit. It is never skipped.

## Procedure

1. **Fan out.** One read-only subagent per block, on the cheapest model the harness offers. Run them in parallel. Give each only its own block and the brief below.
2. **Wait for every subagent** before acting on any of them.
3. **Verify each finding yourself.** A subagent finding is a lead, not a fact. Re-run the cited command (`activity_timeline.py --window`, `afk_blocks.py`, the capture) and read the evidence. Adopt a change only if you see it too. Discard the rest, and say which findings you discarded.
4. **Apply what held.** Apply a verified change to the block under Step 6's guards. If it would make a *user-dictated* block or a declared exception differ from what they asked for, ask rather than change it. Re-run `afk_blocks.py <date> --cover ...` over the final entries.
5. **If anything changed, reprint the whole table**, not a diff, with each changed block marked (`✏️`) and a one-line reason. Then go to Step 7/8. If nothing changed, say "final verify: no changes" in one line.
6. **No subagents available?** Run the checklist below yourself, block by block. Same checks, same verification, same output.

## Subagent brief

A subagent has no conversation context, so the brief must carry everything. It is a template: **fill every `<…>` slot before dispatch**, and never send a brief with a slot empty or a relative path in it.

> You are checking one block of a draft timesheet. **Read only. Change nothing, post nothing, write no files.**
> Block: `<date> <start>-<end>`, client/project `<client>`, note `<note>`.
> Scripts live in `<absolute skill script folder>` (the folder this skill's `SKILL.md` was read from, plus `scripts/`). Run them from there by absolute path, never relative to the workspace:
> `python <skill folder>/scripts/activity_timeline.py <date> --window <start>-<end> --full <utc-offset flag>` and `python <skill folder>/scripts/afk_blocks.py <date> --window <start>-<end> <utc-offset flag>`.
> UTC offset: `<the --utc-offset <hours> this run used, or "none: use the default zone">`; pass it on every command exactly as given.
> Captures to look at, all monitors: directory `<absolute screenshot directory>`; files `<exact capture filenames or timestamps inside the block, every monitor: _m1, _m2, …>`. Look at no others.
> Signals from `.context.md`: for the billed client `<client>`: `<its signals: apps, titles, URLs, paths>`. For the day's other clients: `<each other client and its signals>`.
> Report, per check below, `OK` or `PROBLEM` with the raw signals behind it (the line, the time, the app/title, the capture filename). Do not guess; if the evidence is absent say `NO EVIDENCE`. Report signals only: **do not decide which client a stretch belongs to**; the main agent attributes.

Attribution stays with the main agent, as `references/disambiguation.md` requires: the subagent returns raw signals and the main agent matches them to a client.

## Checklist (per block)

- **Start.** Is the first active minute at or just after `start`? Is there active time before `start` that no block covers?
- **End.** Is the last active minute at or just before `end`? Does the block run into a break or past `work_end`?
- **Client/project.** Does the window/title/capture evidence in the span point to the client billed?
- **Hidden switch.** Does any stretch inside the block, 15 minutes or longer (the threshold is the 0.25 hr minimum entry: anything shorter could not be billed as its own entry), point to a different client or project? Name its start, end and client.
- **Idle.** Is a long AFK stretch inside the block billed as work?

Report only problems that the evidence supports. A block with no evidence either way stays as drafted.

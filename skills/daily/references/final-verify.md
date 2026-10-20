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

> You are checking one block of a draft timesheet. **Read only. Change nothing, post nothing, write no files.**
> Block: `<date> <start>-<end>`, client/project `<client>`, note `<note>`.
> Run `python scripts/activity_timeline.py <date> --window <start>-<end> --full` and `python scripts/afk_blocks.py <date> --window <start>-<end>`; look at any captures in that window.
> Report, per check below, `OK` or `PROBLEM` with the evidence (the line, the time, the app/title). Do not guess; if the evidence is absent say `NO EVIDENCE`.

## Checklist (per block)

- **Start.** Is the first active minute at or just after `start`? Is there active time before `start` that no block covers?
- **End.** Is the last active minute at or just before `end`? Does the block run into a break or past `work_end`?
- **Client/project.** Does the window/title/capture evidence in the span point to the client billed?
- **Hidden switch.** Does any stretch inside the block, 15 minutes or longer, point to a different client or project? Name its start, end and client.
- **Idle.** Is a long AFK stretch inside the block billed as work?

Report only problems that the evidence supports. A block with no evidence either way stays as drafted.

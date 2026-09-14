# Disambiguating a flagged block

`SKILL.md` Step 5 loads this file. It owns the **procedure** for resolving a block whose
attribution is not settled: the ladder, what the ladder is not allowed to decide, and the
switch-point protocol for a day that alternated between clients.

What *raises* a flag stays in `classification-rules.md`, which is read on every run. A rule that
only loads once a block is already flagged can never be the thing that flags one.

It does not own the *contract*. That a run surfaces its uncertainty rather than picking — the 🔸
marks in Steps 3, 6 and 8, and "Don't fabricate confidence" — stays in `SKILL.md`, because it
binds every run and this file loads only on the runs that need it.

## What brings a block here

A **LOW** confidence rating, which `classification-rules.md` § "Confidence rating" defines and
raises — that rating stays there because it is assigned on every run, and a file that loads only
after a flag exists cannot be what raises one. So does a thin `active_ratio` (Step 3), and an
ambiguous attribution that never scored LOW on its own.

Two signals raise a 🔸 at classification time even though nothing about the block *looks*
ambiguous; they have their own section below.

## What the ladder does not decide

**AFK status is settled by the AFK watcher** — never re-infer active/idle from screenshots, and
never from the calendar. Screenshots and zooms answer only *which client/project*; a corroborated
calendar event answers *how long the meeting was* (Step 3) and says nothing about idle either.

Every rung below is a question about attribution. None of them moves a boundary the skeleton
already drew.

## The ladder

Climb it in order, and stop at the rung that answers.

1. **Zoom the timeline first:** `python scripts/activity_timeline.py <date> --window HH:MM-HH:MM`
   folds in Firefox/Chrome web-watcher rows — richer URL/title signals without opening images.
2. **Then screenshots**, for generic apps that don't name their client (XrmToolBox, bare VS Code,
   terminals): find the nearest `HH-MM-SS_mN.png` to the ambiguous timestamps, read the env URL /
   workspace / repo / work item on screen. Different clients in different screenshots within one
   block → split the block, per "Interleaved days" below.
   - **When several blocks need screenshot-checking, delegate the reading to a cheap subagent**
     (e.g. `Agent` with `model: "haiku"`) rather than reading every capture in the main session —
     image tokens add up fast once a date needs more than a couple of captures, and this is a
     plain read-what's-on-screen task a smaller model handles fine. Give the subagent no
     conversation context of its own, so its prompt must carry: the screenshot directory and exact
     timestamps to check (all monitors — `_m1`/`_m2`/…), the signal list from `.context.md`, the
     AFK-settled rule above, and the probe-economically procedure below (3 spread, densify around
     flips) if any block needs a switch point. It reports **raw signals per capture** (app,
     environment URL, ticket numbers, Edge profile, workspace) — never a billing verdict;
     attribution against `.context.md` stays with the main session.
3. **Still ambiguous → ask the user**, showing which screenshots you checked, what you saw, and
   the candidate clients.

## Two signals that arrive here already flagged

`classification-rules.md` §5 and §6 rank these and raise the 🔸. What to do with one is here.

- **An admin tool whose title never names its environment** — XrmToolBox, database/API clients,
  RDP sessions, CLI auth profiles. Go straight to rung 2: only a screenshot of the connection
  answers it. Rung 1 cannot — the environment was never in a title for the zoom to find — and
  neither can the block next door (`classification-rules.md` §6, "Adjacency stops at an admin
  tool").
- **A Claude Code task slug that triangulates against nothing** (`classification-rules.md` §6,
  which is where what a slug is worth is settled). Rungs 1 and 2 are looking for the thing it has
  to triangulate against — an Edge profile, a repo path, an open client environment. Where none
  appears, this is rung 3: ask. A slug is never promoted to the answer for want of a better one.

## Interleaved days — find the switch point, don't average

The costliest real-world misattributions are long blocks on days where the user alternated between
two clients: the whole block gets billed to whichever client *dominates* the category rollup, and
the other client's hours land on the wrong invoice.

**Triggers — treat the block as interleaved when any of these hold:**
- The day rollup shows ≥2 clients with ≥30 min each, and a single proposed block is >1 hr
- The zoomed timeline alternates between two clients' signals within the block
- Any `!MULTI` span, or a block titled by an agent-session file (`CLAUDE.md`, `AGENTS.md`, plan `.md`s)
- An autonomous agent ran during the block (`classification-rules.md` §"Focused window ≠ active attention")

**Procedure:**
1. Zoom the timeline over the block (`activity_timeline.py <date> --window …`) and note every point
   where the client signal flips.
2. Probe screenshots economically: start with ~3 spread across the block (start / middle / end),
   then densify only around detected flips until each switch point is bracketed to ~10 min. Check
   the other monitors at every probe, and record which client's work is on screen.
3. Locate the **switch point(s)**: the boundary between runs of consistent client evidence. Split
   the block there. A switch point is a real boundary even with no AFK gap — client A until 16:10
   and client B after is two entries, at whatever timestamps the evidence shows.
4. Attribute each sub-block to its own client. Never bill the whole block to the rollup-dominant
   client while a second client shows ≥15 min of evidence inside it — if the evidence can't pin the
   switch point, ask the user rather than averaging.
5. If the two "clients" are actually work vs. personal/upskilling/internal interleaved, the same
   procedure applies — carve out the non-billable or internal runs, and say so in the presentation.
6. **A named Teams meeting recurring in fragments through the block is its own sub-block** (the
   user attending while multitasking) — carve it out with its own attribution per
   `classification-rules.md` §3, even though no single fragment is long.  The parallel coding stays
   with its own client.
7. **Some days have no switch point to find.** Two workspaces with an agent session in each, focus
   alternating every 1–3 min for hours, is genuinely parallel work — step 2 will keep finding flips
   and never bracket a boundary. Don't manufacture one, and don't keep spending screenshots hunting
   it. Ask per step 4. If the user hands the split back to you ("you decide"), tally each client's
   minutes across the block from the zoom, allocate proportionally, and place each boundary where
   that client's corroborating evidence clusters (a CRM/ADO/SharePoint run, a commit, a bug fixed).
   A client whose fragments total under step 4's ≥15 min bar is noise — leave that time with the
   dominant client. Say in the presentation that the boundary is an allocation rather than an
   observed switch, so the user knows which kind of call they are approving.


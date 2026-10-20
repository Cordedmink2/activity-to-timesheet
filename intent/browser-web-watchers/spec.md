# Spec: First-class browser address evidence in Firefox, Chrome and Edge

**Intent:** [intent.md](intent.md), Accepted 2026-10-20 (Connor, in conversation with Hermes: "Yeah I think that sounds good"; recorded in the intent's Status line)
**Author:** atlas  **Date:** 2026-10-20  **Status:** Draft (spec re-gate pending)
**Serves:** O1–O4, S1–S4, B1–B5 (inventory below)

## Summary
Browser work is attributed from the web watcher's recorded addresses wherever that helps, not only when
the run zooms into an unclear stretch. Firefox users, who have no tested URL in title extension, get the
same attribution as Edge and Chrome users. Setup installs and verifies the web watcher in each browser,
with Edge-specific steps. A user without the web watcher sees today's behaviour exactly.

## Intent inventory (labels used below)
- O1 Firefox user with the web watcher attributed as reliably as Edge/Chrome with URL in title.
- O2 Edge, Chrome and other supported Chromium browsers use web-watcher addresses wherever they improve attribution.
- O3 setup installs and verifies the web watcher per browser, with Edge steps, and says plainly what is and isn't supported.
- O4 no web watcher → today's behaviour exactly.
- S1 Firefox + web watcher, no URL in title: a day of client browsing classifies to the right clients
  with no more unattributed browser time than the same day in Edge.
- S2 Edge: setup's install link and verification both work and the bucket is found.
- S3 without the web watcher, `daily` output for a recorded test day is unchanged.
- S4 `pytest` and `pyright` green.
- B1 addresses read locally only (refusal 3). B2 an address attributes work; it never decides whether
  the user was working (refusal 5). B3 personal browsing never billable because a tab was open.
  B4 no client hosts or names ship (refusal 4). B5 URL in title stays required where it is today
  unless proven redundant; dropping it is Reserved.

## Problem → benefit → stories
Window titles name a page but not its address, so client attribution in a browser depends on URL in
title, which Firefox lacks; the web watcher's addresses are read only on zoom. The benefit is fewer
unattributed browser stretches, Firefox parity, and less guessing. US-1 is Firefox parity, US-2 wider use
in Chromium browsers, US-3 setup, US-4 the protections, US-5 no regression.

## User stories

```yaml
id: US-1
as: a consultant who does client work in Firefox
want: my browser time attributed to the right client from the addresses the web watcher records
so_that: Firefox work is not left unattributed for lack of URL in title (O1, S1)
criteria:
  - id: AC-1
    text: On a recorded test day of client browsing in Firefox with the web watcher and no URL in title, the run attributes browser time to clients using the recorded addresses matched against the client terms in the context file, with unattributed browser time no greater than the same browsing recorded in Edge with URL in title. Serves O1, S1.
    check: judged
    bar: The paired Firefox and Edge fixture days (same sites, same clients, synthetic hosts) produce per-client browser totals within one sampling interval of each other, and the Firefox day's unattributed browser minutes are less than or equal to the Edge day's.
    probe: Reviewer runs the timeline and daily drafting on the paired fixture days and compares per-client totals.
    expect: {}
  - id: AC-2
    text: The same client host terms already in the context file are what match addresses; no second list of hosts is introduced. Serves O1, B4.
    check: judged
    bar: Address matching reads the context file's Category terms (or rules compiled from them) and nothing else; no new per-client host list exists in the workspace or the plugin.
    probe: Reviewer reads the plan's matching design and the shipped code.
    expect: {}
```

```yaml
id: US-2
as: a consultant who works in Edge, Chrome, Brave, Vivaldi or Opera
want: the web watcher's addresses used wherever they improve attribution, not only in a zoom
so_that: fewer browser stretches come back unclear (O2)
criteria:
  - id: AC-1
    text: Where a browser window's title carries no client signal but the web watcher recorded an address for that tab at that time, the address is used to attribute it, outside zoom as well as within it. Serves O2.
    check: judged
    bar: On a Chromium fixture day where some tabs lack the tag but have addresses of a known client host, those spans are attributed to that client in the compact timeline, and the number of uncategorized browser spans falls compared with main.
    probe: Reviewer compares the compact timeline at main and at the build branch on the fixture day.
    expect: {}
  - id: AC-2
    text: Where the title's signal and the address disagree, the run flags the span for the user instead of choosing silently. Serves O2, B3.
    check: judged
    bar: A fixture span whose title tag says client A and whose address is client B's host appears flagged 🔸 with both cited.
    probe: Reviewer reads the drafting of the conflicting-signal fixture span.
    expect: {}
```

```yaml
id: US-3
as: a consultant running setup with one or more browsers
want: setup to install and verify the web watcher in each browser I work in, with clear Edge steps
so_that: I get address evidence with the least effort and know what is supported (O3, S2)
criteria:
  - id: AC-1
    text: Setup opens the correct store page in each work profile of each browser (Edge from the Chrome Web Store), tells the user the one click to make, and states plainly which combinations are supported, including that Firefox has no tested URL in title and relies on the web watcher. Serves O3.
    check: judged
    bar: The shipped instructions give a working store link per browser family, Edge-specific steps, and one plain supported/unsupported statement per browser.
    probe: Reviewer reads the shipped setup instructions and checks each store link answers.
    expect: {}
  - id: AC-2
    text: On Edge, the install link and the verification both work and the web watcher's bucket for this host is found with a recent event. Serves S2.
    check: usage
    probe: Windows evidence from the windows-latest end-to-end CI job where it can drive the step, otherwise the Atlas logged ship decision plus post-release monitoring (setup transcript showing the store page opened in the named profile, the bucket found, and its last event within minutes).
    expect: {}
  - id: AC-3
    text: Setup verifies each browser's web watcher by its own bucket and recent event, reporting a browser where it is missing by name rather than in aggregate. Serves O3.
    check: judged
    bar: On a fixture bucket list with Edge and Firefox web watcher buckets but no Chrome one, setup reports Edge and Firefox verified and Chrome missing by name. On a fixture where Edge and Chrome share the one `aw-watcher-web-chrome_<host>` bucket (as real Edge does), a browser is reported verified only when a recent event is corroborated by that browser's foreground window, and otherwise reported unproven by name with one plain retry step — never verified on the shared bucket alone. Fixtures copy the real bucket and event shapes of aw-watcher-web for Firefox, Chrome and Edge.
    probe: Reviewer reads setup's verification against the fixture bucket list.
    expect: {}
```

```yaml
id: US-4
as: a consultant who also browses for personal reasons
want: an open personal tab never to be billed, and address evidence never to decide whether I was working
so_that: wider use of addresses does not mis-bill me (B1, B2, B3, B4, B5)
criteria:
  - id: AC-1
    text: Address evidence only attributes time inside spans the activity evidence already counts as active; it never adds active time, moves a break or extends a block. Serves B2.
    check: judged
    bar: The day skeleton for every fixture day is byte-identical with and without web-watcher buckets present, pinned by an automated test.
    probe: Reviewer compares skeleton outputs with and without the web-watcher buckets and reads the pinning test.
    expect: {}
  - id: AC-2
    text: An address that matches no client term never makes a span billable; a background tab (recorded but not the focused window at that time) never attributes the focused window's time. Serves B3.
    check: judged
    bar: On a fixture day with a personal site in focus and a client tab open in the background, the focused time is not attributed to the client.
    probe: Reviewer reads the drafting of the background-tab fixture.
    expect: {}
  - id: AC-3
    text: URL in title remains required for Chromium browsers in setup's instructions; no browser loses a requirement in this project. Serves B5.
    check: judged
    bar: The shipped setup instructions still mark URL in title required for Chromium browsers.
    probe: Reviewer reads the shipped setup instructions.
    expect: {}
  - id: AC-4
    text: No shipped file names a real client host or name; the neutrality and redaction guards cover the new fixtures. Serves B4.
    check: auto
    probe: {kind: command, timeout: 60, argv: [gh, run, list, -R, Cordedmink2/activity-to-timesheet, --workflow, Checks, --branch, main, --status, completed, --limit, "1", --json, conclusion, --jq, ".[0].conclusion"]}
    expect: {exit: 0, regex: "^success$"}
```

```yaml
id: US-5
as: a consultant without the web watcher
want: the daily run to behave exactly as today
so_that: the change costs nothing to users who did not install it (O4, S3, S4)
criteria:
  - id: AC-1
    text: For a recorded test day with no web-watcher buckets, the daily scripts' output is identical to today's release. Serves O4, S3.
    check: judged
    bar: Script outputs for the existing recorded fixture days are byte-identical at main and at the build branch, pinned by an automated test.
    probe: Reviewer diffs fixture-day outputs at main versus the build branch.
    expect: {}
  - id: AC-2
    text: The repository suite is green from the repo root. Serves S4.
    check: auto
    probe: {kind: command, timeout: 60, argv: [gh, run, list, -R, Cordedmink2/activity-to-timesheet, --workflow, Checks, --branch, main, --status, completed, --limit, "1", --json, conclusion, --jq, ".[0].conclusion"]}
    expect: {exit: 0, regex: "^success$"}
  - id: AC-3
    text: Pyright reports zero errors from the repo root. Serves S4.
    check: auto
    probe: {kind: command, timeout: 60, argv: [gh, run, list, -R, Cordedmink2/activity-to-timesheet, --workflow, Checks, --branch, main, --status, completed, --limit, "1", --json, conclusion, --jq, ".[0].conclusion"]}
    expect: {exit: 0, regex: "^success$"}
```

## Edge cases
- E1: The user renamed their web-watcher bucket (e.g. `edge`) in the extension's options → still found, as the zoom already does. Covered by US-3/AC-3.
- E2: Two browsers active in the same minute (one focused) → only the focused browser's address attributes. Covered by US-4/AC-2.
- E3: A shared host (`dev.azure.com`, `github.com`) → matched only with the organisation path after it, as the HOST lines already require. Covered by US-1/AC-2.
- E4: Private/incognito windows, where the extension does not record → no address, today's behaviour. Covered by US-5/AC-1.
- E5: Web-watcher buckets from an old host name → only this host's are read. Covered by US-3/AC-3.
- E6: Managed browsers where store installs are blocked by policy → setup says so and points to the existing endpoint-security allow-list guidance; no policy is changed by setup. Covered by US-3/AC-1.
- E7: Firefox with a URL-in-title-like extension the user installed themselves → not relied on; addresses come from the web watcher. Covered by US-1/AC-1.

## Non-goals
- No dropping URL in title as a requirement for any browser (Reserved).
- No browsing history beyond what the web watcher already records locally; nothing sent anywhere.
- No change to how idle is decided.
- No release is cut (AGENTS.md § Releasing).

## Open questions
- If the build shows the web watcher fully covers URL in title for a browser, dev records the evidence
  and atlas brings Connor an amendment brief; this spec does not drop it. Does not change scope.
- Real Edge evidence for US-3/AC-2 needs an interactive Windows session; atlas arranges it at the build
  gate. Does not change scope.

## Changes
<!-- YYYY-MM-DD: <IDs changed> — <reason>; linked updates: plan/tasks/tests; re-review: <card> -->
- 2026-10-20: US-4/AC-4, US-5/AC-2, AC-3 — F1: auto probes now read the `Checks` workflow conclusion on main (pytest + pyright on windows-latest and ubuntu-latest) instead of bare python/pyright in a shared checkout; US-3/AC-3 bar covers the shared Edge/Chrome bucket and real aw-watcher-web shapes (plan Q1). Reason: spec gate t_a6ab865c CHANGES REQUIRED. Linked updates: plan/tasks re-point on the plan PRs. Re-review: spec re-gate (Atlas, t_3c4f0453).

# Tasks: First-class browser address evidence in Firefox, Chrome and Edge

**Plan:** [plan.md](plan.md)  **Spec:** [spec.md](spec.md)
Check: `python3 <skill_dir>/scripts/trace_check.py .` must print OK (run with spec.md present; it merges via PR #107).
Run tests as `.venv/bin/python -B -m pytest -q -p no:cacheprovider tests skills/daily/tests` and `.venv/bin/pyright` from the repo root of the build worktree. Every fixture host is `*.example`; no real client host or name anywhere.

### T1 — Preflight: fresh base, venv, baselines
serves: D1
- Test first: confirm the check-in build, the guided-setup build and #106 are merged (`git log origin/main`); read the skill map they left (where step 2's text and check live now).
- Do: worktree from fresh origin/main; `python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt`; run the suite and pyright green; record `wc -w skills/daily/SKILL.md skills/setup/SKILL.md`. Capture, before any edit, the text and `--json` output of `activity_timeline.py`, `afk_blocks.py` and the skeleton for every golden day and scenario into `$TMPDIR/before/`. Add `hotspot:` comments for both SKILL.md files on the build card. Nothing is changed in the repo.
- Evidence: commit SHA of the base, green suite and pyright output, word counts, list of captured files.

### T2 — Spike S1: web watcher semantics
serves: D4, D11
- Test first: write the three hypotheses and the expected observations (plan, Autonomous-execution prerequisites) into the decision-log draft before reading source.
- Do: read `aw-watcher-web` `heartbeat.ts`, `config.ts` and its docs for (a) whether heartbeats continue off-foreground, (b) the heartbeat interval, (c) window title shape per browser; read `TAGGED_TITLE` and the Edge fixtures. Read-only; installs nothing; no Windows host. If (a) is refuted, change D4; if (c) is refuted for a browser, change the corroboration rule; either is a plan edit before T6. A criterion-level change goes to atlas.
- Evidence: a table (assumption, observed, source file and line) committed to the decision-log entry; any PENDING-REAL-WINDOWS item named.

### T3 — Fixtures: the paired day and the hazard days
serves: US-1/AC-1, US-2/AC-1
- Test first: use `support.Day` (`.web()` exists). Build, in one fixture module under `skills/daily/tests/`: (1) a paired Firefox/Edge day (same sites, same clients; Firefox with a `firefox` bucket, no tag, titles `… - Mozilla Firefox`; Edge with a `chrome` bucket and the URL-in-title address in titles); (2) a Chromium day where some tabs lack the tag but have a known client host; (3) a conflict span (title tag client A, address client B's host); (4) a personal site in focus with a client tab open in the background; (5) a shared host with and without the org path (`dev.azure.com/<org>`); (6) a private-window event (`incognito: true`); (7) a second browser active in the same minute. Fixtures fail the neutrality and redaction guards if any real name slips in.
- Do: add the fixtures and a test per day that asserts today's (red) behaviour: unattributed browser minutes on main.
- Evidence: the tests collected and failing for the expected reason on main, with the output.

### T4 — Pin no-web identity (red first)
serves: US-5/AC-1
- Test first: a test that, for every golden day and scenario with no web buckets, equals the T1 captured `activity_timeline` text and `--json` output and the skeleton text byte for byte. It must pass on main now, and fail when a probe line is added to the output (mutation run recorded).
- Do: commit the test and the captured expected outputs as goldens (neutral data already).
- Evidence: green on main; red on the planted extra key; both outputs.

### T5 — Shared helpers in `aw_client.py`
serves: D5, US-4/AC-1
- Test first: tests for `not_afk_intervals(events)` (strict not-afk only, dedupe heartbeats, short afk not folded) and `BROWSER_APP` as shared (moved from `category_rules.py`, which imports it from `aw_client`); a module-boundary test still passes; `afk_blocks.py` unchanged (assert its file is untouched in the diff).
- Do: add both to `aw_client.py`; update `category_rules.py`'s import.
- Evidence: failing then passing output; `git diff --stat` showing `afk_blocks.py` absent.

### T6 — Address attribution in `activity_timeline.py`
serves: US-1/AC-1, US-1/AC-2, US-2/AC-1
- Test first: on the T3 fixtures: the Firefox day's per-client browser minutes are within one heartbeat interval of the Edge day's and its unattributed browser minutes are no greater; the Chromium partial-tag day has fewer uncategorized browser spans than at main and the spans carry the client; a test that reads the source of `activity_timeline.py` and `--json` and proves the only term source is the loaded classes (a second host list cannot exist: a planted `HOSTS = ` constant or a `hosts` key in any shipped file fails `tests/test_provider_neutrality`-style scan, mutation recorded).
- Do: implement `address_evidence()` per plan (event-level slice, corroboration, host+path, same `categorize`); `main()` always fetches the web buckets and the AFK events; JSON adds `source: address` and counts of slices dropped for no corroboration, only when web events exist (D10); zoom's web rows gain the category.
- Evidence: failing then passing test output; the paired-day comparison table printed by the test.

### T7 — Focus guard, active clip, query drop
serves: US-4/AC-1, US-4/AC-2
- Test first: the background-tab fixture (personal site in focus, client tab open behind) leaves the focused time unattributed; a web event while the browser is not the foreground application attributes nothing; a slice outside not-afk time keeps its title label; a URL whose client name is only in `?q=` or `#` does not match (D11); the private-window event attributes nothing; two browsers in one minute attribute only the focused one.
- Do: finish the guards in `address_evidence()`.
- Evidence: each fixture's output, failing first on a version without the guard (a mutation run per guard).

### T8 — The `!ADDR` flag
serves: US-2/AC-2
- Test first: the conflict fixture (title tag A, address host B) gives a span with `conflict`, both labels cited, text line `!ADDR title=A address=B`; agreeing signals give no flag.
- Do: add the `conflict` field and the text and JSON rendering (only with web events).
- Evidence: the fixture's compact output and its drafting reading, failing then passing.

### T9 — Pin the skeleton
serves: US-4/AC-1
- Test first: a test builds `day_skeleton()` text for every fixture day with and without web buckets and asserts byte equality. It must fail when a planted edit makes the skeleton read a web bucket (mutation recorded).
- Do: commit the test; change no skeleton code.
- Evidence: green output and the red mutation output.

### T10 — `category_rules.py` stays coherent
serves: D7
- Test first: (a) a Firefox fixture whose client's term appears only in addresses: the gate reports no `UNVERIFIED` for it and `--inspect` is unchanged for title-only terms; (b) `verify` never raises "labels none of them" for an address-only match (the activity source's answer is title-only); (c) `dormant` does not report an address-only client DORMANT while its addresses matched on the day; (d) `--status`, the stamp's `rules` and `context_fingerprint` are byte-identical to main for the same context file, and a context edit still reads `STALE` exactly as before; (e) with no web buckets all outputs are identical to main.
- Do: gate sample and `matched_addresses`; `dormant` address read; no change to `merged`, the stamp or the fingerprint.
- Evidence: failing then passing output for each of (a)-(e).

### T11 — `web_watchers.py`: per-browser verification
serves: US-3/AC-3
- Test first: on a fixture bucket list with `aw-watcher-web-edge_<host>` and `aw-watcher-web-firefox_<host>` and no Chrome bucket: `--browsers edge,firefox,chrome` prints OK for Edge and Firefox and `WEB chrome MISSING` by name; an old-host bucket is not read (spec E5); a bucket with no event in the last N minutes reads `STALE`; the shared `chrome` bucket case reads `UNPROVEN` until a recent event corroborates a foreground Edge window.
- Do: write the script (stdlib; shares `aw_client`; no entry-point import); add it to the module-boundary list and to `daily`'s Files list in one short clause.
- Evidence: the fixture run output for each case, failing then passing.

### T12 — Setup text: links, Edge steps, supported statements
serves: US-3/AC-1, US-4/AC-3
- Test first: extend `tests/test_setup_skill.py` (or the guided build's check test) so that it fails unless each browser family has a store link, Edge-specific steps, one supported/unsupported line, the managed-browser pointer, and URL in title still marked required for Chromium; it also fails if Firefox is described as having a tested URL in title.
- Do: edit step 2's text and its check where the guided-setup build put them; the verify step calls `web_watchers.py` and names a missing browser; keep Firefox's "relies on the web watcher". Check each store link answers (`curl -sI`), recording status codes. A link that does not answer is replaced, not guessed. No policy is changed by setup.
- Evidence: failing then passing test output; the link check output.

### T13 — Daily text and references, inside the word ceiling
serves: US-2/AC-2, D12
- Test first: the size test fails above 5,000 words in `skills/daily/SKILL.md`; a reference test fails unless the `!ADDR` handling and the changed zoom sentence exist.
- Do: one `!ADDR` bullet (flag 🔸 citing both labels, ask the user), the changed `activity_timeline.py` clause (web watchers are read every run, address-attributed spans are marked), one cut elsewhere in the same step; update `references/activitywatch.md` (web buckets are read each run), `references/disambiguation.md` line on zoom, and the module docstring of `activity_timeline.py`.
- Evidence: `wc -w` before and after; the passing size test.

### T14 — Guards and the full suite
serves: US-4/AC-4, US-5/AC-1, US-5/AC-2, US-5/AC-3
- Test first: run `tests/test_provider_neutrality.py tests/test_redaction.py` over the new fixtures (they must see them, proved by planting a real-looking host in a scratch copy: red).
- Do: fix whatever they find; run `.venv/bin/python -B -m pytest -q -p no:cacheprovider tests skills/daily/tests` and `.venv/bin/pyright` from the repo root; re-run the T4 identity test.
- Evidence: the command lines and the observed pass counts and `0 errors`.

### T15 — Evidence for the judged criteria and the URL-in-title record
serves: US-1/AC-1, US-1/AC-2, US-2/AC-1, US-2/AC-2, D9
- Test first: write down, before running, what each bar needs (per-client totals within one interval; Firefox unattributed minutes ≤ Edge's; fewer uncategorized spans than main; the 🔸 with both cited).
- Do: run the timeline and daily drafting on the paired days and the Chromium day at main and at the build branch (the reviewer can repeat with one command, recorded). Write the decision-log entry: the S1 table, the comparison tables, the no-second-list reading, and the D9 finding (address covers hosts; tag covers profile-dedicated work; private windows; PARTIAL coverage; recommendation to keep the requirement) for atlas's amendment brief. Do not edit the requirement.
- Evidence: the commands, the output tables, the decision-log path.

### T16 — Record PENDING-REAL-WINDOWS
serves: US-3/AC-2
- Test first: n/a (no interactive Windows host is reachable from this box).
- Do: write the exact steps a person does on Windows + Edge into the decision log: open setup, confirm the store page opens in the named Edge work profile, make the one click, wait one minute, run `web_watchers.py --browsers edge`, expect `WEB edge OK … last event N min ago`; and the optional real-day comparison for D9 (run the timeline with and without web buckets on one real Edge day; record per-client minutes). Mark US-3/AC-2 PENDING-REAL-WINDOWS. Never marked passed.
- Evidence: the decision-log entry text; the criterion's status line reading PENDING-REAL-WINDOWS.

### T17 — CHANGELOG, PR, cleanup
serves: D13
- Test first: `git tag --list` and the newest CHANGELOG heading: add to the in-progress section; bump only if the newest heading is tagged, then stop. No tag, no release.
- Do: CHANGELOG entry; open the PR to main (body starts "Dev:", lists each AC with its evidence path and the PENDING item); after the PR is up and evidence is committed, remove the worktree, the venv and `$TMPDIR` scratch. The shared checkout is never touched.
- Evidence: PR URL and head SHA; the CHANGELOG diff; `git worktree list` showing the worktree gone.

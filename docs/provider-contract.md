# The timesheet provider's command-line contract

**Status:** Proposed — drafted under #33 for review against ADR-0006 and ADR-0007. Design only:
no code moves in #33. **#35** moves the Harvest adapter behind this contract and **#37** draws
the work-item source boundary beside it; both build on this document.
**Decisions this document works within** (Atlas, #33 comment, not reopened): one command with
five subcommands; no provider wire-format name above the adapter; the confirmation gate lives
in the dispatcher once; credentials are read only by the selected adapter; `TIMESHEET_PROVIDER`
selects the adapter; five exit-code classes, numbers fixed here. Related:
[ADR-0006](./adr/0006-keep-the-provider-in-plugin-but-behind-a-command-contract.md),
[ADR-0007](./adr/0007-two-boundaries-the-provider-writes-the-sources-read.md),
[`CONTEXT.md`](../CONTEXT.md) § **Timesheet provider**.

The vocabulary is the glossary's. An **entry** is one block of billed time. A **project** and
a **task** are the provider's own, named by **opaque identifiers** the layers above never
parse, compare or build. The provider's own field names, endpoints and file names stay inside
the adapter, and `tests/test_provider_contract_doc.py` fails this document if one appears in
it (acceptance item 2, made executable).

## 1. The command

```
timesheet-provider <post|patch|lookup|list|refresh> [arguments]
```

One executable, five subcommands. It is shaped as a plugin `bin/` command, and invoked **by
path** until a split (ADR-0006): the dispatcher is `scripts/provider/bin/timesheet-provider`
inside the `daily` skill, run as `python "<daily>/scripts/provider/bin/timesheet-provider" …`.
The adapter lives behind it in `scripts/provider/harvest/`. A later split into a provider
plugin renames that one path to the bare command name and changes no argument, output line or
exit code.

**Selecting the adapter.** `TIMESHEET_PROVIDER` names it, resolved through
`skill_config.setting()` like every other key; unset or blank means `harvest`. A value that
names no adapter is a **usage error** (exit 2) whose message lists the known adapters. There is
no `--provider` flag: a second route to the same choice would be a second thing to keep
consistent, and which provider a workspace bills to is configuration, not a per-call decision.

**Conventions every subcommand shares**

- **stdout is data, stderr is diagnosis.** A caller that captures stdout gets only what the
  contract below specifies. Notices, progress and every error go to stderr.
- **Every failure starts `ERR `** on the first stderr line, followed by one sentence naming
  what failed, and exits with the class number in § 4. The provider's own status code or body
  may follow on later lines as detail, **never as the first line and never as something a
  caller branches on** — the exit code is the branch.
- **No traceback, ever.** A model reads this output, and a traceback reads as "the tool is
  broken". The dispatcher catches everything and reports it as `ERR internal …`, exit 1.
- **UTF-8** on both streams, set by the dispatcher once.
- **Times and dates are the user's wall clock.** `--date YYYY-MM-DD`, `--start HH:MM`,
  `--end HH:MM`: 24-hour, zero-padded, in `TIMESHEET_TIMEZONE`, else the machine's own zone
  (`timezone.resolve_zone()`). A `*` second-pass marker is **not** accepted: strip it before
  the call. Alternative spellings (`8:15am`, `20260812`, `2026-W33-1`) are a usage error — the
  contract has one spelling so that no adapter has to decide what a second one means.
- **A flag is given once.** A repeated value flag is a usage error, never last-wins. `--confirm`
  is the exception, being a boolean.
- **Identifiers are opaque strings.** `--project-id` and `--task-id` are whatever `lookup`
  printed. A caller never invents one and never reads meaning out of one, and an adapter
  checks its own identifiers' shape (a *code* given where an identifier belongs is refused with
  a message pointing at `lookup`).

## 2. The confirmation gate

The gate lives **in the dispatcher, once**, for `post` and `patch` — the only writes. It is the
#22 consolidation, and it replaces the per-script implementation in `harvest_write.py`.

1. The dispatcher removes `--confirm` from argv **before anything is read positionally**, wherever
   it was typed, so a value flag left without its value cannot swallow it. (A note spelled
   exactly `--confirm` is therefore eaten, the argument count or the value falls short, and
   that is a usage error rather than a silent write.)
2. It validates the arguments against this document's rules (§ 3).
3. It asks the adapter for **pre-flight checks**: `check_post(body)` / `check_patch(id, fields)`.
   These are **read-only** — a patch's check reads the existing entry to judge what the patch
   would leave behind, as `harvest_patch.py` does today — and they run on the preview and the
   confirmed run alike. A check that refuses stops here with exit 4 and **nothing is previewed**:
   the preview is what the user says yes to, so an entry that must not be created must not be
   offered. A check that cannot read exits 3 or 5; it never passes quietly.
4. Without `--confirm`, the dispatcher prints the preview and exits 0:
   ```
   WOULD POST <body>
   Nothing was posted. Re-run with --confirm to create this entry.
   ```
   ```
   WOULD PATCH <entry-id> <body>
   Nothing was changed. Re-run with --confirm to apply it.
   ```
   `<body>` is one line of JSON in the contract's own field names (§ 3.1, § 3.2), keys in the
   order given there, `ensure_ascii` off. It is the very value handed to the adapter on a
   confirmed run, so what the user approved and what is sent cannot come apart. The preview
   never borrows the `OK <id>` shape, which would have a run record an id for an entry nobody
   made.
5. With `--confirm`, the dispatcher calls `adapter.post(body)` / `adapter.patch(id, fields)`.
   **An adapter's write functions are called only on this path; an adapter never sees an
   unconfirmed write, and carries no gate of its own.** `lookup`, `list` and `refresh` carry no
   gate (ADR-0007: nothing a read does needs undoing). `refresh` writes the local catalog, not
   the provider.

SKILL.md Step 8 is where the user's yes is obtained, and what earns `--confirm` in Step 9; that
does not change.

## 3. The five commands

### 3.1 `post` — create an entry

```
timesheet-provider post --project-id ID --task-id ID --date YYYY-MM-DD
                        --start HH:MM --end HH:MM --notes TEXT [--confirm]
```

All six value flags are required (a missing one is a usage error naming it). `--start` must be
before `--end` (equal or reversed is a usage error: a provider can silently store a reversed
range as a day-long entry, so the contract refuses it before any adapter is asked). `--notes`
is free text and may be empty only as `--notes ''`; callers single-quote it (money amounts and
backticks otherwise get mangled by the shell).

Body (preview and adapter input), in this key order:

```json
{"project_id": "<id>", "task_id": "<id>", "date": "YYYY-MM-DD", "start": "HH:MM", "end": "HH:MM", "notes": "<text>"}
```

- **Success:** stdout `OK <entry-id>`, exit 0. The entry id is opaque and is what `patch` takes.
- **Preview:** § 2, exit 0.
- **The entry is always sent as a fixed interval** (a start and an end), never as a running timer
  and never as a bare duration. That is a promise the adapter keeps for every account mode and
  a caller never has to ask for.
- **Adapter refusals (exit 4, before the gate):** an entry the provider would bill wrongly. The
  Harvest adapter refuses an entry running straight through a daylight-saving change, naming the
  two entries to post instead. The refusal text is the adapter's, and travels with it.

### 3.2 `patch` — change an entry

```
timesheet-provider patch ENTRY_ID [--project-id ID] [--task-id ID] [--date YYYY-MM-DD]
                         [--start HH:MM] [--end HH:MM] [--notes TEXT] [--confirm]
```

`ENTRY_ID` is the one positional, and an id `post` or `list` printed. **At least one field flag
is required**; only the fields passed change. `--confirm` may be typed before or after the id.
When both `--start` and `--end` are given they must be ordered as in `post`; one alone is
allowed, and is what changes one side while holding the other fixed.

Body: the same keys as `post`, **only those passed**, in `post`'s order:
`WOULD PATCH <entry-id> {"start": "09:30", "notes": "…"}`.

- **Success:** stdout `OK <entry-id>`, exit 0. **Preview:** § 2, exit 0.
- **Adapter checks run on the result,** not the change: `--start` alone, `--end` alone and
  `--date` alone are each a whole entry once laid over the one already there, so the adapter may
  read the entry (exit 3 or 5 if it cannot, **including on the preview**, where previewing a
  change to a time or a date therefore needs the provider to answer).
- **There is no duration-only flag in the contract.** Today's `harvest_patch.py` carries one for
  duration-mode accounts, and it is the one flag that does not survive: on a start/end account,
  which is the usual one, it leaves an entry inconsistent or converts it to a running timer, and
  no caller in this repo passes it. Naming a duration in a contract whose every other argument
  is a clock time would make the seam describe a provider mode only one adapter has. **An
  adapter for an account that can only hold a duration maps `--start`/`--end` to that duration
  itself.** If a second provider needs a way to state one that the clock cannot, it is added then,
  against that provider (ADR-0006: revisit a rename, not a design). *Open for the reviewer:*
  this is the one capability dropped rather than carried; § 7 lists it.

### 3.3 `lookup` — resolve a project and its tasks

```
timesheet-provider lookup QUERY [--task NAME] [--json] [--cache-only]
                                [--days N] [--catalog-dir DIR]
```

`QUERY` is a project code (exact), or a fragment of a project's code, its name or its client's
name, case-insensitive. A client's name is a first-class term: the live delivery project is
often named for the *work* and matches only on the client. `--task NAME` keeps only tasks whose
name contains `NAME` (case-insensitive).

Where it looks, in order: **the catalog** (what `refresh` last wrote, **every page** of it,
de-duplicated by project), and, **only when the catalog has no match**, the user's own recent
entries on the provider — the way back to a project whose assignment was archived.
`--cache-only` skips the second step (offline use). `--days N` is how far back that second step
looks (default 180). `--catalog-dir DIR` overrides where the catalog is read from, for a test or
an unusual workspace; unset, the catalog is where `refresh` writes it (the workspace's `.mcp/`).
The catalog's file names and shape are the adapter's.

**Output, text (default).** One block per match, ranked exact code, then code-or-name, then
client-only, ties by code:

```
<code>  <project-id>  <project-name>  [<client>]
    <task-id>  <task-name>  (billable)
    <task-id>  <task-name>  (NON-billable)
```

The `  [<client>]` suffix is omitted when the match has no client. Two spaces separate columns;
a task row is indented four spaces.

**Output, `--json`.** One JSON document, an array, indented two spaces:

```json
[{"code": "ACM-CR202", "project_id": "<id>", "name": "…", "client": "…",
  "matched_on": "code", "source": "catalog",
  "tasks": [{"id": "<id>", "name": "…", "billable": true}]}]
```

`matched_on` is `code`, `code/name` or `client`. `source` is `catalog` or `history`, and is
**always present** (today it appears only on the fallback). `client` is `""` when there is none.
Identifiers are strings in both formats.

- **A fallback to history prints on stderr:** `NOTE not in the catalog (assignment likely
  archived); recovered from own entries, last <N> days`, and still exits 0.
- **A fallback that itself fails** prints `WARN history fallback failed: <reason>` on stderr and
  carries on to the verdict below — but the verdict is then **exit 3, 4 or 5, not 6** (a revoked
  token on the fallback is a refusal, 4): a read that
  could not finish must not be reported as "no such project" (ADR-0007). Only a lookup that
  *completed both reads* and found nothing is a no-match.
- **No match:** stderr `ERR no project matching '<QUERY>' in the catalog or recent entries`,
  exit **6**. A genuine miss after the fallback means the project is unknown; refreshing the
  catalog will not help, and the exit code lets the caller say so.
- A catalog that is absent or unreadable is not an error by itself (the fallback runs), but is
  said on stderr. A workspace that cannot be resolved is exit 3 **only if** the fallback is
  also unavailable; a cache-only run with no catalog is exit 3.
- **Credentials are needed only by the fallback.** A catalog hit works with none configured.

### 3.4 `list` — entries over a date range

```
timesheet-provider list FROM [TO] [--by-day]
```

`FROM` and `TO` are `YYYY-MM-DD`; with one date it is both ends. Both are parsed by the
dispatcher: a non-date, or a `TO` before `FROM`, is a usage error (exit 2) — a reversed range
would otherwise read as a month with no gaps in it. Entries are the **caller's own**, never the
company's.

**Output, per entry** (default): one line per entry, sorted by date, then start time, then id.

```
<entry-id>  <date>  <HH:MM>-<HH:MM>  <D>h  <project-code>  <task-name>  <notes>
```

`<entry-id>` is left-aligned in 10 columns, `<D>` is the duration in decimal units of one hour
right-aligned in 5 with two decimals (`2.75h`), `<project-code>` is left-aligned in 11 (`?` when
unknown), `<task-name>` is cut to 25 and left-aligned in 25, and `<notes>` has line breaks
turned to spaces and is cut to 60 characters, ending `…` when cut. Times are 24-hour in the
user's zone; `--:--` stands for an entry with no clock interval (a duration-only entry).

**Output, `--by-day`:** one row **per date in the range, including the empty ones**. Absence is
precisely what an unbilled day looks like, and arithmetic over a hundred rows done by eye is
wrong quietly.

```
<date>  <Day>  <total>h  <n> entries  <project-codes>
```

`<total>` is right-aligned in 6 with two decimals, `<n>` in 2, the noun is `entry  ` (padded)
for one and `entries` otherwise, and the codes are comma-separated in first-seen order, `-` when
there are none. An entry the provider returned with no date inside the range is **not dropped
silently**: stderr says `(skipped <n> with no date inside the range: <ids>)`.

- **An empty range** prints `(no time entries from <FROM> to <TO>)` on stderr, **exits 0**, and
  prints nothing on stdout in the default mode. That is the success case for a day nobody billed,
  and it is told apart from a failed read by the exit code alone.
- **A failed read is non-zero, never a quiet empty result.** Any page that fails stops the
  run with the class's exit code and prints no partial list: a half-paged month would read as a
  month with gaps.

### 3.5 `refresh` — refresh the provider's catalog

```
timesheet-provider refresh [--wait CODE [--attempts N] [--delay SECONDS]]
timesheet-provider refresh --age
```

Re-reads the user's project and task assignments from the provider, **every page**, and rewrites
the local catalog `lookup` reads. **Stdout on success:** one line, `OK <n> projects`. Progress
(a line per page) is stderr.

- **A failed refresh leaves the existing catalog exactly as it was.** Every page is fetched into
  memory before the catalog is touched, and the new pages are staged before the old are
  removed — the property `refresh_catalogs.py` has today and is the contract's to keep, since a
  caller cannot see how the catalog is stored. Exit 3, 4 or 5 (a missing credential is 3), the reason on stderr, and
  `(existing catalog left untouched)` in it.
- **`--age` says how stale the catalog is, and touches nothing.** It reads no provider and needs
  no credential: stdout `AGE <days>` (whole days since the catalog was last written, rounded
  down), or `ABSENT` when there is none, exit 0; a workspace that cannot be resolved is exit 3.
  This is how a caller decides whether to refresh — the thresholds (7 days, the 30-day prompt)
  are the caller's policy, not the contract's — because the catalog's files are the adapter's
  and a caller reading their timestamps would be reading the storage (§ 6.2).
- `--age` with `--wait` is a usage error, exit 2.
- **A catalog that comes back with no projects at all is a failure** (exit 4), not a catalog
  written empty: it would make every later lookup fall through to the live fallback unannounced.
- **`--wait CODE`** is `refresh_catalogs.wait_for_project()` as a command: it polls the
  provider's catalog until `CODE` appears (up to `--attempts`, default 20, `--delay SECONDS`
  between them, default 15), because the catalog is eventually consistent and a just-created
  project can take minutes to surface. A single refresh, and a row count, are not reliable for
  that. On success it **writes the catalog it found** and prints `OK <code>`, exit 0; if it never
  appears, exit **6**, with `ERR <code> did not appear after <N> attempts`. It does not post
  anything — the deferred block is still billed through `post`, behind the gate.
- **`refresh` is the provider's catalog only.** The work-item catalog (`pac`, the active-incident
  list) is **not** a provider operation: it is the read side's, and #37 gives it its own boundary.
  Until #37 lands it stays `refresh_catalogs.py --dataverse-only`. The `--harvest-only` and
  `--dataverse-only` flags therefore **do not exist** on this command: the first is `refresh`
  itself, and the second is not the provider's to run.

## 4. Exit codes

| Code | Class | When | A caller does |
|---:|---|---|---|
| 0 | **Success, or preview** | The operation completed; or a write was *previewed* (`WOULD …`); or a `list` of an empty range. | A preview is **not** a write. Only `OK <id>` records an entry. |
| 1 | Internal error | A defect in the dispatcher or an adapter that nothing above names. `ERR internal …`. | Surface it; do not retry. |
| 2 | **Usage** | An argument the contract refuses: unknown subcommand or flag, missing or repeated flag, malformed date or time, reversed range, no field on `patch`, `TIMESHEET_PROVIDER` naming no adapter (the message lists the known adapters). | Fix the command. The provider was not asked anything. |
| 3 | **Missing configuration or credentials** | A setting the selected adapter needs is absent: a credential, the workspace, the zone where it cannot be read. | Route to setup. **Never ask for the value.** The message names the variable and the setup step. |
| 4 | **Provider refused** | The provider, or the adapter's pre-flight check on its behalf, rejected a well-formed request: an auth failure, a validation error, a wrong id, an entry that would be billed wrongly. | Stop and surface; do not retry silently. |
| 5 | **Provider unreachable** | No answer: a network error, a timeout, a service outage. Nothing was decided by the provider. | Safe to retry later; for a write, the entry may or may not exist — `list` before retrying. |
| 6 | **No match** | `lookup` completed both reads and found nothing; `refresh --wait` timed out. | An unknown project: ask the user; a refresh will not help. |

Classes 0 and 2–5 are the five the #33 decision names; `1` and `6` are additions this document
makes and the reviewer should confirm (§ 7). A read that fails is **never** exit 0 and never an
empty stdout with a notice: it is 3, 4 or 5, which is ADR-0007's "fails loudly and cheaply".

**Telling 4 from 5 is the adapter's job**, and the dispatcher's contract is only that it is
done: an HTTP response of any status, including the provider's own 5xx, is *a response* (4); a
failure to get one is 5. The numbers are the contract; the statuses behind them are not.

## 5. Credentials and configuration

Credentials are read **only by the selected adapter**, through the dispatcher's **one config
helper** (`provider_config.require(names)`, which wraps `skill_config.setting()` and so carries
its flag, `.env`, environment, default precedence). Neither the dispatcher nor any other adapter
reads them, and no test does (`conftest._hermetic` blanks the sources).

- **A missing credential** is exit 3 with the message in this shape on stderr, and **never a
  value**, neither the one that is missing nor one that is present:

  ```
  ERR missing configuration: <VARIABLE> [, <VARIABLE>…]
    Set it with:  <the setup step — for a plugin install, /plugin configure billables>
    <where it is read from on this install, and the new-session note when it applies>
  ```
- **Which commands need them** is the adapter's, with one contract rule: **a command that can
  be answered without the provider does not ask for credentials** (a catalog-hit `lookup`).
- **A key is validated when read, not when imported.** Importing an adapter resolves nothing
  and writes nothing to the environment (`tests/test_config_seam.py`'s rule), so `--help` and
  the usage errors work on a machine with nothing configured.
- The variable names and the setup steps are the adapter's and live in its own documentation
  (`references/first-run.md`'s configuration table); this document does not repeat them.

## 6. The seam, and what is internal

### 6.1 The seam — what a later plugin split renames

Everything below is the contract. **Changing any of it is a published-surface change**, and a
split moves it without redesign:

| Part | Where it is stated |
|---|---|
| The command name and its five subcommands | § 1 |
| Each subcommand's flags, positional arguments, required/optional status and repeat rules | § 3 |
| Date and time spellings; the user's-zone rule; opaque string identifiers | § 1 |
| The body's field names in a preview (`project_id`, `task_id`, `date`, `start`, `end`, `notes`) | § 3.1, § 3.2 |
| `WOULD POST` / `WOULD PATCH` lines, the footer, `OK <id>` | § 2, § 3 |
| The output formats of `lookup` (text and JSON), `list` (both modes) and `refresh` | § 3.3–3.5 |
| stdout-is-data, `ERR ` first line, no traceback | § 1 |
| The exit-code numbers and their classes | § 4 |
| `TIMESHEET_PROVIDER` as the selector, `harvest` as the default | § 1 |
| `TIMESHEET_TIMEZONE`, `TIMESHEET_WORKSPACE` as the settings every adapter is handed | § 1, § 3.3 |
| The shape of the missing-configuration message; "never print a value" | § 5 |
| That a failed refresh leaves the catalog, and that a failed read is never empty | § 3.4, § 3.5 |

A split changes the executable's *location* (a path to a bare name on `PATH`) and the adapter's
*package*. It changes no row above. The ADR's one open platform fact — whether one plugin's
scripts can see another's declared configuration — is about § 5 and must be settled before a
split, not during.

### 6.2 Internal to the adapter — free to change without touching a caller

| Part | Note |
|---|---|
| The provider's field names, endpoints, base URL, request headers, paging parameters and status codes | All of it. The adapter maps the contract's `date`/`start`/`end` onto whatever the provider stores. |
| How an entry is sent (fixed interval, never a timer) and the account modes it copes with | The promise is § 3.1's; the mechanism is the adapter's. |
| The pre-flight guards and their wording, including the daylight-saving refusal and its arithmetic | `refusal_for_a_straddled_change()` and the repeated-span rule move with the adapter; the *fact* that a check can refuse (exit 4, before the gate) is the seam's. |
| The catalog's on-disk file names, page files and format | `lookup` and `refresh` of the same adapter agree on them; no caller reads them. |
| The names of the credential variables, and the setup steps' wording | § 5 specifies the shape of the message, not its content. |
| The retry, timeout and pagination strategy; the `client`/`request` helper | Including `harvest_client.py`. |
| Which 4xx/5xx a status means, and so how it maps onto 4 or 5 | The numbers are the seam; the mapping is internal. |
| The history fallback's query and look-back strategy, behind `--days` | The flag is the seam. |
| Accepting more time spellings than the contract's | An adapter may be lenient *inside*; the dispatcher has already normalised. |

The dispatcher itself is **neither**: it holds the gate, the argument validation, the
adapter selection and the one config helper, and it imports an adapter only by the name
`TIMESHEET_PROVIDER` selects. The import direction ADR-0006 and `test_module_boundaries.py` hold
continues: no adapter imports the activity-source client, nothing imports a script, and an
adapter imports neither another adapter nor the dispatcher's gate.

**The adapter interface** the dispatcher calls (Python, in `scripts/provider/<name>/`):

```
NAME: str
check_post(body: dict) -> None                 # read-only; raises Refused / Unreachable / Misconfigured
check_patch(entry_id: str, fields: dict) -> None   # read-only; may read the entry
post(body: dict) -> str                        # entry id; called only when confirmed
patch(entry_id: str, fields: dict) -> str      # entry id; called only when confirmed
lookup(query, task, catalog_dir, cache_only, days) -> list[match]
list_entries(date_from, date_to) -> list[entry]
refresh(wait_for=None, attempts=20, delay=15) -> int   # projects written
catalog_age() -> float | None                  # days since the catalog was written; None if absent
```

`catalog_age()` is what `refresh --age` asks, so no caller reads the catalog's files. The exceptions (`provider/errors.py`: `Usage`, `Misconfigured`, `Refused`, `Unreachable`, `NoMatch`) map onto exit 2, 3, 4, 5 and 6; an adapter raises the last four. The interface is internal to this plugin until a
split, which would turn it into the executable's own argument surface — and this document is
that surface already.

## 7. Open points for the reviewer

These are the decisions this design made that the #33 comment did not, listed so none is
discovered by accident:

1. **Two exit codes beyond the five classes:** `1` for an internal defect (so a bug is never read
   as a class) and `6` for no match (so an unknown project is told from a failed read, which the
   `daily` skill's "a miss after the fallback means the project is genuinely unknown" needs).
2. **The duration-only patch flag is dropped** (§ 3.2). No caller uses it. If the reviewer would
   rather carry it, it needs a contract name that is not a provider's field, and a decision on
   what an adapter that has no duration mode does with it.
3. **`lookup` without a catalog** is exit 3 only when cache-only; otherwise it falls through
   to the live read, as today.
4. **The work-item catalog is not `refresh`'s** (§ 3.5), so the `daily` skill's "run
   `refresh_catalogs.py`" becomes two commands until #37, one of them this contract's.
5. **A patch preview can need the provider** (§ 3.2). That is today's behaviour, kept because the
   alternative — previewing a change the check would refuse — is the failure the gate exists to
   prevent.
6. **`refresh --age`** (§ 3.5), so a caller can tell a stale catalog without reading the adapter's
   storage. Added in review: the first draft left freshness to the file's modification time.

## 8. Mapping from every current invocation (#35's work list)

`<daily>` is the `daily` skill's directory; `TP` stands for
`python "<daily>/scripts/provider/bin/timesheet-provider"`. Rows are exhaustive: every place in
`skills/` and `docs/` that runs, imports or names a provider script, **or reads a provider file
or field directly**. The same-named files under `skills/daily/tests/`
exercise these scripts and move with them in #35.

### 8.1 Commands

| Today | Contract | What changes |
|---|---|---|
| `python scripts/harvest_post.py <project_id> <task_id> <YYYY-MM-DD> <HH:MM> <HH:MM> '<notes>' [--confirm]` | `TP post --project-id <project_id> --task-id <task_id> --date <YYYY-MM-DD> --start <HH:MM> --end <HH:MM> --notes '<notes>' [--confirm]` | Positionals become flags. Output (`OK <id>`, `WOULD POST <body>`) keeps its shape; the **body's keys change** (`date`, `start`, `end` replace the provider's names). Exit 1 on any failure becomes 2/3/4/5. |
| `python scripts/harvest_patch.py <entry_id> [--start …] [--end …] [--notes …] [--project-id N] [--task-id N] [--date …] [--confirm]` | `TP patch <entry_id> [--start …] [--end …] [--notes …] [--project-id ID] [--task-id ID] [--date …] [--confirm]` | Same flags, now opaque strings not integers. **The duration-only flag is removed** (§ 3.2). `WOULD PATCH <id> <body>` keeps its shape, body keys renamed. |
| `python scripts/harvest_lookup.py <query>` | `TP lookup <query>` | Text output is unchanged. |
| `python scripts/harvest_lookup.py <query> --task <name>` | `TP lookup <query> --task <name>` | Unchanged. |
| `python scripts/harvest_lookup.py <query> --json` | `TP lookup <query> --json` | `source` is now always present; identifiers are strings. |
| `python scripts/harvest_lookup.py <query> --no-live` | `TP lookup <query> --cache-only` | Renamed: it says what it does, not that it avoids a provider's "live" API. |
| `python scripts/harvest_lookup.py <query> --days N` | `TP lookup <query> --days N` | Unchanged. |
| `python scripts/harvest_lookup.py <query> --mcp-dir DIR` | `TP lookup <query> --catalog-dir DIR` | Renamed: `.mcp/` is a path, not the contract. |
| `python scripts/harvest_list.py <from> [<to>]` | `TP list <from> [<to>]` | Per-entry columns unchanged; exit 1 → 2/3/4/5. |
| `python scripts/harvest_list.py <from> <to> --by-day` | `TP list <from> <to> --by-day` | Unchanged; this is the month sweep `reconcile` runs. |
| `python scripts/refresh_catalogs.py --harvest-only` | `TP refresh` | Output is now `OK <n> projects`; per-page progress is stderr. |
| `python scripts/refresh_catalogs.py` (both) | `TP refresh`, then `python scripts/refresh_catalogs.py --dataverse-only` | Two commands until #37 (§ 3.5). |
| `python scripts/refresh_catalogs.py --dataverse-only` | unchanged | Not the provider's; #37 owns it. |
| `refresh_catalogs.wait_for_project('<code>')` (`new-client-work.md`, `catalog-refresh.md`) | `TP refresh --wait '<code>'` | A function call becomes a command; exit 6 means it never appeared. |
| `python scripts/harvest_list.py <today> <today>` as the credentials check (`SKILL.md` Prerequisite 5, `first-run.md` step 4) | `TP list <today> <today>` | Success is **exit 0**, with the empty-range notice a success; exit 3 is "credentials not found", **4 is "the credential was refused"** (a revoked token), 5 is the network. The caller can now tell the three apart from the exit code, where it read the text before. |

### 8.2 Every caller

| File | Line's subject | Becomes |
|---|---|---|
| `skills/daily/SKILL.md` Prerequisite 4 | "else run `scripts/refresh_catalogs.py`" | `TP refresh` (and the work-item refresh as above) |
| `skills/daily/SKILL.md` Prerequisite 4 | freshness judged from the assignment catalog file's modification time | `TP refresh --age`: refresh at `AGE` ≥ 7 or `ABSENT`; surface `AGE` > 30 first, as today (§ 3.5) |
| `skills/daily/SKILL.md` "Data sources" table | the assignment catalog's file glob and the provider's field names as a data source | one row: "the provider's project/task catalog, read through `TP lookup`"; no file or field named |
| `skills/daily/SKILL.md` checklist, work-kind line | the task name came from "this project's own" task list, named by its provider field | "from the tasks `TP lookup` lists for this project" |
| `skills/daily/references/classification-rules.md` project lookup (step 2) | read the project code's id and tasks out of the catalog file | `TP lookup <code> --json`: `project_id` and `tasks[]` |
| `skills/daily/references/classification-rules.md` task authority and billable rule | the provider's per-project task list, and its per-task billable flag, named as the authority | the `tasks[]` `TP lookup` returns and its `billable` (text: `(billable)` / `(NON-billable)`) |
| `skills/daily/references/catalog-refresh.md` "Output" | the page files' names, and "downstream readers expect the provider's own shape" | removed: storage is the adapter's (§ 6.2); the paragraph says `TP refresh` writes the catalog `TP lookup` reads |
| `skills/daily/references/new-client-work.md` | `scripts/refresh_catalogs.py` for the bulk work-item catalog | stays `refresh_catalogs.py --dataverse-only` until #37 |
| `skills/daily/SKILL.md` Tunable defaults and Step 4 (task selection) | the project's own task list, and the billable rule, named by the provider's fields | "the tasks `TP lookup` lists for this project", and its `billable` |
| `skills/daily/SKILL.md` Step 4 (work-item strings) | "matches only on" the provider's client field | lookup's `matched_on: client` |
| `skills/daily/SKILL.md` "Files in this skill", `refresh_catalogs.py` entry | the catalog's file glob as what it refreshes | `TP refresh` writes the catalog `TP lookup` reads; no file named |
| `skills/daily/references/classification-rules.md` step 1 (prefix → client) | groups the catalog file's projects by code prefix to find a client | `TP lookup <prefix> --json`, grouped by `client` |
| `skills/daily/references/classification-rules.md` step 4b | the task list named by its provider field ("`harvest_lookup.py` returns them") | "the `tasks[]` `TP lookup` returns" |
| `skills/daily/references/catalog-refresh.md` "When to refresh" | the catalog file's modification time and the project's code field | `TP refresh --age` (`AGE` ≥ 7 or `ABSENT`); lookup's `code` |
| `skills/daily/references/catalog-refresh.md` "The assignment catalog" (endpoint, scope, headers, paging, output) | the provider's endpoint, token scope, headers, paging and page files | **moves behind the adapter** (§ 6.2), into the adapter's own notes; the section keeps only what `TP lookup` returns and that `TP refresh` needs no admin scope |
| `skills/daily/references/first-run.md` Work kinds | read the task names out of the catalog file | offer the task names `TP lookup` lists across the user's projects |
| `skills/daily/references/first-run.md` token scope | the endpoint and cached file the skill reads through | "a member-scope token is enough; `TP refresh` and `TP lookup` need no admin scope" — the endpoint is the adapter's |
| `docs/adr/0007-…md` and `CONTEXT.md` status paragraph | the gate "implemented once, in `skills/daily/scripts/harvest_write.py`" | #35 amends both: the gate is in the dispatcher (§ 2) |
| `skills/daily/SKILL.md` Prerequisite 5 | the `harvest_list.py` credentials check | `TP list <today> <today>`, per § 8.1 |
| `skills/daily/SKILL.md` Step 1 (gap listing) and "check whether that date is already billed" | `harvest_list.py <date> <date>` | `TP list <date> <date>` |
| `skills/daily/SKILL.md` Step 4 and the checklist | `harvest_lookup.py <code-name-or-client>` | `TP lookup <code-name-or-client>` |
| `skills/daily/SKILL.md` Step 9 | the `harvest_post.py` template and its `--confirm` bullets | the `TP post` template; "`OK <id>` / `ERR <status> <body>`" becomes "`OK <id>` / `ERR <message>`, exit 2–5" |
| `skills/daily/SKILL.md` Step 9, patch paragraph | the `harvest_patch.py` template | the `TP patch` template, without the duration flag |
| `skills/daily/SKILL.md` Step 9, "Harvest bills the difference…" daylight-saving bullet | names `harvest_patch.py`, `harvest_post.py` and a duration flag | name the command; **drop the clause about the duration flag**; the refusal text itself is the adapter's and unchanged |
| `skills/daily/SKILL.md` "Hard rules" | "`harvest_post.py` and `harvest_patch.py` write only when passed `--confirm`" | "`post` and `patch` write only when passed `--confirm`" |
| `skills/daily/SKILL.md` "Files in this skill" | five script entries, every flag named (held by `skills/daily/tests/test_references.py` and, for `reconcile`, `tests/test_reconcile_skill.py`) | one `timesheet-provider` entry naming the five subcommands and every flag in § 3; the two flag-equality tests re-point at the dispatcher's parser |
| `skills/reconcile/SKILL.md` Step 1 | `python "<daily>/scripts/harvest_list.py" <first> <last> --by-day` | `python "<daily>/scripts/provider/bin/timesheet-provider" list <first> <last> --by-day` |
| `skills/reconcile/SKILL.md` header and "Finding the files" | the sibling-directory path resolution | still reaches the dispatcher by path — **until the split**, which is the point where this row, and `test_every_script_it_names_is_one_the_sibling_skill_actually_ships`, collapse into "the command is on `PATH`" |
| `skills/reconcile/SKILL.md`, which must not write | `WRITE_TOKENS` in `tests/test_reconcile_skill.py` (`harvest_post`, `harvest_patch`, `--confirm`, …) | re-point the denylist at `post` / `patch` used as subcommands: `reconcile` may name `list` and nothing else |
| `skills/daily/references/new-client-work.md` | `refresh_catalogs.wait_for_project(<code>)` | `TP refresh --wait <code>` |
| `skills/daily/references/catalog-refresh.md` | the credentials and `wait_for_project` paragraphs; "`refresh_catalogs.py` does all the above in one go" | `TP refresh` / `TP refresh --wait`; the credentials paragraph points at § 5 |
| `skills/daily/references/output-format.md` | "Strip it before `harvest_post.py`" and the `harvest_patch.py` refusal paragraph | name `post` / `patch`; the second-pass marker is now refused by the contract itself, for every adapter |
| `skills/daily/references/classification-rules.md` | "`harvest_lookup.py` returns them" | "`lookup` returns them" |
| `skills/daily/references/reporting-issues.md` | "`harvest_lookup.py` can't find the project" | "`lookup` finds no project (exit 6)" |
| `skills/daily/references/first-run.md` | the `harvest_list.py` verification, the zone row, the workspace note | `TP list`; exit-code vocabulary per § 4 |
| `docs/CONTRIBUTING.md` | the layout tree and three rows naming the scripts | the layout tree; the import-direction row names the adapter directory |

### 8.3 Properties each script holds that the contract preserves

So that #35 is a move and not a rewrite: the guards in front of the gate (ordered times, the
daylight-saving refusal, the date shape) are kept and **run before the preview**; the
read-before-preview of a patch is kept (§ 3.2); a catalog-hit `lookup` needs no credentials; a
refresh is atomic; `list --by-day` prints every date; and every failure is a one-line message
rather than a traceback. What *changes* is exactly: the argument spelling, the preview body's
keys, the exit numbers, `lookup`'s `--no-live` / `--mcp-dir` names, the always-present `source`,
the `refresh` output line, and the dropped duration-only flag. Each is in § 8.1.

### 8.4 What the move must add, in order

1. `scripts/provider/bin/timesheet-provider` with the gate, the argument validation, the adapter
   selection and `provider_config`, written against a fake adapter first.
2. `scripts/provider/harvest/` with the five scripts' logic behind § 6.2's interface; the
   pre-flight guards stay with it.
3. The § 8.2 edits, in the same change as the move: a caller still naming a retired script path
   is the failure `test_every_script_it_names_is_one_the_sibling_skill_actually_ships` exists to
   catch.
4. The docstrings that name the scripts or `--mcp-dir` — `skill_config.py` and `timezone.py` — are
   not invocations, but the move stales them; re-point them in the same change.
5. A test per row of § 3 and § 4 against the fake adapter, and the existing Harvest-shaped
   tests re-pointed at the adapter. None shells out to a script and none reads a real credential.

"""The activity source's category rules: gate, back up, write, verify.

The plugin owns those rules (#69). Each client gets **one** rule, made from a few literal
**terms** the run curates with the user — the client code, the names of the client's own
products or apps, the client's full name — and this script judges them and writes the ones
that survive. The user sees the terms, never a regex or a JSON body.

**Choosing the terms is the model's, enforcement is this script's.** The context file
legitimately holds prose, hints and free text, so no parser should be asked to read it —
which is why this takes *candidates* rather than the file. What it does with them is
deterministic:

  1. **Gate.** A client with no terms or with more than `MAX_TERMS`, and a term matching an
     implausible share of the sampled window titles, are refused, and a refusal anywhere
     writes nothing. A term matching none of them is written and reported `UNVERIFIED`, as
     dormant or suspect — see `unverified_as_dormant_or_suspect()`. Two clients' rules
     matching the same titles is reported as `OVERLAP` and written: the candidates' order
     decides those titles, and refusing would let one shared title veto every rebuild.
  2. **Back up.** The current rule set is copied into the workspace before the first write.
     That is the recovery path, and it is what makes the write safe to perform without
     showing the user a diff.
  3. **Write.** One class per client, named for the client, merged over what is already
     there: a rule this plugin did not author is kept exactly as it was.
  4. **Verify.** The rules are read back, and the activity source itself is asked which
     events each one labels. A rule the gate matched and the activity source does not is a
     failed run — the gate's own matcher once agreed with itself about rules the activity
     source could never match (decision log, "The category rules labelled nothing").

A term is literal, matched case-insensitively anywhere in the app name or the title — each
field on its own, because that is how the activity source matches (`matching()`).

Three modes:
  * `--candidates <file|->`  gate, back up, write, verify
  * `--inspect`              what the activity source holds now, each rule marked managed
                             or not and carrying the share of the sample it matches — the
                             read behind adopting rules the plugin did not author — and,
                             as `SEEN` lines, the profile tags the titles really carry, and
                             as `HOST` lines, the addresses the browser titles carry
  * `--status`               whether the rules are still current for the workspace context
                             file. Reads two local files and nothing over the wire

No third-party deps — stdlib urllib, via the shared aw_client.py.

Usage:
  python scripts/category_rules.py --candidates candidates.json
  python scripts/category_rules.py --inspect
  python scripts/category_rules.py --status
"""
import argparse
import collections
import datetime as dt
import hashlib
import io
import json
import re
import sys
import urllib.error
from pathlib import Path

import skill_config
from aw_client import SourceError, get, post_setting, query, unreachable, window_day

# How much of the day the sample covers. A week rather than a day so a client worked on
# only on Tuesdays still has titles to gate against; the whole point of the gate is that a
# rule is judged against real evidence, and a sample that is too thin refuses a good rule.
DEFAULT_DAYS = 7

# The share of sampled titles above which a term is refused as over-broad. The measured bad
# case is 0.46 (256 of 552 in one day), so the ceiling has to sit below that; 0.35 is the
# nearest round number that does. It is a judgement call and therefore a flag as well —
# a one-client consultant legitimately runs hotter than a five-client one, and the
# `## Preferences` line in the workspace template is where a user's own value belongs.
DEFAULT_MAX_SHARE = 0.35

# A client's rule is a curated handful — its code, its products, its name, and for a user who
# works every client from one browser profile, the addresses only that client's work opens
# (its SharePoint tenant, its DevOps org). More than this is a list generated rather than
# chosen, which is what this shape replaced.
MAX_TERMS = 8

# The characters a term is escaped on. Not `re.escape`, which also escapes a space: the
# activity source's own UI evaluates these rules too, and an escape one engine does not know
# is a rule that fails there alone.
REGEX_SPECIAL = re.compile(r"([\\.^$|?*+()\[\]{}])")

# A profile tag where the extension writes it — the end of the page part, before Edge's own
# ` and N more pages` and the profile slot — so a page's own `[Draft]` is not read as one. The
# greedy prefix takes the last tag, which is the extension's; the slot is bounded, so the page
# part cannot pass for a profile. The code shape is `CONTEXT.md`'s client code. Group 1 is the
# tag, group 2 Edge's profile slot, absent in Chrome, which prints no profile.
TAGGED_TITLE = re.compile(r"^.* - (\[[A-Za-z0-9-]{2,12}\])(?: and \d+ more pages?)?"
                          r"(?: - ([^-]+(?: - [^-]+)?) - Microsoft\W*Edge| - Google Chrome)?$",
                          re.IGNORECASE)

# The address the extension appends: `{title}-{hostname}{path}…`, one whitespace-free token
# that also carries the last word of the page title, since the extension joins the two with
# a bare `-`. Hosts contain hyphens too, so the split is decided in `host_counts()`.
HOST = re.compile(r"(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}", re.IGNORECASE)
BROWSER_APP = re.compile(r"msedge|edge|chrome|firefox|brave|opera|vivaldi|safari", re.IGNORECASE)

# Hosts shared by every tenant, whose tenant is the first path segment. Bare, they would
# match every client's work at once, so they are only ever offered with that segment.
SHARED_HOSTS = frozenset({"dev.azure.com", "github.com", "gitlab.com", "bitbucket.org"})

# How many `HOST` lines `--inspect` prints: enough to find each client's addresses, few enough
# that the run is not handed the week's browsing.
HOSTS_SHOWN = 25

# Where the backup and the stamp live under the workspace. `.mcp/` already holds the cached
# catalogs — machine state the user does not hand-edit — which is what both of these are.
STATE_DIR = ".mcp"
STAMP = "category-rules.json"
CONTEXT_FILE = Path("Timesheets") / ".context.md"

# (app, title) — the two fields the activity source matches a rule against.
Window = tuple[str, str]


class Refusal(Exception):
    """A run that cannot proceed: one line printed after `ERR`, exit 1. Everything the gate
    refuses is reported together rather than raised, so a run fixing its candidates sees all
    of them at once; this is for the failures that stop the run before that."""


# --------------------------------------------------------------------------------------
# The sample
# --------------------------------------------------------------------------------------

def sample_windows(days: int) -> tuple[str, str, str, list[Window]]:
    """The distinct `(app, title)` pairs the window watcher saw over the last `days`, the
    bucket they came from, and the range read — the verify asks the activity source about
    the same range.

    Distinct, because share is a question about the day's *variety* and a title left open
    all afternoon is one title however long it stayed there. Read over a rolling window
    ending now rather than over a named local date: this runs during setup, before the
    timezone is necessarily configured, and a rule is no better or worse for having been
    gated against a day that ends at midnight.
    """
    end = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    start = end - dt.timedelta(days=days)
    start_utc = start.isoformat().replace("+00:00", "Z")
    end_utc = end.isoformat().replace("+00:00", "Z")
    _, bucket, events = window_day(start_utc, end_utc,
                                   "there is nothing to test a category rule against")
    seen = {}
    for event in events:
        data = event.get("data") or {}
        seen.setdefault((str(data.get("app", "?")), str(data.get("title", "") or "")), None)
    return bucket, start_utc, end_utc, list(seen)


def shown(window: Window) -> str:
    return f"{window[0]} {window[1]}"


# --------------------------------------------------------------------------------------
# The gate
# --------------------------------------------------------------------------------------

def rule_for(terms: list[str]) -> str:
    """The regex written for a client: its terms, escaped, as one alternation."""
    return "(?:" + "|".join(REGEX_SPECIAL.sub(r"\\\1", term) for term in terms) + ")"


def matching(regex: str, sample: list[Window]) -> list[Window]:
    """The sampled windows a regex matches, case-insensitively, in the app or the title.

    Each field on its own, because that is how the activity source's `categorize` matches:
    a regex that needs the app and the title together matches nothing there. One
    implementation, because the gate, the verify and `--inspect` are asking the same
    question. The case flag matters as much: `merged()` writes every rule with
    `ignore_case: true`, so a reader that compiled without it would report a share the
    activity source will not reproduce.
    """
    compiled = re.compile(regex, re.IGNORECASE)
    return [w for w in sample if compiled.search(w[0]) or compiled.search(w[1])]


def judge(candidate: dict, sample: list[Window], max_share: float) -> dict:
    """One client, decided: `verdict` is `write` or `refuse`, with a `reason` for a refusal,
    each term's matches, and the regex that would be written.

    Everything here is a property of the candidate and the sample, so a caller can report
    every verdict before acting on any of them. Nothing is written from this function.
    """
    client = (candidate.get("client") or "").strip()
    raw = candidate.get("terms")
    terms = [t.strip() for t in raw if isinstance(t, str)] if isinstance(raw, list) else []
    out = {"client": client, "terms": terms, "regex": "", "matched": [], "per_term": {}}

    def verdict(kind: str, reason: str) -> dict:
        return {**out, "verdict": kind, "reason": reason}

    if not client:
        return verdict("refuse", "a candidate needs a client")
    if not isinstance(raw, list) or not terms or len(terms) != len(raw) or not all(terms):
        return verdict("refuse", 'a candidate needs "terms": a list of words, none of them '
                                 "empty — the client code, the client's products, its name")
    if len(terms) > MAX_TERMS:
        return verdict("refuse", f"{len(terms)} terms, over the {MAX_TERMS} a client's rule "
                                 f"takes. Keep the ones only this client's work produces: "
                                 f"its code, its products, its name")
    broad = []
    for term in terms:
        hits = matching(rule_for([term]), sample)
        out["per_term"][term] = len(hits)
        share = len(hits) / len(sample) if sample else 0.0
        if share > max_share:
            broad.append(f"'{term}' matches {len(hits)} of {len(sample)} sampled titles "
                         f"({share:.0%})")
    out["regex"] = rule_for(terms)
    out["matched"] = matching(out["regex"], sample)
    if broad:
        return verdict("refuse", f"{'; '.join(broad)}, over the {max_share:.0%} ceiling. The "
                                 f"first matching rule wins, so a term this broad takes the "
                                 f"label off a correct one; use a narrower term")
    return verdict("write", "")


def unverified_as_dormant_or_suspect(judged: list[dict]) -> list[str]:
    """One `UNVERIFIED` line per term that matched nothing, named for what the rest of its
    client's terms say.

    Every declared client is passed on a rebuild, and one not worked on inside the window
    matches nothing however right its terms are: **dormant**. A client whose other terms did
    match, and this one did not, is the mistyped code or the product never opened that a
    zero once refused: **suspect**. Neither is refused. A term that matches nothing cannot
    take the label off another, so writing it costs the rule set nothing, while a refusal
    wrote nothing at all — one quiet client vetoed every rebuild until its work came back.
    """
    lines = []
    for j in judged:
        if j["verdict"] != "write":
            continue
        silent = [term for term, n in j["per_term"].items() if not n]
        for term in silent:
            if j["matched"]:
                lines.append(f"UNVERIFIED {j['client']} '{term}' — suspect: matches none of "
                             f"the sampled titles, though {j['client']}'s other terms do. "
                             f"Probably mistyped, or never seen in a title; written anyway")
            else:
                lines.append(f"UNVERIFIED {j['client']} '{term}' — dormant: nothing declared "
                             f"for {j['client']} matches the sampled titles — most likely "
                             f"not worked on in the window. Written unchecked")
    return lines


def overlaps(judged: list[dict]) -> list[str]:
    """One `OVERLAP` line per pair of clients whose rules match the same titles.

    Reported, not refused. The earlier client in the candidates takes those titles, which
    is right for a title that is mostly one client's and wrong for a term two clients share
    — the line names both so a run can drop the shared term. Refusing instead would let one
    title naming two clients veto every rebuild.
    """
    lines = []
    writing = [j for j in judged if j["verdict"] == "write"]
    for index, first in enumerate(writing):
        for second in writing[index + 1:]:
            if first["client"] == second["client"]:
                continue
            shared = sorted(set(first["matched"]) & set(second["matched"]))
            if shared:
                lines.append(f"OVERLAP {first['client']} and {second['client']} — both match "
                             f"{len(shared)} title{'' if len(shared) == 1 else 's'}, which "
                             f"go to {first['client']}. e.g. {shown(shared[0])[:100]}")
    return lines


def seen_profile_tags(sample: list[Window]) -> dict[str, collections.Counter]:
    """Each profile tag in the sampled titles, counted per Edge profile slot it was seen in
    — `None` for a title that names no profile."""
    seen: dict[str, collections.Counter] = {}
    for _, title in sample:
        found = TAGGED_TITLE.search(title)
        if found:
            seen.setdefault(found.group(1), collections.Counter())[found.group(2)] += 1
    return seen


def print_seen(sample: list[Window]) -> None:
    """One `SEEN` line per profile tag, most-seen first.

    What the titles carry, so a client code chosen from memory can be held against what is
    really there. No verdict on a tag seen in several profiles: which one is general is the
    user's to say. The slot is printed whole, account and all.
    """
    seen = seen_profile_tags(sample)
    if not seen:
        print("SEEN no profile tag in the sampled titles")
        return
    for tag, slots in sorted(seen.items(), key=lambda item: (-sum(item[1].values()), item[0])):
        total = sum(slots.values())
        titles = f"{total} title{'' if total == 1 else 's'}"
        if len(slots) == 1:
            (slot,) = slots
            where = f'in Edge profile "{slot}"' if slot else "no profile in the title"
        else:
            where = "in several profiles: " + ", ".join(
                f"{_named(slot)} ({n})" for slot, n in
                sorted(slots.items(), key=lambda item: (-item[1], item[0] or "")))
        print(f"SEEN {tag} — {titles}, {where}")


def _named(slot: str | None) -> str:
    return f'"{slot}"' if slot else "no profile"


def address_readings(title: str) -> list[str]:
    """Every way the extension's address in `title` could read, as `host` or `host/tenant`.

    The address is the last whitespace-free token holding `-<host>`. The extension joins the
    page title's last word to it with a bare `-`, and a host has hyphens of its own, so
    `Home-harbour-trust.example.com` could be either host — both are returned, and
    `host_counts()` settles it on what the rest of the sample says.
    """
    for token in reversed(title.split()):
        readings = []
        for index, char in enumerate(token):
            if char != "-":
                continue
            rest = token[index + 1:]
            found = HOST.match(rest)
            if not found or (rest[found.end():found.end() + 1] not in ("", "/", "?", "#", ":")):
                continue
            host = found.group(0).lower()
            if host in SHARED_HOSTS:
                segment = rest[found.end():].lstrip("/").split("/", 1)[0]
                segment = re.split(r"[?#]", segment, maxsplit=1)[0]
                if not segment:
                    continue
                host = f"{host}/{segment}"
            readings.append(host)
        if readings:
            return readings
    return []


def host_counts(sample: list[Window]) -> collections.Counter:
    """Distinct browser titles per address, each title counted once under one reading.

    A title with several readings goes to the one most other titles agree on, then the
    longest: `harbourtrust.sharepoint.com` seen on its own a hundred times outweighs the
    `Home-harbourtrust…` reading of one title, and a hyphenated host seen whole wins over the
    fragment of itself that follows its own hyphen.
    """
    per_title = [address_readings(title) for app, title in sample if BROWSER_APP.search(app)]
    support = collections.Counter(reading for readings in per_title for reading in set(readings))
    counts: collections.Counter = collections.Counter()
    for readings in per_title:
        if readings:
            counts[max(readings, key=lambda r: (support[r], len(r)))] += 1
    return counts


def print_hosts(sample: list[Window]) -> None:
    """One `HOST` line per address in the browser titles, most-seen first.

    What a user who works every client from one browser profile has instead of a profile
    tag: the addresses only one client's work opens are that client's terms. A count of
    distinct titles, not of time, and no example title — the address is the whole finding.
    """
    counts = host_counts(sample)
    if not counts:
        print("HOST no address in the sampled browser titles")
        return
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    for host, n in ranked[:HOSTS_SHOWN]:
        print(f"HOST {host} — {n} distinct title{'' if n == 1 else 's'}")
    if len(ranked) > HOSTS_SHOWN:
        print(f"HOST … and {len(ranked) - HOSTS_SHOWN} more addresses seen fewer times")


# --------------------------------------------------------------------------------------
# The rules the activity source holds
# --------------------------------------------------------------------------------------

def read_classes() -> list[dict]:
    """The `classes` list as the activity source holds it now.

    A refusal rather than an exception when the settings endpoint is not there: that is the
    older build the `setup` skill has a manual fallback for, and the fallback is only
    reached if this says so in words rather than in a traceback.
    """
    try:
        settings = get("/settings")
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise Refusal(f"the activity source answered {exc.code} for its settings "
                          f"({exc.reason}); nothing has been written.") from None
        raise Refusal(
            f"this activity source has no settings endpoint ({exc}), so the rules cannot be "
            f"written to it. They have to be entered by hand — the `setup` skill's category "
            f"step has that fallback, and it verifies the result.") from None
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise Refusal(
            f"the activity source would not answer for its settings ({exc}). That is the "
            f"source being unreachable rather than a build that has no such endpoint, so "
            f"re-entering the rules by hand would not help; nothing has been written."
        ) from None
    return [c for c in settings.get("classes", []) if isinstance(c, dict)]


def class_name(entry: dict) -> str:
    """A class's flat label — what `activity_timeline.categorize()` will report for a span
    it matches. The name is a path, joined with `>` there, so a rule this plugin writes has
    one element and a grouping parent someone else made keeps whatever it has."""
    return ">".join(entry.get("name") or [])


def class_regex(entry: dict) -> str | None:
    """The regex a class matches on, or None for a grouping category — which carries
    `{"type": "none"}` and no `regex` at all, and is the entry that turns a healthy
    configuration into an error when something reaches for a field that is not there."""
    rule = entry.get("rule") or {}
    if rule.get("type") != "regex":
        return None
    return rule.get("regex") or None


def merged(existing: list[dict], writing: list[dict], previously: set[str],
           adopting: set[str]) -> list[dict]:
    """The `classes` list to send: the rules being written, in the candidates' order, then
    everything the plugin did not author, untouched and in the order it was already in.

    Ours first because `categorize()` takes the *first* matching class as a span's label,
    and a client's curated terms are better evidence than whatever a leftover rule matches.

    **The managed set is regenerated whole.** A class is dropped when it is named by a client
    being written, by `previously` (what the last write recorded), or by `adopting` (a rule
    the user agreed to have taken over, whose name need not be the client's — an adopted
    `Work > Acme` is dropped and rewritten flat). So a client removed from `.context.md`
    loses its rule instead of being orphaned into the user's own set, and an adopted rule
    leaves one copy rather than two. Everything else is kept exactly as it was, `id` and all.
    """
    replaced = {j["client"] for j in writing} | previously | adopting
    kept = [entry for entry in existing if class_name(entry) not in replaced]
    ids = [entry["id"] for entry in existing if isinstance(entry.get("id"), int)]
    next_id = max(ids) + 1 if ids else 0
    ours = [{"id": next_id + offset,
             "name": [judged["client"]],
             "rule": {"type": "regex", "regex": judged["regex"], "ignore_case": True}}
            for offset, judged in enumerate(writing)]
    return ours + kept


# --------------------------------------------------------------------------------------
# The workspace: the backup, and the stamp the staleness check reads
# --------------------------------------------------------------------------------------

def state_dir(flag: str | None, create: bool = True) -> Path:
    """Where the backup and the stamp go: `<workspace>/.mcp/`.

    The workspace is the configured one, else whatever `find_workspace()` resolves, else the
    directory this was run from — which is what the declared configuration promises when
    `TIMESHEET_WORKSPACE` is left blank. Every run that writes prints the backup's full
    path, so a run that resolved somewhere unexpected says so rather than leaving the user
    to find out at recovery time.

    `create=False` for the modes that only read: a read has no business leaving a directory
    behind in wherever a run happened to start.
    """
    root = Path(flag).expanduser() if skill_config.has_value(flag) else None
    root = root or skill_config.find_workspace() or Path.cwd()
    directory = root / STATE_DIR
    if create:
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise Refusal(
                f"cannot keep the backup and the stamp in {directory} ({exc}). That is where "
                f"the rule set as it stands would be copied before anything is written, so "
                f"nothing has been. Name a writable workspace with --workspace, or set "
                f"TIMESHEET_WORKSPACE.") from None
    return directory


def back_up(classes: list[dict], directory: Path) -> Path:
    """Copy the current rule set into the workspace, before the first write of a run.

    Timestamped rather than overwritten: the state worth recovering is usually the one from
    *before* the plugin ever wrote, and a single file would have lost it on the second run.
    """
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = directory / f"aw-categories-{stamp}.json"
    path.write_text(json.dumps({"classes": classes}, indent=2), encoding="utf-8")
    return path


def context_fingerprint(root: Path) -> tuple[str, Path]:
    """The workspace context file's digest, or "" when there is no such file.

    The whole file, not the section that declares the terms: parsing that section is the
    thing this feature deliberately does not do, and a digest of the bytes costs one read
    and cannot be fooled. The price is a rebuild after an edit that changed a preference
    rather than a term, which writes the same rules back and is cheap.
    """
    path = root / CONTEXT_FILE
    if not path.is_file():
        return "", path
    return hashlib.sha256(path.read_bytes()).hexdigest(), path


def write_stamp(directory: Path, writing: list[dict]) -> None:
    """Record what was written and what it was built from, so the next run can tell whether
    the rules are still current without reading the activity source at all."""
    digest, _ = context_fingerprint(directory.parent)
    (directory / STAMP).write_text(json.dumps({
        "written": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "context_sha256": digest,
        "rules": [{"client": j["client"], "terms": j["terms"], "regex": j["regex"]}
                  for j in writing],
    }, indent=2), encoding="utf-8")


def read_stamp(directory: Path) -> dict | None:
    path = directory / STAMP
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None


# --------------------------------------------------------------------------------------
# The modes
# --------------------------------------------------------------------------------------

def load_candidates(source: str) -> list[dict]:
    """The candidates, from a file or from stdin (`-`).

    A list of `{"client", "terms"}` objects, each optionally carrying `adopts`. A single
    object is accepted as a list of one, because that is what a run testing a single client
    writes.
    """
    raw = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
    try:
        loaded = json.loads(raw)
    except ValueError as exc:
        raise Refusal(f"the candidates are not JSON: {exc}") from None
    if isinstance(loaded, dict):
        loaded = loaded.get("candidates", [loaded])
    if not isinstance(loaded, list) or not loaded or not all(
            isinstance(c, dict) for c in loaded):
        raise Refusal("the candidates must be a non-empty JSON list of "
                      '{"client", "terms"} objects')
    clients = [str(c.get("client") or "").strip() for c in loaded]
    doubled = sorted({c for c in clients if c and clients.count(c) > 1})
    if doubled:
        raise Refusal(f"one candidate per client, and {', '.join(doubled)} has more than one "
                      f"— a client's terms go in one list, because they are one rule")
    return loaded


def compile_rules(source: str, days: int, max_share: float, directory: Path) -> int:
    candidates = load_candidates(source)
    bucket, start_utc, end_utc, sample = sample_windows(days)
    if not sample:
        raise Refusal(f"no window events in the last {days} days, so there is nothing to "
                      f"test a category rule against. Bucket read: {bucket}")
    print(f"SAMPLE {len(sample)} titles over {days} days ({bucket})")

    judged = [judge(candidate, sample, max_share) for candidate in candidates]
    for verdict in judged:
        if verdict["verdict"] == "refuse":
            print(f"REFUSE {verdict['client'] or '?'} — {verdict['reason']}")
    unverified = unverified_as_dormant_or_suspect(judged)
    for line in unverified + overlaps(judged):
        print(line)
    if unverified:
        print_seen(sample)
    if any(v["verdict"] == "refuse" for v in judged):
        print("ERR nothing written: the refusals above have to be answered first, because "
              "a rule set is written whole and a bad rule in it would outrank a good one",
              file=sys.stderr)
        return 1

    writing = [j for j in judged if j["verdict"] == "write"]
    adopting = {name for candidate in candidates
                for name in _named_list(candidate.get("adopts"))}
    existing = read_classes()
    previously = managed_clients(directory)
    sending = merged(existing, writing, previously, adopting)
    dropped = sorted({class_name(e) for e in existing} - {class_name(e) for e in sending})
    backup = back_up(existing, directory)
    print(f"BACKUP {backup}")
    try:
        post_setting("classes", sending)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise Refusal(
            f"the activity source refused the write ({exc}). Nothing changed, and the rule "
            f"set as it was is in {backup}. The `setup` skill's category step falls back to "
            f"entering the rules by hand and verifying them, which is the route from here."
        ) from None
    print(f"WROTE {len(writing)} rules for {len(writing)} clients; "
          f"{len(sending) - len(writing)} rules left as they were")
    for name in dropped:
        print(f"DROPPED {name} — this plugin wrote it and nothing declares it now")

    code = verify(writing, bucket, start_utc, end_utc, backup)
    if code == 0:
        # Only now. The stamp is what tomorrow's staleness check believes, so recording a
        # write that did not land would report the rules current against a source that does
        # not hold them — and the run that would have rebuilt them skips.
        write_stamp(directory, writing)
    return code


def _named_list(value) -> list[str]:
    """A candidate's `adopts` — one existing category name, or several, or nothing."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str)]
    return []


def labelled_seconds(entry: dict, bucket: str, start_utc: str, end_utc: str) -> float:
    """How long the activity source's own `categorize` puts under this one class over the
    range — the class alone, so another rule taking the span first cannot hide it."""
    names = ", ".join(_query_string(part) for part in entry["name"])
    ignore_case = "true" if entry["rule"].get("ignore_case") else "false"
    classes = (f'[[[{names}], {{"type": "regex", "regex": {_query_string(entry["rule"]["regex"])}, '
               f'"ignore_case": {ignore_case}}}]]')
    answer = query([f"{start_utc}/{end_utc}"], [
        f"events = query_bucket({_query_string(bucket)});",
        f"events = categorize(events, {classes});",
        "RETURN = merge_events_by_keys(events, ['$category']);",
    ])
    return sum(e.get("duration", 0) for e in answer[0]
               if e.get("data", {}).get("$category") == entry["name"])


def _query_string(text: str) -> str:
    """A string literal in the activity source's query language. Its lexer un-escapes `\\"`
    and nothing else, so a backslash is written once — `json.dumps` doubles it, and the regex
    the server then compiles looks for a literal backslash (measured: a term with a `.` in it
    labelled nothing)."""
    return '"' + text.replace('"', '\\"') + '"'


def verify(writing: list[dict], bucket: str, start_utc: str, end_utc: str,
           backup: Path) -> int:
    """Read the rules back, and ask the activity source what each one labels.

    Two failures. A rule missing from what reads back is a write that did not land. A rule
    the gate matched titles with and the activity source labels nothing with is a rule
    written in a shape the activity source does not match — the gate and the source
    disagree, and only the source's answer is what a day will actually be labelled with.
    A term set that matched nothing in the gate is not a failure here: it was reported as
    unverified already.
    """
    landed = {}
    for entry in read_classes():
        regex = class_regex(entry)
        if regex:
            landed.setdefault((class_name(entry), regex), entry)
    failed = 0
    for judged in writing:
        key = (judged["client"], judged["regex"])
        if key not in landed:
            print(f"ERR {judged['client']} is not in the rules the activity source reads "
                  f"back — the write did not land", file=sys.stderr)
            failed += 1
            continue
        try:
            seconds = labelled_seconds(landed[key], bucket, start_utc, end_utc)
        except (urllib.error.URLError, OSError, ValueError, LookupError) as exc:
            print(f"ERR {judged['client']}: the activity source would not say what the rule "
                  f"labels ({exc}), so the write is unconfirmed. The rule set as it was is "
                  f"in {backup}", file=sys.stderr)
            failed += 1
            continue
        if judged["matched"] and not seconds:
            print(f"ERR {judged['client']}: the gate matched {len(judged['matched'])} titles "
                  f"and the activity source labels none of them with this rule — it is "
                  f"written in a shape the activity source does not match. The rule set as "
                  f"it was is in {backup}", file=sys.stderr)
            failed += 1
            continue
        print(f"VERIFY {judged['client']} — {len(judged['matched'])} sampled titles; the "
              f"activity source labels {seconds / 3600:.1f}h with it")
    return 1 if failed else 0


def managed_clients(directory: Path) -> set[str]:
    """The clients this plugin last wrote rules for, from the stamp.

    Read by name rather than by pattern: a rebuild changes the terms and the rule is still
    the same rule, and the name is what `merged()` replaces on. Everything else the
    activity source holds is the user's own, whether they made it before installing this or
    in the settings dialog last week.
    """
    stamp = read_stamp(directory) or {}
    return {rule.get("client") for rule in stamp.get("rules", [])}


def inspect(days: int, max_share: float, directory: Path) -> int:
    """Every rule the activity source holds now: managed or not, and the share of the
    sample each matches.

    The read behind adopting rules the plugin did not author. A run maps each unmanaged one
    to a client and the terms behind it, puts the whole set to the user as one list, and
    an over-broad rule is surfaced here rather than left to mislabel days. Prints the regex
    — the *agent* reads this output, and the user reads the plain-language list the agent
    makes of it.
    """
    bucket, _, _, sample = sample_windows(days)
    print(f"SAMPLE {len(sample)} titles over {days} days ({bucket})")
    # Before the rules: a build with no settings endpoint refuses below, and the tags are
    # read from the sample alone.
    print_seen(sample)
    print_hosts(sample)
    classes = read_classes()
    if not classes:
        print("RULES none — the activity source holds no categories")
        return 0
    rules = (read_stamp(directory) or {}).get("rules", [])
    managed = {rule.get("client") for rule in rules}
    written = {(rule.get("client"), rule.get("regex")) for rule in rules}
    for entry in classes:
        name = class_name(entry) or "(unnamed)"
        held = "managed" if name in managed else "unmanaged"
        regex = class_regex(entry)
        if not regex:
            print(f"RULE {name} [{held}] — no regex (a grouping category), matched against "
                  f"nothing")
            continue
        # A managed rule whose pattern is not the one the stamp recorded has been edited in
        # the settings dialog since. The staleness check cannot see this — it reads two local
        # files and nothing over the wire — so this is where a rule damaged by hand surfaces,
        # and a recompile is what puts it back (#69 story 5).
        edited = " EDITED since it was written" if (
            held == "managed" and (name, regex) not in written) else ""
        try:
            hits = matching(regex, sample)
        except re.error as exc:
            print(f"RULE {name} [{held}] — does not compile ({exc}): {regex}")
            continue
        share = len(hits) / len(sample) if sample else 0.0
        over = f"  OVER the {max_share:.0%} ceiling" if share > max_share else ""
        print(f"RULE {name} [{held}]{edited} — {len(hits)} of {len(sample)} titles "
              f"({share:.0%}){over}  regex: {regex}")
        for example in hits[:2]:
            print(f"     e.g. {shown(example)[:100]}")
    return 0


def status(directory: Path) -> int:
    """Whether the rules are still the ones the workspace context file implies.

    Reads two local files and nothing over the wire, so a run can afford it at the start of
    every day. It answers `BROKEN`, `STALE` or `CURRENT` and exits 0 whichever: each is a
    state to act on, not a failure.

    `BROKEN` is a stamp from before 0.11.0, whose rules carry a `signal`. Those were written
    anchored on the app name, a shape the activity source never matches, so they label
    nothing however current the context file is — and the rebuild they need is the `setup`
    skill's category step, where the terms are chosen with the user, not a quiet recompile.
    """
    stamp = read_stamp(directory)
    digest, path = context_fingerprint(directory.parent)
    if stamp is None:
        print(f"STALE this plugin has not written the category rules from {path} — nothing "
              f"records what they were built from")
        return 0
    if any("signal" in rule for rule in stamp.get("rules", [])):
        print(f"BROKEN the category rules written {stamp.get('written', 'earlier')} are in a "
              f"shape the activity source never matches, so it labels no client with them. "
              f"Run the `setup` skill's category step to replace them")
        return 0
    if not digest:
        print(f"STALE there is no {path} to build rules from")
        return 0
    if stamp.get("context_sha256") != digest:
        print(f"STALE {path} has changed since the rules were written "
              f"({stamp.get('written', 'unknown')}) — recompile them")
        return 0
    print(f"CURRENT {len(stamp.get('rules', []))} rules, written {stamp.get('written')}, "
          f"and {path} has not changed since")
    return 0


def main():
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(
        description="Gate, write and verify the activity source's category rules.")
    ap.add_argument("--candidates",
                    help="JSON file of {client, terms} candidates, or `-` for stdin. Gates, "
                         "backs up, writes and verifies.")
    ap.add_argument("--inspect", action="store_true",
                    help="Report the rules the activity source holds now, each with the "
                         "share of the sample it matches. Writes nothing.")
    ap.add_argument("--status", action="store_true",
                    help="Say whether the rules are still current for the workspace "
                         "context file. Reads no activity source.")
    ap.add_argument("--days", type=int, default=DEFAULT_DAYS,
                    help=f"How many days of window titles to sample (default {DEFAULT_DAYS})")
    ap.add_argument("--max-share", type=float, default=DEFAULT_MAX_SHARE,
                    help=f"Refuse a term matching more than this share of the sampled "
                         f"titles (default {DEFAULT_MAX_SHARE})")
    ap.add_argument("--workspace",
                    help="The workspace to keep the backup and the stamp under, overriding "
                         "the configured TIMESHEET_WORKSPACE for this run")
    args = ap.parse_args()

    chosen = [bool(args.candidates), args.inspect, args.status]
    if sum(chosen) != 1:
        print("ERR give exactly one of --candidates, --inspect or --status", file=sys.stderr)
        return 2

    try:
        # `--inspect` resolves no workspace on purpose: it writes nothing, and creating a
        # state directory to read the activity source would leave a mark on whatever
        # directory a run happened to start in.
        if args.inspect:
            return inspect(args.days, args.max_share,
                           state_dir(args.workspace, create=False))
        if args.status:
            # Read-only, and run at the start of every day: it must not mint a directory in
            # whatever folder the session started in, nor fail because it could not.
            return status(state_dir(args.workspace, create=False))
        directory = state_dir(args.workspace)
        return compile_rules(args.candidates, args.days, args.max_share, directory)
    except Refusal as exc:
        print(f"ERR {exc}", file=sys.stderr)
        return 1
    except SourceError as exc:
        print(f"ERR {exc}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"ERR {unreachable(exc)}", file=sys.stderr)
        return 1
    except OSError as exc:
        # Narrower than it looks worth being: a network failure arrives as a `URLError`,
        # which is itself an `OSError`, so catching the base class first would report a
        # workspace this run could not write to as an activity source that is down — and
        # send whoever read it to restart a service that was never the problem.
        print(f"ERR {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

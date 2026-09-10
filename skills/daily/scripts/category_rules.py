"""The activity source's category rules: gate, order, back up, write, verify.

The plugin owns those rules (#69). The user declares their clients and **signals** in
`Timesheets/.context.md`; a run composes a pattern per signal and hands the candidates to
this script, which judges them and writes the ones that survive. The user never sees a
regex or a JSON body.

**Composition is the model's, enforcement is this script's.** The context file legitimately
holds prose, hints and free text, so no parser should be asked to read it — which is why
this takes *candidate rules* rather than the file. What it does with them is deterministic:

  1. **Gate.** A pattern that does not compile, one that matches none of the sampled window
     titles, and one that matches an implausible share of them are all refused, and a
     refusal anywhere writes nothing. The measured case for the third is a bare-word rule
     matching 256 of 552 browser titles in one day: via first-match-wins that does not just
     add noise, it takes the label off a correct rule.
  2. **Order.** Imposed here by signal type, most specific first, with the profile tag
     deliberately last — so when two clients' rules both match a span, the more specific
     evidence wins. The candidates' own order is not consulted.
  3. **Back up.** The current rule set is copied into the workspace before the first write.
     That is the recovery path, and it is what makes the write safe to perform without
     showing the user a diff.
  4. **Write.** One class per candidate, named for the client, merged over what is already
     there: a rule this plugin did not author is kept exactly as it was.
  5. **Verify.** The rules are read back and each is re-matched against the sample, so a
     write that did not land is reported now rather than surfacing days later as a client
     whose whole day came back uncategorized.

Which signal types compile is this script's table too, and it is about the activity source
rather than about the user: only a type that can appear in an app name or a window title is
compiled. A local repository path cannot — an editor titles its window with the workspace
name — so it is skipped rather than refused.

Three modes:
  * `--candidates <file|->`  compile, gate, back up, write, verify
  * `--inspect`              what the activity source holds now, each rule marked managed
                             or not and carrying the share of the sample it matches — the
                             read behind adopting rules the plugin did not author
  * `--status`               whether the rules are still current for the workspace context
                             file. Reads two local files and nothing over the wire

No third-party deps — stdlib urllib, via the shared aw_client.py.

Usage:
  python scripts/category_rules.py --candidates candidates.json
  python scripts/category_rules.py --inspect
  python scripts/category_rules.py --status
"""
import argparse
import datetime as dt
import hashlib
import io
import json
import re
import sys
import urllib.error
from pathlib import Path

import skill_config
from aw_client import SourceError, get, post_setting, unreachable, window_day

# How much of the day the sample covers. A week rather than a day so a client worked on
# only on Tuesdays still has titles to gate against; the whole point of the gate is that a
# rule is judged against real evidence, and a sample that is too thin refuses a good rule.
DEFAULT_DAYS = 7

# The share of sampled titles above which a rule is refused as over-broad. The measured bad
# case is 0.46 (256 of 552 in one day), so the ceiling has to sit below that; 0.35 is the
# nearest round number that does. It is a judgement call and therefore a flag as well —
# a one-client consultant legitimately runs hotter than a five-client one, and the
# `## Preferences` line in the workspace template is where a user's own value belongs.
DEFAULT_MAX_SHARE = 0.35

# Which signal types compile, in the order a rule made from one outranks a rule made from
# another. The rank is the whole point: `categorize()` takes the *first* matching class as a
# span's label, so this table is what decides which client wins a span two rules both match.
#
# `scope` names the application family a rule of that type is confined to, or None where the
# signal implies no application. It is applied here rather than trusted to the composition:
# a work item number is evidence wherever it appears, but a client's *name* in a page title
# is evidence about a browser window and nothing else.
SIGNAL_RANK = {
    "work_item_prefix": (10, None),
    "url_host": (20, "browser"),
    "editor_workspace": (30, "editor"),
    "teams_team": (40, "meeting"),
    "title_token": (50, None),
    "browser_profile": (80, "browser"),
    "profile_tag": (90, "browser"),
}

# At or above this rank a signal is a *fallback*: it identifies browser time carrying no
# other evidence, and it is deliberately beaten by anything more specific — including a rule
# this plugin did not write. See `merged()`, which is where that ordering is imposed.
FALLBACK_RANK = 80

# The two signals that are the client's name by construction, because the user chose them as
# a name for the client: the bracketed code the extension injects, and the name they gave a
# browser profile. Exempt from the "never just the client's name" refusal, which is about
# evidence the work produced rather than a marker the user configured.
NAMED_BY_THE_USER = {"profile_tag", "browser_profile"}

# A signal type that is real, declared by users, and never reaches a window title — so it is
# skipped rather than refused, with the reason said out loud. On the machine this was
# specified against there is no editor bucket at all, and an editor titles its window with
# the workspace name rather than the path to it.
NOT_IN_A_TITLE = {
    "repo_path": "a local repository path never reaches a window title — an editor titles "
                 "its window with the workspace name, which is `editor_workspace`",
}

# The app-name alternations a scoped rule is anchored on. Matched against the start of the
# haystack, which is `"<app> <title>"` — see `categorize()` in activity_timeline.py. Both
# spellings of the ones that differ by platform: the window watcher reports `msedge.exe` on
# Windows and `Microsoft Edge` on macOS, and a rule that only knew one of them would be
# refused by the gate on the other rather than written wrong.
SCOPES = {
    "browser": (r"msedge|microsoft edge|chrome|google chrome|chromium|firefox|opera|brave|"
                r"safari|vivaldi|arc|iexplore"),
    "editor": (r"code|visual studio code|codium|devenv|visual studio|idea|pycharm|"
               r"webstorm|rider|sublime_text|notepad\+\+|nvim|vim|emacs"),
    "meeting": r"teams|ms-teams|microsoft teams|zoom|slack|webex",
}

# Where the backup and the stamp live under the workspace. `.mcp/` already holds the cached
# catalogs — machine state the user does not hand-edit — which is what both of these are.
STATE_DIR = ".mcp"
STAMP = "category-rules.json"
CONTEXT_FILE = Path("Timesheets") / ".context.md"


class Refusal(Exception):
    """A run that cannot proceed: one line printed after `ERR`, exit 1. Everything the gate
    refuses is reported together rather than raised, so a run fixing its candidates sees all
    of them at once; this is for the failures that stop the run before that."""


# --------------------------------------------------------------------------------------
# The sample
# --------------------------------------------------------------------------------------

def sample_titles(days: int) -> tuple[str, list[str]]:
    """The distinct `"<app> <title>"` haystacks the window watcher saw over the last
    `days`, and the bucket they came from.

    Distinct, because share is a question about the day's *variety* and a title left open
    all afternoon is one title however long it stayed there. Read over a rolling window
    ending now rather than over a named local date: this runs during setup, before the
    timezone is necessarily configured, and a rule is no better or worse for having been
    gated against a day that ends at midnight.
    """
    end = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    start = end - dt.timedelta(days=days)
    _, bucket, events = window_day(start.isoformat().replace("+00:00", "Z"),
                                   end.isoformat().replace("+00:00", "Z"),
                                   "there is nothing to test a category rule against")
    seen = {}
    for event in events:
        data = event.get("data") or {}
        seen.setdefault(f"{data.get('app', '?')} {data.get('title', '') or ''}", None)
    return bucket, list(seen)


# --------------------------------------------------------------------------------------
# The gate
# --------------------------------------------------------------------------------------

def compose(pattern: str, signal: str) -> str:
    """The regex actually written, from the pattern the model composed.

    A scoped signal type is anchored on its application family; an unscoped one is written
    through unchanged. The user's pattern is always wrapped in `(?:…)`, so a top-level
    alternation in it stays one alternative of this rule rather than swallowing the anchor.
    """
    scope = SIGNAL_RANK[signal][1]
    if not scope:
        return pattern
    return f"^(?:{SCOPES[scope]}).*(?:{pattern})"


def matching(regex: str, sample: list[str]) -> list[str]:
    """The sampled titles a regex matches, case-insensitively.

    One implementation, because the three callers — the gate, the verify and `--inspect` —
    are asking the same question and were asking it three ways. The case flag is the third
    copy that mattered: `merged()` writes every rule with `ignore_case: true`, so a reader
    that compiled without it would report a share the activity source will not reproduce.
    """
    compiled = re.compile(regex, re.IGNORECASE)
    return [haystack for haystack in sample if compiled.search(haystack)]


def denominator(signal: str, sample: list[str]) -> tuple[list[str], str]:
    """The titles a rule's share is measured against, and what to call them.

    Not the whole sample, for a scoped signal. The ceiling was calibrated on a rule matching
    **256 of 552 browser titles** in one day; measured against every window title that
    machine saw — Explorer, the editor, Teams — the same rule scores well under the ceiling
    and is written. A browser-scoped rule can only ever match browser titles, so the browser
    titles are the population it is broad *within*, and comparing it to anything else scales
    the number by how much of the day was spent outside a browser.
    """
    scope = SIGNAL_RANK[signal][1]
    if not scope:
        return sample, "sampled titles"
    anchor = re.compile(f"^(?:{SCOPES[scope]})", re.IGNORECASE)
    return [h for h in sample if anchor.match(h)], f"sampled {scope} titles"


def judge(candidate: dict, sample: list[str], max_share: float) -> dict:
    """One candidate, decided: `verdict` is `write`, `skip` or `refuse`, with a `reason`
    for the two that are not `write`, and the matching that earned it.

    Everything here is a property of the candidate and the sample, so a caller can report
    every verdict before acting on any of them. Nothing is written from this function.
    """
    client = (candidate.get("client") or "").strip()
    signal = (candidate.get("signal") or "").strip()
    pattern = candidate.get("pattern") or ""
    out = {"client": client, "signal": signal, "pattern": pattern, "matched": 0,
           "share": 0.0, "regex": ""}

    def verdict(kind: str, reason: str) -> dict:
        return {**out, "verdict": kind, "reason": reason}

    if not client or not signal or not pattern:
        return verdict("refuse", "a candidate needs a client, a signal and a pattern")
    if signal in NOT_IN_A_TITLE:
        return verdict("skip", NOT_IN_A_TITLE[signal])
    if signal not in SIGNAL_RANK:
        return verdict("refuse", f"unknown signal type '{signal}' — the types that compile "
                                 f"are {', '.join(sorted(SIGNAL_RANK))}, and "
                                 f"{', '.join(sorted(NOT_IN_A_TITLE))} never reaches a title")
    if signal not in NAMED_BY_THE_USER and _is_only_the_clients_name(pattern, client):
        return verdict("refuse", f"the pattern is only the client's name. A category named "
                                 f"for {client} that matches the word {client} labels every "
                                 f"unrelated page that mentions them; match a signal instead")
    regex = compose(pattern, signal)
    out["regex"] = regex
    try:
        re.compile(regex)
    except re.error as exc:
        return verdict("refuse", f"the pattern does not compile: {exc}")
    population, called = denominator(signal, sample)
    out["matched"] = len(matching(regex, population))
    out["share"] = out["matched"] / len(population) if population else 0.0
    if not out["matched"]:
        scope = SIGNAL_RANK[signal][1]
        scoped = f", scoped to a {scope} window," if scope else ""
        return verdict("refuse", f"matches none of the {len(population)} {called}{scoped} "
                                 f"— a rule that matches nothing leaves that client's whole "
                                 f"day uncategorized")
    if out["share"] > max_share:
        return verdict("refuse", f"matches {out['matched']} of {len(population)} {called} "
                                 f"({out['share']:.0%}), over the {max_share:.0%} ceiling. "
                                 f"The first matching rule wins, so a rule this broad takes "
                                 f"the label off a correct one; match a narrower signal")
    return verdict("write", "")


def _is_only_the_clients_name(pattern: str, client: str) -> bool:
    """Whether a pattern is the client's name and nothing else.

    Read after stripping the regex punctuation, so `\\bAcme\\b` and `(?:Acme)` are caught
    along with the bare word. `NAMED_BY_THE_USER` is exempt at the call site: those two
    markers are things the user *called* the client — a bracketed code, a browser profile's
    name — so being the client's name is what they are, and refusing that would refuse the
    ordinary case. Every other type is evidence the work produced, where the client's name
    on its own labels every unrelated page that mentions them.
    """
    bare = re.sub(r"\\b|\(\?:|\(\?i\)", "", pattern)
    bare = re.sub(r"[\\^$()\[\]{}?*+|]", "", bare).strip()
    return bare.casefold() == client.casefold() or bare.casefold() in {
        word.casefold() for word in client.split()}


def in_rank_order(judged: list[dict]) -> list[dict]:
    """The rules to write, most specific signal type first, profile tags last.

    Sorted on the rank alone, so the order candidates arrive in decides nothing beyond
    ties inside one type — `sorted` is stable, which is the whole of what a tie deserves.
    """
    return sorted([j for j in judged if j["verdict"] == "write"],
                  key=lambda j: SIGNAL_RANK[j["signal"]][0])


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
    """The `classes` list to send, in the order the labels are decided in.

    Three groups, and the order is the whole point, because `categorize()` takes the *first*
    matching class as a span's label:

      1. the specific rules being written — a work item number, an environment address, an
         editor workspace;
      2. everything the plugin did not author, untouched and in the order it was already in;
      3. the **fallback** rules being written, a profile tag and a profile name.

    Putting group 3 last rather than with the rest of the managed set is what makes "the more
    specific evidence wins" true against the user's *own* rules as well as against ours. A
    managed profile tag above a user's work-item rule would take the label off it — the same
    theft the tag was narrowed to single-client profiles to prevent, arriving by a different
    route, and worst for the user who skipped adoption and kept their rules.

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
    ours = [(SIGNAL_RANK[judged["signal"]][0],
             {"id": next_id + offset,
              "name": [judged["client"]],
              "rule": {"type": "regex", "regex": judged["regex"], "ignore_case": True}})
            for offset, judged in enumerate(writing)]
    specific = [entry for rank, entry in ours if rank < FALLBACK_RANK]
    fallback = [entry for rank, entry in ours if rank >= FALLBACK_RANK]
    return specific + kept + fallback


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

    The whole file, not the section that declares the signals: parsing that section is the
    thing this feature deliberately does not do, and a digest of the bytes costs one read
    and cannot be fooled. The price is a rebuild after an edit that changed a preference
    rather than a signal, which writes the same rules back and is cheap.
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
        "rules": [{"client": j["client"], "signal": j["signal"], "regex": j["regex"]}
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
    """The candidate rules, from a file or from stdin (`-`).

    A list of `{"client", "signal", "pattern"}` objects. A single object is accepted as a
    list of one, because that is what a run testing a single client writes.
    """
    raw = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
    try:
        loaded = json.loads(raw)
    except ValueError as exc:
        raise Refusal(f"the candidates are not JSON: {exc}") from None
    if isinstance(loaded, dict):
        loaded = loaded.get("candidates", [loaded])
    if not isinstance(loaded, list) or not loaded:
        raise Refusal("the candidates must be a non-empty JSON list of "
                      '{"client", "signal", "pattern"} objects')
    return loaded


def compile_rules(source: str, days: int, max_share: float, directory: Path) -> int:
    candidates = load_candidates(source)
    bucket, sample = sample_titles(days)
    if not sample:
        raise Refusal(f"no window events in the last {days} days, so there is nothing to "
                      f"test a category rule against. Bucket read: {bucket}")
    print(f"SAMPLE {len(sample)} titles over {days} days ({bucket})")

    judged = [judge(candidate, sample, max_share) for candidate in candidates]
    for verdict in judged:
        if verdict["verdict"] != "write":
            print(f"{verdict['verdict'].upper()} {verdict['client'] or '?'} "
                  f"{verdict['signal'] or '?'} — {verdict['reason']}")
    if any(v["verdict"] == "refuse" for v in judged):
        print("ERR nothing written: the refusals above have to be answered first, because "
              "a rule set is written whole and a bad rule in it would outrank a good one",
              file=sys.stderr)
        return 1

    writing = in_rank_order(judged)
    if not writing:
        print("ERR nothing written: no candidate compiled into a rule", file=sys.stderr)
        return 1

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
    print(f"WROTE {len(writing)} rules for {len({j['client'] for j in writing})} clients; "
          f"{len(sending) - len(writing)} rules left as they were")
    for name in dropped:
        print(f"DROPPED {name} — this plugin wrote it and nothing declares it now")

    code = verify(writing, sample)
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


def verify(writing: list[dict], sample: list[str]) -> int:
    """Read the rules back and re-match each against the sample.

    The gate has already refused a rule that matches nothing, so a zero here is not a bad
    rule — it is a write that did not land, and it is the difference between a configured
    install and one that looks configured.
    """
    landed = {}
    for entry in read_classes():
        regex = class_regex(entry)
        if regex:
            landed.setdefault((class_name(entry), regex), entry)
    missing = 0
    for judged in writing:
        key = (judged["client"], judged["regex"])
        if key not in landed:
            print(f"ERR {judged['client']} {judged['signal']} is not in the rules the "
                  f"activity source reads back — the write did not land", file=sys.stderr)
            missing += 1
            continue
        population, called = denominator(judged["signal"], sample)
        matched = len(matching(judged["regex"], population))
        print(f"VERIFY {judged['client']} {judged['signal']} — {matched} of "
              f"{len(population)} {called}")
    return 1 if missing else 0


def managed_clients(directory: Path) -> set[str]:
    """The clients this plugin last wrote rules for, from the stamp.

    Read by name rather than by pattern: a rebuild changes the pattern and the rule is
    still the same rule, and the name is what `merged()` replaces on. Everything else the
    activity source holds is the user's own, whether they made it before installing this or
    in the settings dialog last week.
    """
    stamp = read_stamp(directory) or {}
    return {rule.get("client") for rule in stamp.get("rules", [])}


def inspect(days: int, max_share: float, directory: Path) -> int:
    """Every rule the activity source holds now: managed or not, and the share of the
    sample each matches.

    The read behind adopting rules the plugin did not author. A run maps each unmanaged one
    to a client and the signals behind it, puts the whole set to the user as one list, and
    an over-broad rule is surfaced here rather than left to mislabel days. Prints the regex
    — the *agent* reads this output, and the user reads the plain-language list the agent
    makes of it.
    """
    bucket, sample = sample_titles(days)
    print(f"SAMPLE {len(sample)} titles over {days} days ({bucket})")
    classes = read_classes()
    if not classes:
        print("RULES none — the activity source holds no categories")
        return 0
    written = {rule.get("client"): rule.get("regex")
               for rule in (read_stamp(directory) or {}).get("rules", [])}
    for entry in classes:
        name = class_name(entry) or "(unnamed)"
        held = "managed" if name in written else "unmanaged"
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
            held == "managed" and written.get(name) != regex) else ""
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
            print(f"     e.g. {example[:100]}")
    return 0


def status(directory: Path) -> int:
    """Whether the rules are still the ones the workspace context file implies.

    Reads two local files and nothing over the wire, so a run can afford it at the start of
    every day. It answers `STALE` or `CURRENT` and exits 0 either way: staleness is a state
    to act on, not a failure — the caller rebuilds and moves on.
    """
    stamp = read_stamp(directory)
    digest, path = context_fingerprint(directory.parent)
    if stamp is None:
        print(f"STALE this plugin has not written the category rules from {path} — nothing "
              f"records what they were built from")
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
        description="Compile, gate, write and verify the activity source's category rules.")
    ap.add_argument("--candidates",
                    help="JSON file of {client, signal, pattern} candidate rules, or `-` "
                         "for stdin. Compiles, gates, backs up, writes and verifies.")
    ap.add_argument("--inspect", action="store_true",
                    help="Report the rules the activity source holds now, each with the "
                         "share of the sample it matches. Writes nothing.")
    ap.add_argument("--status", action="store_true",
                    help="Say whether the rules are still current for the workspace "
                         "context file. Reads no activity source.")
    ap.add_argument("--days", type=int, default=DEFAULT_DAYS,
                    help=f"How many days of window titles to sample (default {DEFAULT_DAYS})")
    ap.add_argument("--max-share", type=float, default=DEFAULT_MAX_SHARE,
                    help=f"Refuse a rule matching more than this share of the sampled "
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

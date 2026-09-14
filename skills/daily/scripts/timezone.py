"""The zone a day is read in, and the clock arithmetic that follows from it.

Both halves of this skill need this and neither owns it. The day-reading scripts need it to
bound a day, to parse a `--window` and to render an instant a person will read; the provider
scripts need it to tell whether an entry runs through a clock change that would bill it
short. It lived in `aw_client.py` until #36, which meant `harvest_post.py` and
`harvest_patch.py` imported the activity-source client to get at it — the one import edge
that ran the wrong way, and one an adapter behind a boundary cannot have. Nothing about the
functions changed in the move; only where they live.

So this module knows about neither side: it reads the configured zone through
`skill_config`, like everything else here, and imports nothing else of this skill's.
`tests/test_module_boundaries.py` holds that.

**A zone, not an offset.** A day does not necessarily have one offset — on the two dates a
year the clocks change it has two — so every conversion below takes the zone itself and
resolves each instant at the offset in force for *it*. `resolve_zone()` says what a single
figure read once cost.

**Configured, or the machine's own — never assumed.** With nothing configured the zone is
read from the machine (#30), and every run that does so says so: the source travels with
the zone (`resolve_zone_with_source()`), and `zone_label()` names a derived zone as the
machine's. What it never does is fall back to a fixed offset; `resolve_zone_with_source()`
carries the history of the one that used to be here.

No third-party deps — stdlib `zoneinfo`, `winreg` where there is one, like the sibling
modules.
"""
import datetime as dt
import os
import sys
from pathlib import Path
from typing import NamedTuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import skill_config

# Where a resolved zone came from. The words are read by the prose the run writes — the
# label a derived zone carries into a skeleton header and a timesheet's notes — so they are
# constants rather than spellings, and a test holds the documents to them.
CONFIGURED, DERIVED, OVERRIDE = "configured", "derived", "override"


class Resolved(NamedTuple):
    """A zone and which of the three sources answered for it."""
    zone: dt.tzinfo
    source: str


def resolve_zone(flag, offers_offset_flag: bool = True):
    """The timezone this day's local clock is read in — the zone alone.

    For the callers that only convert. A caller that will *print* the zone wants
    `resolve_zone_with_source()`, because a zone read from the machine has to be announced
    as such wherever the user reads it.
    """
    return resolve_zone_with_source(flag, offers_offset_flag).zone


def resolve_zone_with_source(flag, offers_offset_flag: bool = True) -> Resolved:
    """The timezone this day's local clock is read in, and where it came from.

    Three sources, highest first:

    1. `flag` is whatever `--utc-offset` supplied, or None; it wins, so a day spent in
       another zone can still be reconstructed without reconfiguring anything. It resolves
       to a zone that is that offset all year, which is what passing a number has always
       meant. Source `OVERRIDE`.
    2. The configured `TIMESHEET_TIMEZONE`, when it is set. Source `CONFIGURED`.
    3. The machine's own zone, read by `machine_zone_name()`, when nothing is configured.
       Source `DERIVED` — and that word reaches the user, which is the whole difference
       between this and a default. A derived value that is never announced is a silent
       default; one announced every run follows the user across zones and tells them it did.

    Nothing after that. A derivation that misses, or that names a zone this interpreter
    cannot load, produces the same refusal an unconfigured run has always produced — naming
    the setting and how to set it, and never an offset. The unloadable case adds the one
    line saying what the machine reported and the install that makes it load, because on
    Windows `zoneinfo` has no data without `tzdata`: the machine can name `Pacific/Auckland`
    correctly and the run still cannot read a day in it, so a derivation is validated by
    resolving, never by producing a string.

    `offers_offset_flag=False` says the calling script has no such per-run override —
    which the provider scripts have not, carrying no flags but their fields and the
    confirmation gate. The messages below then stop naming `--utc-offset`, rather than
    sending a user who is already stuck to try one more thing that would come back as a
    usage error.

    A boolean and not the flag's own spelling, which is what it was first written as: a
    bare `"--utc-offset"` default here is indistinguishable from a flag *this* module
    parses, and `tests/test_references.py` said so — it reads the flags out of each
    script's syntax tree and wanted this one added to the inventory entry of the module
    this used to live in, where it would tell every run that a module with no command line
    takes an argument. There is one spelling of the flag either way, so nothing is lost by
    not passing it.

    A zone rather than a number, because a day does not necessarily have *one* offset.
    This used to answer with a single figure read at local noon, and on the day the clocks
    change that is wrong at both ends of the day at once: the fetch window opens an hour
    late or early, and every event on the far side of the transition renders an hour out.
    Neither failure raises anything — the day simply reads short and starts in the wrong
    place. Handing the zone itself to the arithmetic below lets each instant be converted
    at the offset in force for *it*.

    There is deliberately no fixed fallback. This used to be `default=12.0` in both
    day-reading scripts' argument parsers, so every user who was not in New Zealand got a
    day boundary up to twelve hours out — and, again, nothing failed. No offset is safe to
    guess; the machine's own zone is not a guess, and is labelled so that a wrong one is
    seen rather than billed from.
    """
    if flag is not None:
        try:
            return Resolved(dt.timezone(dt.timedelta(hours=flag)), OVERRIDE)
        except (ValueError, OverflowError):
            # Every other bad input to these scripts produces a line and a non-zero exit;
            # one that escaped from here would be the single traceback, and a traceback
            # tells a model reading this that the tool is broken rather than that the
            # number is. Both exception types, because `argparse type=float` takes `inf`
            # as readily as `99` and the timedelta constructor answers them differently.
            skill_config.fail_missing(
                f"--utc-offset {flag} is not an offset any zone has.\n"
                "  It is hours from UTC, between -24 and 24, e.g. 13 or -5.5.")
    name = skill_config.setting("TIMESHEET_TIMEZONE")
    if name:
        return Resolved(_load(name, offers_offset_flag), CONFIGURED)
    derived = machine_zone_name()
    if derived:
        try:
            return Resolved(ZoneInfo(derived), DERIVED)
        except (ZoneInfoNotFoundError, ValueError):
            pass
    skill_config.fail_missing(
        ("No timezone configured, and no --utc-offset given.\n" if offers_offset_flag
         else "No timezone configured.\n") +
        "  Your zone decides where a day begins and ends, and when the clocks change\n"
        "  inside it, so there is nothing safe to assume.\n"
        "  Set it once:  /plugin configure billables  -> TIMESHEET_TIMEZONE\n"
        "                (an IANA name, e.g. Europe/London or Pacific/Auckland)\n"
        "  Already set it? Start a new session — the value is published at session\n"
        "  start. If a new session still shows this, see references/first-run.md\n"
        "  § 'When the configuration does not arrive'." +
        (f"\n  This machine reports its zone as {derived}, which could not be loaded —\n"
         "  on Windows the zone database is a separate install:  pip install tzdata"
         if derived else
         "\n  This machine's own zone could not be read, or is not one this plugin knows.") +
        ("\n  Or for this run only:  --utc-offset <hours>" if offers_offset_flag else "")
        # Last, after the escape hatch, because it is the cause a user cannot deduce
        # and the two lines above are the wrong advice for it. Shared with
        # `harvest_client.load_creds()`: one absence, one cause, one wording.
        + skill_config.note_for_an_unreached_shell())


def _load(name: str, offers_offset_flag: bool) -> ZoneInfo:
    """A configured name as a zone, or the refusal that names it.

    Two causes, one message: a mistyped IANA name, and a Windows Python with no zone
    database installed. Both are "this name did not resolve", and both are fixed by one of
    the two lines below, so the message names the check and the escape hatch rather than
    guessing which."""
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        skill_config.fail_missing(
            f"Could not load the timezone '{name}' ({exc}).\n"
            "  Check it against the IANA list (e.g. Europe/London, Pacific/Auckland).\n"
            "  On Windows the zone database is a separate install:  pip install tzdata" +
            ("\n  Or bypass it for this run:  --utc-offset <hours>" if offers_offset_flag
             else ""))


def machine_zone_name(platform: str | None = None, environ=None, root: Path = Path("/"),
                      registry=None) -> str | None:
    """The IANA name of this machine's own zone, or None when it cannot be read.

    Windows keeps its zone under its own names — `New Zealand Standard Time` — in the
    registry, read here with `winreg` and mapped through `WINDOWS_ZONES` below, the CLDR
    table of one IANA zone per Windows identifier. An identifier the table does not know is
    a miss, not an approximation. `TryConvertWindowsIdToIanaId` would do the same in one
    call and was rejected: it is .NET 6+, so it exists under `pwsh` and not under the
    Windows PowerShell 5.1 the `setup` skill supports, and it would mean spawning a shell to
    learn a fact the registry holds.

    A POSIX machine names its zone in one of three places, any of which may be absent:
    `TZ` in the environment, the target of the `/etc/localtime` symlink (the path after
    `zoneinfo/`), and the contents of `/etc/timezone`. The first that yields a name wins;
    none of them is validated here — the caller loads it, and a name that will not load is
    the caller's refusal.

    Every parameter is for the tests: `platform` and `environ` drive the branch, `root`
    relocates `/etc`, and `registry` stands in for the `winreg` read. A run passes none of
    them.
    """
    platform = sys.platform if platform is None else platform
    environ = os.environ if environ is None else environ
    if platform == "win32":
        return _windows_zone_name(registry or _registry_zone_key_name)
    return _posix_zone_name(environ, root)


def _registry_zone_key_name() -> str | None:
    """`TimeZoneKeyName` under `HKLM\\SYSTEM\\CurrentControlSet\\Control\\TimeZoneInformation`,
    or None off Windows or when the key cannot be read."""
    # Guarded on `sys.platform` and not by catching `ImportError`, though both refuse off
    # Windows at runtime: `winreg` is Windows-only in typeshed, so a type checker running
    # on Linux resolves none of its attributes and reports three errors an import guard
    # cannot narrow away. `sys.platform` it does narrow, which is what keeps the Linux half
    # of the `Checks` matrix green.
    if sys.platform != "win32":
        return None
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SYSTEM\CurrentControlSet\Control\TimeZoneInformation") as key:
            value, _ = winreg.QueryValueEx(key, "TimeZoneKeyName")
    except OSError:
        return None
    # Some Windows releases pad the value with NULs past the name; stripped rather than
    # matched, so the lookup below sees the name and not its storage.
    return str(value).rstrip("\x00").strip() or None


def _windows_zone_name(registry) -> str | None:
    key_name = registry()
    return WINDOWS_ZONES.get(key_name) if key_name else None


def _posix_zone_name(environ, root: Path) -> str | None:
    tz = (environ.get("TZ") or "").strip().lstrip(":")
    if tz:
        return tz
    localtime = root / "etc" / "localtime"
    try:
        if localtime.is_symlink():
            target = os.readlink(localtime).replace("\\", "/")
            _, sep, tail = target.rpartition("zoneinfo/")
            if sep and tail:
                return tail
    except OSError:
        pass
    timezone_file = root / "etc" / "timezone"
    try:
        text = timezone_file.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return text or None


def zone_label(zone, source: str = CONFIGURED):
    """How a resolved zone names itself in a header a person reads.

    A real zone is named, because on a transition day no single offset describes it and
    printing one would be a claim the run is not making. A `--utc-offset` zone keeps the
    wording it always had, since that is exactly what the user typed. A zone the machine
    supplied says so — `zone Europe/London, derived from this machine` — because that
    announcement is what makes reading it safe: a wrong one is seen, not billed from.
    """
    key = getattr(zone, "key", None)
    if key:
        label = f"zone {key}"
        if source == DERIVED:
            label += f", {DERIVED} from this machine"
        return label
    return f"offset UTC{zone.utcoffset(None).total_seconds() / 3600:+g}"


SECOND_PASS_MARK = "*"


def parse_local_time(s):
    """Parse 'HH:MM' or 'HH:MM:SS' to a datetime.time, reading a trailing `*`.

    The `*` is how a caller names the *second* pass over the hour a fall-back repeats —
    the shape `local_clock()` writes — and it survives as the returned time's `fold`,
    which `to_utc()` then honours. Without it the plain reading stands, so every time
    written before this existed still means what it did.
    """
    s = s.strip()
    fold = 0
    if s.endswith(SECOND_PASS_MARK):
        s, fold = s[:-len(SECOND_PASS_MARK)].strip(), 1
    fmt = "%H:%M:%S" if s.count(":") == 2 else "%H:%M"
    return dt.datetime.strptime(s, fmt).time().replace(fold=fold)


READS_ONCE, READS_TWICE, READS_NEVER = "once", "twice", "never"


def clock_reads(local_date, local_time, zone):
    """How many times a clock in `zone` reaches this reading on this date — `READS_ONCE`
    on any ordinary reading, `READS_TWICE` inside the hour a fall-back repeats,
    `READS_NEVER` inside the hour a spring-forward skips.

    The two transition hours are told apart by the *sign* of the offset shift across
    `fold`, not by the fact that there is one. Under PEP 495 `fold=0` always means the
    offset in force before the change and `fold=1` the one after, so a repeated hour
    shifts backwards (in `Pacific/Auckland`, +13 to +12) and a skipped hour forwards (+12
    to +13). Asking only whether the two differ cannot separate them, and the callers
    below need to: a marker means one thing in a repeated hour and nothing at all in a
    skipped one.
    """
    moment = dt.datetime.combine(local_date, local_time, tzinfo=zone)
    # How far apart in real time the two passes sit. Measured by converting each to UTC
    # rather than by subtracting the two `utcoffset()`s, which is the same quantity —
    # an instant is its clock reading minus its offset, so the offsets cancel the other
    # way round — but is not typed as possibly absent the way an offset is.
    shift = (moment.replace(fold=0).astimezone(dt.timezone.utc)
             - moment.replace(fold=1).astimezone(dt.timezone.utc))
    if shift < dt.timedelta(0):
        return READS_TWICE
    if shift > dt.timedelta(0):
        return READS_NEVER
    return READS_ONCE


def to_utc(local_date, local_time, zone):
    """A wall-clock time on a local date, as the UTC instant it names in `zone`.

    The single place a local clock becomes an instant, so the transition-day answer is the
    same for a day boundary, a `--window` and a `--cover` block. On the hour a fall-back
    repeats, the wall clock is genuinely ambiguous, and this resolves it to whichever pass
    `local_time.fold` asks for — the first unless the caller marked it, which is what an
    unmarked time has always meant. On the hour a spring-forward skips, an *unmarked*
    reading takes the instant the clock would have reached. Both are conventions rather
    than facts — but only inside that one hour, and both scripts read the same one.

    A marker on a time the clock does not read twice is refused rather than ignored, and
    the two ways that happens are named apart. `zoneinfo` drops `fold` on an unambiguous
    reading, so `09:00*` would quietly mean `09:00` — a marker that sometimes carries
    meaning is worse than one that always does, because nothing in the output
    distinguishes the two cases. Inside a skipped hour `zoneinfo` does the opposite and
    honours `fold`, resolving `02:30*` an hour *earlier* than `02:30`, so the marker there
    used to be accepted and quietly report on a different hour than the one asked for.
    """
    moment = dt.datetime.combine(local_date, local_time, tzinfo=zone)
    if local_time.fold:
        reads = clock_reads(local_date, local_time, zone)
        clock = local_time.strftime("%H:%M:%S")
        opening = (f"'{clock}{SECOND_PASS_MARK}' names a second pass over a repeated "
                   f"hour, but ")
        if reads == READS_NEVER:
            raise ValueError(
                f"{opening}the clock never reads {clock} on {local_date} in this zone — "
                f"the clocks go forward at that hour, so no instant on that date carries "
                f"that reading at all")
        if reads == READS_ONCE:
            raise ValueError(
                f"{opening}the clock reads {clock} only once on {local_date} in this "
                f"zone — drop the '{SECOND_PASS_MARK}'")
    return moment.astimezone(dt.timezone.utc)


def _offset_at(moment, zone):
    """The offset in force at an instant, as a timedelta.

    By subtracting the two renderings rather than by asking `utcoffset()`, which is typed
    as possibly absent and is not, for the same reason `clock_reads` converts to UTC
    instead. Both operands are made naive first: a naive difference is the offset, where
    an aware one would be zero by construction.
    """
    return moment.astimezone(zone).replace(tzinfo=None) - moment.replace(tzinfo=None)


class Transition(NamedTuple):
    """The one clock change on a date: its two readings, and which way it went."""
    as_reached: dt.time         # what the clock said as the instant arrived
    once_passed: dt.time        # what it said immediately afterwards
    repeats: bool               # True if the span between them happens twice, not never


def transition_clocks(local_date, zone):
    """The clock change on `local_date`, or None if there isn't one.

    In `Pacific/Auckland` on 2026-04-05 the clocks go back at one instant that reads
    `03:00` as you arrive at it and `02:00` afterwards, so this answers
    `(03:00, 02:00, repeats=True)`; on the spring-forward day it answers
    `(02:00, 03:00, repeats=False)`, the same pair the other way round.

    `repeats` comes from the sign of the offset shift and not from comparing the two
    readings, which is the same distinction `clock_reads` draws and for a sharper reason
    here: a zone whose clocks go back at midnight reads `00:00` as it arrives and `23:00`
    once passed, so "the later reading came second" gets that day exactly backwards.
    `America/Santiago` does this every April.

    None on every other day, which is the answer for all but two dates a year and the one
    that keeps a caller's behaviour on those dates exactly what it was.

    Found by bisection because `zoneinfo` publishes no transition list — there is no
    supported way to ask a zone when it next changes, only what its offset is at a given
    instant. The day is bracketed by its own two midnights, resolved in the zone the way
    `utc_bounds` resolves them, so a day that is 23 or 25 hours long is searched at its
    real length. A second transition inside one day would be missed; no zone has had one
    since the standard-time era, and a day with two would break far more than this.
    """
    lo = to_utc(local_date, dt.time(0, 0), zone)
    hi = to_utc(local_date + dt.timedelta(days=1), dt.time(0, 0), zone)
    before, after = _offset_at(lo, zone), _offset_at(hi, zone)
    if before == after:
        return None
    while hi - lo > dt.timedelta(seconds=1):
        mid = lo + (hi - lo) / 2
        if _offset_at(mid, zone) == before:
            lo = mid
        else:
            hi = mid
    # `hi` is now the first instant past the change, within a second of it. Transitions
    # land on a minute boundary, so flooring recovers the instant itself exactly — and the
    # readings below are wanted to the minute regardless, since that is what a time entry
    # is written in.
    moment = hi.replace(second=0, microsecond=0)
    return Transition((moment + before).time(), (moment + after).time(), after < before)


def _minutes(t: dt.time) -> int:
    """A clock reading as minutes since midnight, the unit `repeated_span()` answers in."""
    return t.hour * 60 + t.minute


def repeated_span(spent, zone) -> tuple[int, int] | None:
    """The minutes-since-midnight bounds of the span the clocks repeat on `spent`, or None.

    Measured, never assumed: `Australia/Lord_Howe` moves thirty minutes and
    `Antarctica/Troll` two hours, and both figures come off the zone's own two readings.

    None means there is nothing on this date an entry could straddle, which is three
    different facts and not one:

    - no transition at all, which is every date but two a year;
    - a spring-forward. The clock skips rather than repeating, so an entry across it is
      over-billed rather than short, and its two pieces would be separated by a gap where
      these two abut — a different message, and #23 put it out of scope. The Open gaps entry
      for the skipped hour in `docs/skills/daily/decision-log.md` (in the repository, not in
      an installed copy) carries it. `repeats` comes from the sign of
      the offset shift and not from the order of the two readings, which gets
      `America/Santiago` exactly backwards;
    - a repeated span that crosses midnight, as it does in `America/Santiago`, where the
      clocks go back at 00:00 to 23:00. Containment would then need an end past 1440, and
      a clock reading caps at 23:59 — so a span that opens at 23:00 and closes at 00:00
      reads as `(1380, 0)`, and the guard is the `repeat_open >= repeat_close` line rather
      than a special case for that zone.

    Answered in minutes since midnight, not as the two `time`s the transition carries,
    because the callers compare it against an interval — and a caller that did its own
    conversion would be the second place the midnight-crossing case has to be got right.
    `harvest_write.py`'s `refusal_for_a_straddled_change()` is the one that decides what to
    do about a straddle; this is the cheap half of the question it asks first, and
    `harvest_patch.py` asks it directly for that reason: on a date with no repeated span it
    can skip reading the entry it is about to patch, which is a request over the wire.

    Here and not beside that refusal because the answer is the zone's: what the clocks did
    on a date is the same fact whoever is billing it, and how a provider bills across it is
    not.
    """
    change = transition_clocks(spent, zone)
    if change is None or not change.repeats:
        return None
    repeat_open, repeat_close = _minutes(change.once_passed), _minutes(change.as_reached)
    if repeat_open >= repeat_close:
        return None
    return repeat_open, repeat_close


def parse_range(rng, local_date, zone):
    """Parse a local 'HH:MM-HH:MM' (seconds optional) to an aware UTC (start, end) pair.

    Raises ValueError on a bad format or a reversed/empty range. Shared because both
    day-reading scripts take a `--window` in this shape and each used to parse it its own
    way: the afk one rejected `17:00-09:00`, the timeline one accepted it and printed an
    empty result, so the same typo produced an error in one script and a plausible-looking
    "nothing happened then" in the other.

    A range that runs backwards in real time has three causes on a transition day, and
    each gets its own message. Naming the wrong one is worse than naming none: a range
    refused for spanning a spring-forward on the day the clocks went *back* sends the
    reader hunting a transition six months away.
    """
    a, b = rng.split("-", 1)
    lo, hi = parse_local_time(a), parse_local_time(b)
    ws, we = to_utc(local_date, lo, zone), to_utc(local_date, hi, zone)
    if we <= ws:
        # `time` comparison ignores `fold`, so this asks only whether the two *clock
        # readings* run forwards — which is the question worth asking here, the instants
        # having already been shown not to. Stripping `fold` says so out loud.
        clock_ordered = hi.replace(fold=0) > lo.replace(fold=0)
        skipped = READS_NEVER in (clock_reads(local_date, lo, zone),
                                  clock_reads(local_date, hi, zone))
        if clock_ordered and skipped:
            # Ordered on the clock and empty in real time, with a reading inside the hour
            # a spring-forward skips: no instant on this date corresponds to it. Falling
            # through to "end must be after start" would send the user hunting a typo they
            # did not make.
            raise ValueError(f"'{rng}' spans the hour the clocks skip on {local_date}, "
                             f"so no time passed between those two readings")
        if clock_ordered and lo.fold and not hi.fold:
            # A fall-back day, marked on one end. The start is the second pass and the
            # unmarked end is the first, an hour earlier — the cause is the *end*, so say
            # so rather than blaming the range.
            raise ValueError(
                f"'{rng}' carries the second-pass marker on its start only, so the end "
                f"resolves to the first pass over the hour the clocks repeat on "
                f"{local_date} — an hour before the start. Mark both ends or neither")
        raise ValueError(f"end must be after start in range '{rng}'")
    return ws, we


def utc_bounds(local_date, zone):
    """The local day as the Z-suffixed UTC strings the activity source's events API wants.

    Both ends are resolved in the zone independently, so the day the clocks change is
    asked for at its true length — twenty-five hours in autumn, twenty-three in spring —
    rather than at a flat twenty-four hung off whichever offset was read once.
    """
    start = to_utc(local_date, dt.time(0, 0), zone)
    end = to_utc(local_date + dt.timedelta(days=1), dt.time(0, 0), zone)
    return (start.strftime("%Y-%m-%dT%H:%M:%SZ"), end.strftime("%Y-%m-%dT%H:%M:%SZ"))


def local_clock(moment, zone):
    """An instant as the `HH:MM:SS` a clock in `zone` showed at it.

    No date: a day that runs past midnight renders its end as `01:12:00`, which is the
    established output shape and the one the goldens pin.

    On the hour a fall-back repeats, that shape is not enough on its own — two instants an
    hour apart show the same clock — so the second pass over it is suffixed `*`. An
    hour-long break across the change used to render `02:30:00-02:30:00`, sixty minutes as
    a zero-length string; it now ends `02:30:00*`. The marker is exact rather than
    decorative: `parse_local_time()` reads it back, so a time lifted out of one script's
    output names the same instant when handed to another's `--window` or `--cover`.

    It appears on one hour of one day a year, and never at all for a `--utc-offset` run,
    whose zone is that offset all year and so has no repeated hour to mark.
    """
    local = moment.astimezone(zone)
    return local.strftime("%H:%M:%S") + (SECOND_PASS_MARK if local.fold else "")


# One IANA zone per Windows time-zone identifier: the `territory="001"` rows of CLDR's
# `common/supplemental/windowsZones.xml`, generated rather than typed, on 2026-09-11. A
# Windows machine names its zone with the left-hand string, in the registry; the scripts
# need the right-hand one. Several right-hand names are the zone database's older spellings
# (`Asia/Calcutta`, `Europe/Kiev`) because that is what CLDR carries — they load as links to
# the current names, and a name is validated by loading in any case. An identifier absent
# from this table is a miss, and the run says so rather than approximating.
WINDOWS_ZONES = {
    "Dateline Standard Time":            "Etc/GMT+12",
    "UTC-11":                            "Etc/GMT+11",
    "Aleutian Standard Time":            "America/Adak",
    "Hawaiian Standard Time":            "Pacific/Honolulu",
    "Marquesas Standard Time":           "Pacific/Marquesas",
    "Alaskan Standard Time":             "America/Anchorage",
    "UTC-09":                            "Etc/GMT+9",
    "Pacific Standard Time (Mexico)":    "America/Tijuana",
    "UTC-08":                            "Etc/GMT+8",
    "Pacific Standard Time":             "America/Los_Angeles",
    "US Mountain Standard Time":         "America/Phoenix",
    "Mountain Standard Time (Mexico)":   "America/Mazatlan",
    "Mountain Standard Time":            "America/Denver",
    "Yukon Standard Time":               "America/Whitehorse",
    "Central America Standard Time":     "America/Guatemala",
    "Central Standard Time":             "America/Chicago",
    "Easter Island Standard Time":       "Pacific/Easter",
    "Central Standard Time (Mexico)":    "America/Mexico_City",
    "Canada Central Standard Time":      "America/Regina",
    "SA Pacific Standard Time":          "America/Bogota",
    "Eastern Standard Time (Mexico)":    "America/Cancun",
    "Eastern Standard Time":             "America/New_York",
    "Haiti Standard Time":               "America/Port-au-Prince",
    "Cuba Standard Time":                "America/Havana",
    "US Eastern Standard Time":          "America/Indianapolis",
    "Turks And Caicos Standard Time":    "America/Grand_Turk",
    "Paraguay Standard Time":            "America/Asuncion",
    "Atlantic Standard Time":            "America/Halifax",
    "Venezuela Standard Time":           "America/Caracas",
    "Central Brazilian Standard Time":   "America/Cuiaba",
    "SA Western Standard Time":          "America/La_Paz",
    "Pacific SA Standard Time":          "America/Santiago",
    "Newfoundland Standard Time":        "America/St_Johns",
    "Tocantins Standard Time":           "America/Araguaina",
    "E. South America Standard Time":    "America/Sao_Paulo",
    "SA Eastern Standard Time":          "America/Cayenne",
    "Argentina Standard Time":           "America/Buenos_Aires",
    "Greenland Standard Time":           "America/Godthab",
    "Montevideo Standard Time":          "America/Montevideo",
    "Magallanes Standard Time":          "America/Punta_Arenas",
    "Saint Pierre Standard Time":        "America/Miquelon",
    "Bahia Standard Time":               "America/Bahia",
    "UTC-02":                            "Etc/GMT+2",
    "Azores Standard Time":              "Atlantic/Azores",
    "Cape Verde Standard Time":          "Atlantic/Cape_Verde",
    "UTC":                               "Etc/UTC",
    "GMT Standard Time":                 "Europe/London",
    "Greenwich Standard Time":           "Atlantic/Reykjavik",
    "Sao Tome Standard Time":            "Africa/Sao_Tome",
    "Morocco Standard Time":             "Africa/Casablanca",
    "W. Europe Standard Time":           "Europe/Berlin",
    "Central Europe Standard Time":      "Europe/Budapest",
    "Romance Standard Time":             "Europe/Paris",
    "Central European Standard Time":    "Europe/Warsaw",
    "W. Central Africa Standard Time":   "Africa/Lagos",
    "Jordan Standard Time":              "Asia/Amman",
    "GTB Standard Time":                 "Europe/Bucharest",
    "Middle East Standard Time":         "Asia/Beirut",
    "Egypt Standard Time":               "Africa/Cairo",
    "E. Europe Standard Time":           "Europe/Chisinau",
    "Syria Standard Time":               "Asia/Damascus",
    "West Bank Standard Time":           "Asia/Hebron",
    "South Africa Standard Time":        "Africa/Johannesburg",
    "FLE Standard Time":                 "Europe/Kiev",
    "Israel Standard Time":              "Asia/Jerusalem",
    "South Sudan Standard Time":         "Africa/Juba",
    "Kaliningrad Standard Time":         "Europe/Kaliningrad",
    "Sudan Standard Time":               "Africa/Khartoum",
    "Libya Standard Time":               "Africa/Tripoli",
    "Namibia Standard Time":             "Africa/Windhoek",
    "Arabic Standard Time":              "Asia/Baghdad",
    "Turkey Standard Time":              "Europe/Istanbul",
    "Arab Standard Time":                "Asia/Riyadh",
    "Belarus Standard Time":             "Europe/Minsk",
    "Russian Standard Time":             "Europe/Moscow",
    "E. Africa Standard Time":           "Africa/Nairobi",
    "Iran Standard Time":                "Asia/Tehran",
    "Arabian Standard Time":             "Asia/Dubai",
    "Astrakhan Standard Time":           "Europe/Astrakhan",
    "Azerbaijan Standard Time":          "Asia/Baku",
    "Russia Time Zone 3":                "Europe/Samara",
    "Mauritius Standard Time":           "Indian/Mauritius",
    "Saratov Standard Time":             "Europe/Saratov",
    "Georgian Standard Time":            "Asia/Tbilisi",
    "Volgograd Standard Time":           "Europe/Volgograd",
    "Caucasus Standard Time":            "Asia/Yerevan",
    "Afghanistan Standard Time":         "Asia/Kabul",
    "West Asia Standard Time":           "Asia/Tashkent",
    "Ekaterinburg Standard Time":        "Asia/Yekaterinburg",
    "Pakistan Standard Time":            "Asia/Karachi",
    "Qyzylorda Standard Time":           "Asia/Qyzylorda",
    "India Standard Time":               "Asia/Calcutta",
    "Sri Lanka Standard Time":           "Asia/Colombo",
    "Nepal Standard Time":               "Asia/Katmandu",
    "Central Asia Standard Time":        "Asia/Bishkek",
    "Bangladesh Standard Time":          "Asia/Dhaka",
    "Omsk Standard Time":                "Asia/Omsk",
    "Myanmar Standard Time":             "Asia/Rangoon",
    "SE Asia Standard Time":             "Asia/Bangkok",
    "Altai Standard Time":               "Asia/Barnaul",
    "W. Mongolia Standard Time":         "Asia/Hovd",
    "North Asia Standard Time":          "Asia/Krasnoyarsk",
    "N. Central Asia Standard Time":     "Asia/Novosibirsk",
    "Tomsk Standard Time":               "Asia/Tomsk",
    "China Standard Time":               "Asia/Shanghai",
    "North Asia East Standard Time":     "Asia/Irkutsk",
    "Singapore Standard Time":           "Asia/Singapore",
    "W. Australia Standard Time":        "Australia/Perth",
    "Taipei Standard Time":              "Asia/Taipei",
    "Ulaanbaatar Standard Time":         "Asia/Ulaanbaatar",
    "Aus Central W. Standard Time":      "Australia/Eucla",
    "Transbaikal Standard Time":         "Asia/Chita",
    "Tokyo Standard Time":               "Asia/Tokyo",
    "North Korea Standard Time":         "Asia/Pyongyang",
    "Korea Standard Time":               "Asia/Seoul",
    "Yakutsk Standard Time":             "Asia/Yakutsk",
    "Cen. Australia Standard Time":      "Australia/Adelaide",
    "AUS Central Standard Time":         "Australia/Darwin",
    "E. Australia Standard Time":        "Australia/Brisbane",
    "AUS Eastern Standard Time":         "Australia/Sydney",
    "West Pacific Standard Time":        "Pacific/Port_Moresby",
    "Tasmania Standard Time":            "Australia/Hobart",
    "Vladivostok Standard Time":         "Asia/Vladivostok",
    "Lord Howe Standard Time":           "Australia/Lord_Howe",
    "Bougainville Standard Time":        "Pacific/Bougainville",
    "Russia Time Zone 10":               "Asia/Srednekolymsk",
    "Magadan Standard Time":             "Asia/Magadan",
    "Norfolk Standard Time":             "Pacific/Norfolk",
    "Sakhalin Standard Time":            "Asia/Sakhalin",
    "Central Pacific Standard Time":     "Pacific/Guadalcanal",
    "Russia Time Zone 11":               "Asia/Kamchatka",
    "New Zealand Standard Time":         "Pacific/Auckland",
    "UTC+12":                            "Etc/GMT-12",
    "Fiji Standard Time":                "Pacific/Fiji",
    "Chatham Islands Standard Time":     "Pacific/Chatham",
    "UTC+13":                            "Etc/GMT-13",
    "Tonga Standard Time":               "Pacific/Tongatapu",
    "Samoa Standard Time":               "Pacific/Apia",
    "Line Islands Standard Time":        "Pacific/Kiritimati",
}

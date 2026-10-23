#!/usr/bin/env python3
"""What the user said they were doing, read from the check-in watchers. Read-only.

An answer is context, never a block (ADR-0009). This script reads one day for one host,
prints the answers as JSON in the skeleton's clock notation, and writes nothing. It is not
imported by the skeleton, the timeline or the calendar wrapper, so none of them can come to
depend on it.

Sources, both optional:
  `aw-watcher-ask-away_<host>` (type `afktask`) - one event over the away gap, `data.message`.
  `aw-watcher-ask_<host>`      - point events, `data.success`, the answer under the prompt's title.
"""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

import skill_config
from aw_client import SourceError, fetch_events, get, pick_bucket, unreachable
from context_terms import ContextError, load_clients
from timezone import local_clock, resolve_zone_with_source, utc_bounds

CHECKIN_PREFIX = "aw-watcher-ask-away"
ASK_PREFIX = "aw-watcher-ask"
AFK_PREFIX = "aw-watcher-afk"


# Small, generic, ships no user's words (D11). The user's own exclusions extend it.
PERSONAL_WORDS = ("lunch", "break", "coffee", "tea", "school run", "school pickup", "gym",
                  "commute", "errand", "personal", "nap", "doctor", "dentist", "kids")


def _has_word(text, term):
    """Whole-word, case-insensitive: "launch" is not "lunch"."""
    return re.search(rf"(?<!\w){re.escape(term.strip())}(?!\w)", text, re.IGNORECASE) is not None


def classify(words, terms):
    """One class per answer, in this order (D6: a personal match always wins).

    personal: empty, or a shipped or user-excluded word. Otherwise work, naming the clients
    whose terms appear - one, several (E4), or none ("meeting")."""
    text = (words or "").strip()
    if not text:
        return {"class": "personal", "clients": []}
    personal = list(PERSONAL_WORDS) + list((terms or {}).get("exclusions") or [])
    if any(t.strip() and _has_word(text, t) for t in personal):
        return {"class": "personal", "clients": []}
    clients = [c["client"] for c in (terms or {}).get("clients") or []
               if any(t.strip() and _has_word(text, t) for t in c.get("terms") or [])]
    return {"class": "work", "clients": clients}


def host_of(bucket):
    return bucket.split("_", 1)[1] if bucket and "_" in bucket else None


def pick_for_host(buckets, prefix, host):
    """The bucket for `prefix` on `host`. `aw-watcher-ask` is a prefix of
    `aw-watcher-ask-away`, so the check-in bucket is never offered to the ask reader (D4)."""
    own = {b: v for b, v in buckets.items()
           if b.startswith(prefix) and (prefix != ASK_PREFIX or not b.startswith(CHECKIN_PREFIX))
           and (host is None or host_of(b) in (host, None))}
    return pick_bucket(own, prefix)


def _parse(ts):
    return dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _answer_text(event):
    data = event.get("data") or {}
    if "message" in data:
        return str(data["message"]).strip()
    return " ".join(str(v).strip() for k, v in data.items()
                    if k != "success" and isinstance(v, str)).strip()


def read_answers(events, source, zone, lo, hi):
    out = []
    for ev in events:
        data = ev.get("data") or {}
        if source == "ask" and data.get("success") is False:
            continue
        start = max(_parse(ev["timestamp"]), lo)
        end = min(_parse(ev["timestamp"]) + dt.timedelta(seconds=ev.get("duration") or 0), hi)
        if end < start:
            continue
        out.append({"source": source, "start": local_clock(start, zone),
                    "end": local_clock(end, zone), "words": _answer_text(ev)})
    return sorted(out, key=lambda a: (a["start"], a["source"]))


def _secs(clock, floor=0):
    """Seconds since local midnight of an `HH:MM:SS` reading; a span end that reads at or
    before its start has crossed midnight, which `floor` lifts by a day."""
    h, m, sec = (int(x) for x in clock.rstrip("*").split(":"))
    v = h * 3600 + m * 60 + sec
    return v + 86400 if v < floor else v


def _load(path):
    if not path:
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _span(a):
    start = _secs(a["start"])
    return start, _secs(a["end"], start + 1 if a["end"] != a["start"] else 0)


def _ruling_for(rulings, start, end):
    for r in (rulings or {}).get("checkin_questions") or []:
        if r.get("start") == start and r.get("end") == end:
            return r.get("ruling")
    return None


def place(answers, terms, skeleton, calendar, rulings):
    """Sort each answer into question, hint or context. Never emits a block.

    A check-in answer overlapping a break becomes one question per overlapped break, spanning
    the answer clipped to that break and never more (D7: only check-in answers do); a ruling
    already on file for that span takes it out of `questions`. One that
    overlaps no break, or any ask answer, is a hint. An answer inside a corroborated
    calendar block is context only - the calendar path already asks."""
    breaks = [(_secs(b["start"]), _secs(b["end"], _secs(b["start"]) + 1), b)
              for b in (skeleton or {}).get("breaks") or []]
    events = (calendar or {}).get("events") or []
    questions, hints, ruled = [], [], []
    for a in answers:
        a.update(classify(a["words"], terms))
        a["placement"] = "personal" if a["class"] == "personal" else "hint"
        if a["class"] == "personal":
            continue
        lo, hi = _span(a)
        if any(e.get("corroborated") and e.get("block")
               and _secs(e["block"]["start"]) <= lo and hi <= _secs(e["block"]["end"])
               for e in events):
            a["placement"] = "context"
            continue
        over = []
        for bs, be, b in breaks:
            if a["source"] != "checkin" or min(hi, be) <= max(lo, bs):
                continue
            # Clip the answer to the break: keep the clock text of whichever edge is inner.
            s_sec, s_txt = (lo, a["start"]) if lo >= bs else (bs, b["start"])
            e_sec, e_txt = (hi, a["end"]) if hi <= be else (be, b["end"])
            over.append((s_sec, e_sec, s_txt, e_txt))
        if not over:
            hints.append({k: a[k] for k in ("source", "start", "end", "words", "clients")})
            continue
        a["placement"] = "question"
        for bs, be, start, end in over:  # one question per overlapped break
            verdict = _ruling_for(rulings, start, end)
            if verdict:
                ruled.append({"start": start, "end": end, "ruled": verdict})
                continue
            cite = next(({"subject": e["subject"], "start": e["start"], "end": e["end"]}
                         for e in events if not e.get("corroborated")
                         and min(be, _secs(e["end"], _secs(e["start"]) + 1)) > max(bs, _secs(e["start"]))),
                        None)
            questions.append({"start": start, "end": end, "words": a["words"],
                              "clients": a["clients"], "calendar": cite})
    return questions, hints, ruled


def with_context_clients(terms):
    """`terms` with the clients read from the workspace context file, the one home of the
    terms, unless the caller named some. A context file with no readable clients leaves the
    answers with no client rather than failing the day."""
    terms = dict(terms or {})
    if terms.get("clients"):
        return terms
    root = skill_config.find_workspace() or Path.cwd()
    try:
        clients, _ = load_clients(root)
    except (ContextError, OSError):
        return terms
    terms["clients"] = clients
    return terms


def read_day(date, zone, terms=None, skeleton=None, calendar=None, rulings=None):
    terms = with_context_clients(terms)
    start_utc, end_utc = utc_bounds(date, zone)
    lo, hi = _parse(start_utc), _parse(end_utc)
    off = set((terms or {}).get("off") or [])
    result = {"date": date.isoformat(), "status": "absent", "host": None, "answers": [],
              "questions": [], "hints": [], "ruled": []}
    if {"checkin", "ask"} <= off:
        result["status"] = "off"
        return result
    try:
        buckets = get("/buckets/")
        afk = pick_bucket(buckets, AFK_PREFIX)
        host = host_of(afk)
        result["host"] = host
        checkin = None if "checkin" in off else pick_for_host(buckets, CHECKIN_PREFIX, host)
        ask = None if "ask" in off else pick_for_host(buckets, ASK_PREFIX, host)
        answers = (read_answers(fetch_events(checkin, start_utc, end_utc), "checkin", zone, lo, hi)
                   + read_answers(fetch_events(ask, start_utc, end_utc), "ask", zone, lo, hi))
    except Exception as exc:
        raise SourceError(unreachable(exc)) from None
    if checkin or ask:
        result["status"] = "ok" if answers else "empty"
    result["questions"], result["hints"], result["ruled"] = place(
        answers, terms, skeleton, calendar, rulings)
    result["answers"] = answers
    return result


def probe(which):
    """Setup's check: is this host's watcher bucket there, and when did it last write?
    Reads only. The newest event is the one a person can be told about."""
    prefix = CHECKIN_PREFIX if which == "checkin" else ASK_PREFIX
    try:
        buckets = get("/buckets/")
        bucket = pick_for_host(buckets, prefix, host_of(pick_bucket(buckets, AFK_PREFIX)))
        events = get(f"/buckets/{bucket}/events?limit=1") if bucket else []
    except Exception as exc:
        raise SourceError(unreachable(exc)) from None
    return {"watcher": which, "found": bucket is not None, "bucket": bucket,
            "newest_event": events[0]["timestamp"] if events else None}


def diagnose():
    """The condition that makes the check-in watcher refuse to start: more than one AFK
    bucket (its `find_afk_bucket` matches every bucket with `afk` in its name). Names the
    buckets and the stale one by `last_updated`; deletes and posts nothing (US-4/AC-4).
    The watcher has no host or bucket option (H3), so the only fix is to remove the stale
    bucket - after an export, and only on the user's yes naming it."""
    try:
        buckets = get("/buckets/")
    except Exception as exc:
        raise SourceError(unreachable(exc)) from None
    afk = sorted(b for b in buckets if "afk" in b)
    result = {"clean": len(afk) <= 1, "condition": None, "buckets": afk, "stale": None, "fixes": []}
    if len(afk) > 1:
        stale = min(afk, key=lambda b: buckets[b].get("last_updated") or "")
        result.update(condition="two-afk-buckets", stale=stale, fixes=[
            f"Export {stale} from the ActivityWatch web page (Raw data, Export) and save the file.",
            f"After the export is saved, and only if you say yes to {stale} by name, delete that bucket.",
        ])
    return result


def main():
    ap = argparse.ArgumentParser(description="Read one day's check-in answers (read-only).")
    ap.add_argument("date", nargs="?", help="YYYY-MM-DD (local date)")
    ap.add_argument("--utc-offset", type=float, default=None)
    ap.add_argument("--probe", choices=("checkin", "ask"),
                    help="setup: is this host's watcher bucket there, and its newest event")
    ap.add_argument("--diagnose", action="store_true",
                    help="setup: name the two-AFK-bucket condition that stops the check-in watcher")
    ap.add_argument("--terms", help="JSON: {exclusions: [..], off: [checkin|ask]}. Clients "
                                    "are read from the workspace context file")
    ap.add_argument("--skeleton", help="the day's `afk_blocks.py --json` output (breaks)")
    ap.add_argument("--calendar", help="the day's `calendar_day.py` output")
    ap.add_argument("--rulings", help="Timesheets/<date>_harvest_responses.json")
    args = ap.parse_args()
    if args.probe or args.diagnose:
        try:
            print(json.dumps(probe(args.probe) if args.probe else diagnose(), indent=2))
        except SourceError as e:
            print(f"ERR {e}", file=sys.stderr)
            return 1
        return 0
    if not args.date:
        print("ERR a date (YYYY-MM-DD) is required unless --probe or --diagnose is given",
              file=sys.stderr)
        return 2
    try:
        date = dt.datetime.strptime(args.date, "%Y-%m-%d").date()
    except ValueError:
        print(f"ERR bad date '{args.date}', expected YYYY-MM-DD", file=sys.stderr)
        return 2
    zone, _ = resolve_zone_with_source(args.utc_offset)
    try:
        inputs = [_load(p) for p in (args.terms, args.skeleton, args.calendar, args.rulings)]
    except (OSError, ValueError) as e:
        print(f"ERR cannot read an input file: {e}", file=sys.stderr)
        return 2
    try:
        result = read_day(date, zone, *inputs)
    except SourceError as e:
        print(f"ERR {e}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

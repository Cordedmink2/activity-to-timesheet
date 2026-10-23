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
import sys

from aw_client import SourceError, fetch_events, get, pick_bucket, unreachable
from timezone import local_clock, resolve_zone_with_source, utc_bounds

CHECKIN_PREFIX = "aw-watcher-ask-away"
ASK_PREFIX = "aw-watcher-ask"
AFK_PREFIX = "aw-watcher-afk"


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


def read_day(date, zone):
    start_utc, end_utc = utc_bounds(date, zone)
    lo, hi = _parse(start_utc), _parse(end_utc)
    result = {"date": date.isoformat(), "status": "absent", "host": None,
              "answers": [], "questions": [], "hints": []}
    try:
        buckets = get("/buckets/")
        afk = pick_bucket(buckets, AFK_PREFIX)
        host = host_of(afk)
        result["host"] = host
        checkin = pick_for_host(buckets, CHECKIN_PREFIX, host)
        ask = pick_for_host(buckets, ASK_PREFIX, host)
        answers = (read_answers(fetch_events(checkin, start_utc, end_utc), "checkin", zone, lo, hi)
                   + read_answers(fetch_events(ask, start_utc, end_utc), "ask", zone, lo, hi))
    except Exception as exc:
        raise SourceError(unreachable(exc)) from None
    if checkin or ask:
        result["status"] = "ok" if answers else "empty"
    result["answers"] = answers
    return result


def main():
    ap = argparse.ArgumentParser(description="Read one day's check-in answers (read-only).")
    ap.add_argument("date", help="YYYY-MM-DD (local date)")
    ap.add_argument("--utc-offset", type=float, default=None)
    args = ap.parse_args()
    try:
        date = dt.datetime.strptime(args.date, "%Y-%m-%d").date()
    except ValueError:
        print(f"ERR bad date '{args.date}', expected YYYY-MM-DD", file=sys.stderr)
        return 2
    zone, _ = resolve_zone_with_source(args.utc_offset)
    try:
        result = read_day(date, zone)
    except SourceError as e:
        print(f"ERR {e}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

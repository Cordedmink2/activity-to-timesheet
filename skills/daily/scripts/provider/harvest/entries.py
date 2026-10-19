"""Time entries: the adapter's `check_*`, `post`, `patch` and `list_entries` (§ 6.2).

The contract's body (`project_id`, `task_id`, `date`, `start`, `end`, `notes`) is mapped
here onto what Harvest stores. **An entry is always sent as a fixed interval** - a start and
an end, never a running timer and never a bare duration - which is a promise the contract
makes for every account mode and this adapter keeps.

The two checks are **read-only** and run on the preview and the confirmed run alike
(§ 2). `post` and `patch` carry no gate of their own: the dispatcher calls them only on a
confirmed run, so an adapter never sees an unconfirmed write.
"""
from __future__ import annotations

import datetime as dt

import timezone
from provider.errors import ProviderError, Refused, with_context
from provider.harvest import client, guards

TO_WIRE = {"project_id": "project_id", "task_id": "task_id", "date": "spent_date",
           "start": "started_time", "end": "ended_time", "notes": "notes"}


def _wire(fields: dict) -> dict:
    return {TO_WIRE[k]: v for k, v in fields.items()}


def _numeric(body: dict) -> dict:
    """The ids Harvest wants as integers. A *code* where an identifier belongs is refused
    with a message pointing at `lookup`, because it would otherwise reach Harvest as a 422."""
    out = dict(body)
    for key in ("project_id", "task_id"):
        if key in out:
            try:
                out[key] = int(out[key])
            except ValueError:
                raise Refused(
                    f"{key} must be an identifier `lookup` printed, got {out[key]!r}. A "
                    "project *code* like 'ACM-CR202' is not an id - run `lookup` to "
                    "resolve it.") from None
    return out


def _zone():
    # No offset flag is offered: the contract has none. See `timezone.resolve_zone`.
    return timezone.resolve_zone(None, offers_offset_flag=False)


def check_post(body: dict) -> None:
    """Refuse an entry Harvest would bill wrongly: one worked straight through the autumn
    daylight-saving change. Last of the checks and the only one that reads configuration,
    so a plain typo is answered as a typo, not as a missing setting."""
    _numeric(body)
    spent = dt.date.fromisoformat(body["date"])
    refusal = guards.refusal_for_a_straddled_change(
        spent, client.parse_time_to_minutes(body["start"]),
        client.parse_time_to_minutes(body["end"]), _zone())
    if refusal:
        raise Refused(refusal)


def check_patch(entry_id: str, fields: dict) -> None:
    """Refuse a patch whose *result* runs straight through the change.

    A patch carries only what it changes, so `start` alone, `end` alone and `date` alone are
    each a whole straddling entry once laid over the one already there; reading the rest
    costs a GET, which is not paid for where nothing in the fields could move a clock or
    where a `date` names a day with no repeated span. That read happens on the preview too:
    what must not be applied must not be offered.
    """
    _numeric(fields)
    if not {"start", "end", "date"} & fields.keys():
        return
    zone = _zone()
    if "date" in fields and timezone.repeated_span(
            dt.date.fromisoformat(fields["date"]), zone) is None:
        return
    keys = ("date", "start", "end")
    result = {k: fields[k] for k in keys if k in fields}
    if len(result) < len(keys):
        held = client.request("GET", f"/time_entries/{entry_id}")
        wire = {"date": held.get("spent_date"), "start": held.get("started_time"),
                "end": held.get("ended_time")}
        result = {**wire, **result}
    if not all(result.get(k) for k in keys):
        return          # a duration-mode entry holds no interval; refuse only what is read
    try:
        spent = dt.date.fromisoformat(result["date"])
        start_min = client.parse_time_to_minutes(result["start"])
        end_min = client.parse_time_to_minutes(result["end"])
    except ValueError:
        return          # a shape Harvest accepted and this adapter did not put there
    refusal = guards.refusal_for_a_straddled_change(spent, start_min, end_min, zone)
    if refusal:
        raise Refused(refusal)


def post(body: dict) -> str:
    resp = client.request("POST", "/time_entries", body=_wire(_numeric(body)))
    return str(resp["id"])


def patch(entry_id: str, fields: dict) -> str:
    resp = client.request("PATCH", f"/time_entries/{entry_id}", body=_wire(_numeric(fields)))
    return str(resp.get("id", entry_id))


def _to_24h(t: str | None) -> str | None:
    """Harvest's '8:15am' / '08:15' as 'HH:MM', or None when it holds no clock time."""
    if not t:
        return None
    try:
        minutes = client.parse_time_to_minutes(t)
    except ValueError:
        return t
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def list_entries(date_from: str, date_to: str) -> list[dict]:
    """The caller's own entries over the range, every page. Any page that fails stops the
    run with that failure's class and returns no partial list: a half-paged month would read
    as a month with gaps."""
    try:
        user_id = client.request("GET", "/users/me")["id"]
    except ProviderError as e:
        raise with_context(e, "reading the user") from None
    raw: list[dict] = []
    page = 1
    while True:
        try:
            resp = client.request("GET", "/time_entries", query={
                "user_id": user_id, "from": date_from, "to": date_to,
                "per_page": 100, "page": page})
        except ProviderError as e:
            raise with_context(e, f"reading entries, page {page}") from None
        raw.extend(resp.get("time_entries", []))
        if not resp.get("next_page"):
            break
        page += 1
    return [{
        "id": e.get("id"),
        "date": e.get("spent_date"),
        "start": _to_24h(e.get("started_time")),
        "end": _to_24h(e.get("ended_time")),
        "hours": e.get("hours") or 0.0,
        "project_code": (e.get("project") or {}).get("code"),
        "task_name": (e.get("task") or {}).get("name"),
        "notes": e.get("notes") or "",
    } for e in raw]

"""The project/task catalog: `refresh` writes it, `lookup` reads it (the adapter's, § 6.2).

The catalog's on-disk file names, page files and format are this adapter's; no caller reads
them. `lookup` and `refresh` of the same adapter agree on them here, and `catalog_age()` is
how a caller learns how stale it is without reading the storage (§ 3.5).

  lookup(query, task, catalog_dir, cache_only, days) -> list[match]
  refresh(wait_for, attempts, delay) -> int
  catalog_age() -> float | None

**A failed refresh leaves the existing catalog exactly as it was.** Every page is fetched
into memory before the catalog is touched, and the new pages are staged under temporary
names before the old are removed.

The assignments endpoint only returns *active* assignments, so a project whose assignment
was archived disappears from the catalog while it still has entries against it. The history
fallback recovers its identifiers from the user's own recent entries.
"""
from __future__ import annotations

import datetime as dt
import glob
import json
import os
import sys
import time
from pathlib import Path

import skill_config
from provider.errors import Misconfigured, NoMatch, ProviderError, Refused
from provider.harvest import client

PAGE_GLOB = "harvest_assignments*.json"
RANK = {"code": 0, "code/name": 1, "client": 2}


def catalog_dir(explicit: str | None = None) -> Path:
    """Where the catalog lives: the flag, else the workspace's `.mcp/`.

    Resolved through `skill_config.find_workspace()`, the same resolver the writer uses,
    so a refresh cannot write into one directory while a lookup reads another. Unresolved
    is `Misconfigured`: writing to a guessed path would report success while the reader kept
    seeing stale data.
    """
    if skill_config.has_value(explicit):
        return Path(explicit)
    workspace = skill_config.find_workspace()
    if workspace is None:
        raise Misconfigured(
            "missing configuration: TIMESHEET_WORKSPACE\n"
            "  Can't locate your timesheet workspace (the directory holding .mcp/ and "
            "Timesheets/). Run this from that directory, or set TIMESHEET_WORKSPACE.\n"
            "  Set it with:  /plugin configure billables"
            + skill_config.note_for_an_unreached_shell())
    return workspace / ".mcp"


def _pages(directory: Path) -> list[str]:
    return sorted(glob.glob(os.path.join(directory, PAGE_GLOB)))


def _assignments(directory: Path):
    """Each project assignment across every page, de-duplicated by project."""
    seen = set()
    for page in _pages(directory):
        try:
            with open(page, encoding="utf-8") as fh:
                doc = json.load(fh)
        except Exception:
            continue
        rows = doc if isinstance(doc, list) else doc.get("project_assignments",
                                                          doc.get("assignments", []))
        for pa in rows:
            pid = (pa.get("project") or {}).get("id")
            if pid in seen:
                continue
            seen.add(pid)
            yield pa


def match_kind(q: str, code: str, name: str, client_name: str) -> str | None:
    """How a project matched the query, or None. A client's name counts: the live delivery
    project is often named for the work and carries the client only on its client, so a
    code/name-only search misses it and can leave a stale shell project as the sole hit."""
    if code.lower() == q:
        return "code"
    if q in code.lower() or q in name.lower():
        return "code/name"
    if q in (client_name or "").lower():
        return "client"
    return None


def from_catalog(query: str, directory: Path, task_filter: str | None) -> list[dict]:
    q = query.lower()
    matches = []
    for pa in _assignments(directory):
        p = pa.get("project") or {}
        code, name = p.get("code") or "", p.get("name") or ""
        client_name = (pa.get("client") or {}).get("name") or ""
        kind = match_kind(q, code, name, client_name)
        if kind is None:
            continue
        tasks = []
        for ta in pa.get("task_assignments", []):
            t = ta.get("task") or {}
            tname = t.get("name") or ""
            if task_filter and task_filter.lower() not in tname.lower():
                continue
            tasks.append({"id": t.get("id"), "name": tname, "billable": bool(ta.get("billable"))})
        matches.append({"code": code, "project_id": p.get("id"), "name": name,
                        "client": client_name, "matched_on": kind, "source": "catalog",
                        "tasks": tasks})
    return sorted(matches, key=lambda m: (RANK[m["matched_on"]], m["code"]))


def from_history(query: str, days: int, task_filter: str | None) -> list[dict]:
    """The user's own recent entries, for a project the catalog misses. Only this path
    needs credentials. Scoped to the caller: unscoped, an admin-scope token paginates the
    whole company's entries and can surface a project/task pair the user has no assignment
    to, which then fails or mis-bills at post time."""
    q = query.lower()
    since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    user_id = client.request("GET", "/users/me")["id"]
    projects: dict = {}
    page = 1
    while True:
        payload = client.request("GET", "/time_entries", query={
            "user_id": user_id, "from": since, "per_page": 100, "page": page})
        for e in payload.get("time_entries", []):
            p = e.get("project") or {}
            code, name = p.get("code") or "", p.get("name") or ""
            client_name = (e.get("client") or {}).get("name") or ""
            kind = match_kind(q, code, name, client_name)
            if kind is None:
                continue
            t = e.get("task") or {}
            tname = t.get("name") or ""
            if task_filter and task_filter.lower() not in tname.lower():
                continue
            proj = projects.setdefault(p.get("id"), {
                "code": code, "project_id": p.get("id"), "name": name, "client": client_name,
                "matched_on": kind, "tasks": {}})
            # Entries arrive newest-first; keep the most recent billable flag per task.
            proj["tasks"].setdefault(t.get("id"), {"id": t.get("id"), "name": tname,
                                                   "billable": bool(e.get("billable"))})
        if not payload.get("next_page"):
            break
        page += 1
    found = [{**m, "tasks": list(m["tasks"].values()), "source": "history"}
             for m in projects.values()]
    return sorted(found, key=lambda m: (RANK[m["matched_on"]], m["code"]))


def lookup(query, task, catalog_directory, cache_only, days) -> list[dict]:
    """Catalog first, every page; the history fallback only when the catalog has no match.

    A read that could not finish is never reported as "no such project" (ADR-0007): a
    failed fallback is said on stderr and then re-raised, so the verdict is the failure's
    class (3, 4 or 5) and never exit 6.
    """
    try:
        directory: Path | None = catalog_dir(catalog_directory)
    except Misconfigured:
        if cache_only:
            raise
        directory = None            # the fallback can still answer; say so
        print("WARN no workspace to read the catalog from; asking the provider's recent "
              "entries instead", file=sys.stderr)
    if directory is not None and not _pages(directory):
        print(f"WARN no catalog in {directory}; run `refresh`", file=sys.stderr)
        if cache_only:
            raise Misconfigured(f"no catalog in {directory} and --cache-only was given; "
                                "run `refresh` first")
    matches = from_catalog(query, directory, task) if directory is not None else []
    if matches or cache_only:
        return matches
    try:
        return from_history(query, days, task)
    except ProviderError as e:
        print(f"WARN history fallback failed: {str(e).splitlines()[0]}", file=sys.stderr)
        raise


def _fetch_all(progress: list[str]) -> list[dict]:
    """Every page of the user's project assignments, into memory. Any failure raises with
    nothing written.

    Progress is appended to `progress` and printed by the caller only once the refresh has
    succeeded: the contract says every failure starts `ERR ` on the *first* stderr line, so a
    line per page printed as it went would put the progress in front of the error.
    """
    pages: list[dict] = []
    page = 1
    while True:
        try:
            payload = client.request("GET", "/users/me/project_assignments",
                                     query={"per_page": 100, "page": page})
        except ProviderError as e:
            raise type(e)(f"{str(e).splitlines()[0]} (reading page {page}; "
                          "existing catalog left untouched)") from None
        progress.append(f"  page {page}: {len(payload.get('project_assignments', []))} "
                        "project assignments")
        pages.append(payload)
        if not payload.get("next_page"):
            return pages
        page += 1


def _count(pages: list[dict]) -> int:
    return sum(len(p.get("project_assignments", [])) for p in pages)


def _write(pages: list[dict], directory: Path) -> None:
    """Stage every page under a temporary name BEFORE removing anything. Deleting first
    meant a failed write - disk full, a sync client holding the folder - left no catalog at
    all, and every later lookup fell through to the history fallback unannounced."""
    directory.mkdir(parents=True, exist_ok=True)
    staged: list[tuple[Path, Path]] = []
    try:
        for i, payload in enumerate(pages, start=1):
            name = "harvest_assignments.json" if i == 1 else f"harvest_assignments_p{i}.json"
            tmp = directory / (name + ".new")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            staged.append((tmp, directory / name))
    except OSError:
        for tmp, _ in staged:
            tmp.unlink(missing_ok=True)
        raise
    # Stale page files from a prior, longer run would be read as current data. The `.new`
    # staging files do not match the page glob.
    for old in directory.glob(PAGE_GLOB):
        old.unlink()
    for tmp, final in staged:
        tmp.replace(final)


def _has_code(pages: list[dict], code: str) -> bool:
    return any(((pa.get("project") or {}).get("code") or "") == code
               for page in pages for pa in page.get("project_assignments", []))


def refresh(wait_for=None, attempts=20, delay=15) -> int:
    """Re-read the user's assignments, every page, and rewrite the catalog; returns the
    number of projects written.

    `wait_for` is the eventually-consistent case: a just-created project can take minutes to
    surface, each attempt is an independent read (replica selection varies), and so a single
    refresh and a row count are not reliable for it. On success it writes the catalog it
    found; if the code never appears, `NoMatch` (exit 6).
    """
    directory = catalog_dir()
    progress: list[str] = []
    pages = _fetch_all(progress)
    if wait_for is not None:
        for attempt in range(1, attempts + 1):
            if _has_code(pages, wait_for):
                break
            if attempt == attempts:
                raise NoMatch(f"{wait_for} did not appear after {attempts} attempts")
            time.sleep(delay)
            progress.clear()
            pages = _fetch_all(progress)
    n = _count(pages)
    if n == 0:
        # Written empty it would make every later lookup fall through to the history
        # fallback unannounced.
        raise Refused("the provider returned no projects at all, so the catalog was not "
                      "rewritten (existing catalog left untouched)")
    _write(pages, directory)
    for line in progress:
        print(line, file=sys.stderr)
    return n


def catalog_age() -> float | None:
    """Whole days since the catalog was last written (a float; the caller rounds down), or
    None when there is none. Reads no provider and needs no credential."""
    pages = _pages(catalog_dir())
    if not pages:
        return None
    newest = max(os.path.getmtime(p) for p in pages)
    return max(0.0, (time.time() - newest) / 86400)

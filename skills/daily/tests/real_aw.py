"""The real ActivityWatch server, standing in for the fake one when `--real-aw` is passed.

The fake in `support.aw_server` is this suite's model of ActivityWatch: bucket listing, the
event range read, the settings key store and the one query shape the scripts send. A model
is only as good as the last time someone checked it against the thing it models, and a
script that agrees with a wrong fake passes every test while failing on a user's machine.
This module is that check, made repeatable: the same tests, the same `Day`s, served by the
genuine `aw-server` binary instead.

    python -m pytest skills/daily/tests --real-aw=/path/to/aw-server

or set `BILLABLES_AW_SERVER` to the binary and pass `--real-aw` bare. Without the flag
nothing here runs and the suite is exactly what it was.

## How a test reaches it

`live_aw` in `conftest.py` asks `serve()` here for a server instead of building the fake.
One `aw-server` process serves the whole session, on a free loopback port, writing a
database in a temporary directory that is deleted afterwards — never the user's own
ActivityWatch data directory, which `--dbpath` keeps it away from. Each test starts from an
empty server: every bucket and every settings key left by the previous test is deleted
first, then the test's `Day` is loaded through the same REST endpoints a watcher uses.

The scripts do not talk to the binary directly. A `FakeServer` sits in front of it as a
recording proxy, forwarding each request and handing back the real status and body, so the
`.requests` / `.sent()` assertions written against the fake keep working unchanged and
still describe what the script actually sent.

## What stays on the fake

A test that asks the fake to *misbehave* — a settings endpoint that is absent
(`settings_status`), a write that is refused (`write_status`), a query endpoint that errors
(`query_status`) — or that pins a bucket's `last_updated`, describes a server this binary is
not. Those keep the fake, and `serve()` says so by returning `None`. That is a property of
the test, not a gap in the check: there is no real build of 0.14 to point those tests at.

## Safety

The binary is started with `--dbpath` into a fresh temporary directory and `--port` on a
port picked by the OS, and is bound to `127.0.0.1`. It cannot read or write the
ActivityWatch the developer has running on 5600, and nothing in this module knows that
port exists.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from support import NO_BODY, FakeServer

ENV_BINARY = "BILLABLES_AW_SERVER"

# Arguments a test passes to make the fake misbehave or report a fixed freshness. The real
# server cannot be asked to do either, so a test passing one keeps the fake.
FAKE_ONLY = frozenset({"settings_status", "write_status", "query_status", "last_updated"})

# The bucket type each watcher declares, by bucket-id prefix. The server stores whatever it
# is told; the scripts select buckets by id, so the type matters only for fidelity.
BUCKET_TYPES = (
    ("aw-watcher-afk", "afkstatus"),
    ("aw-watcher-window", "currentwindow"),
    ("aw-watcher-web", "web.tab.current"),
)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class RealServer:
    """One `aw-server` process for the session, reset to empty between tests."""

    def __init__(self, binary: str):
        self.binary = binary
        self.port = _free_port()
        self.dir = Path(tempfile.mkdtemp(prefix="billables-real-aw-"))
        self.log = open(self.dir / "aw-server.log", "wb")
        self.proc = subprocess.Popen(
            [binary, "--host", "127.0.0.1", "--port", str(self.port),
             "--dbpath", str(self.dir / "test.db"), "--no-legacy-import",
             "--device-id", "billables-test-suite"],
            stdout=self.log, stderr=subprocess.STDOUT)
        self.base = f"http://127.0.0.1:{self.port}"
        deadline = time.monotonic() + 20
        while True:
            try:
                self.version = self._ok("GET", "/api/0/info")["version"]
                break
            except (urllib.error.URLError, ConnectionError, OSError):
                if self.proc.poll() is not None or time.monotonic() > deadline:
                    self.close()
                    raise RuntimeError(
                        f"{binary} did not start; see {self.dir / 'aw-server.log'}") from None
                time.sleep(0.02)

    # -- raw access ---------------------------------------------------------------------

    def request(self, method: str, path: str, body: object = None) -> tuple[int, object]:
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw, status = r.read(), r.status
        except urllib.error.HTTPError as e:
            raw, status = e.read(), e.code
            e.close()
        return status, (json.loads(raw) if raw.strip() else NO_BODY)

    def _ok(self, method: str, path: str, body: object = None) -> Any:
        status, payload = self.request(method, path, body)
        if status >= 400:
            raise RuntimeError(f"real aw-server refused {method} {path}: {status} {payload}")
        return None if payload is NO_BODY else payload

    # -- per-test state -------------------------------------------------------------------

    def reset(self) -> None:
        """Delete every bucket and every settings key the previous test left."""
        for bid in self._ok("GET", "/api/0/buckets/") or {}:
            self._ok("DELETE", f"/api/0/buckets/{urllib.parse.quote(bid, safe='')}?force=1")
        for key in self._ok("GET", "/api/0/settings/") or {}:
            self._ok("DELETE", f"/api/0/settings/{urllib.parse.quote(key, safe='')}")

    def load(self, buckets: dict[str, list[dict]], settings: dict | None) -> None:
        """Load a day the way the watchers and the web UI would have written it."""
        for bid, events in buckets.items():
            kind = next((t for prefix, t in BUCKET_TYPES if bid.startswith(prefix)), "unknown")
            host = bid.rsplit("_", 1)[1] if "_" in bid else "unknown"
            self._ok("POST", f"/api/0/buckets/{urllib.parse.quote(bid, safe='')}",
                     {"id": bid, "client": "billables-test-suite", "type": kind,
                      "hostname": host})
            if events:
                self._ok("POST", f"/api/0/buckets/{urllib.parse.quote(bid, safe='')}/events",
                         [{"timestamp": e["timestamp"], "duration": e["duration"],
                           "data": e["data"]} for e in events])
        for key, value in (settings or {}).items():
            self._ok("POST", f"/api/0/settings/{urllib.parse.quote(key, safe='')}", value)

    def proxy(self) -> FakeServer:
        """A recording proxy in front of the real server, shaped like the fake."""
        def handler(method, path, query, body):
            qs = urllib.parse.urlencode(query)
            return self.request(method, path + (f"?{qs}" if qs else ""), body)
        return FakeServer(handler)

    def close(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        self.log.close()
        shutil.rmtree(self.dir, ignore_errors=True)


def resolve_binary(flag: str | None) -> str:
    """The binary `--real-aw` names, or `BILLABLES_AW_SERVER` when the flag is bare."""
    path = flag if flag and flag != "env" else os.environ.get(ENV_BINARY, "")
    if not path:
        raise RuntimeError(f"--real-aw needs a path to aw-server, or {ENV_BINARY} set to one")
    found = shutil.which(path) or (path if Path(path).is_file() else None)
    if not found:
        raise RuntimeError(f"--real-aw: no aw-server binary at {path!r}")
    return found

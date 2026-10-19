"""Harvest's HTTP client, behind the provider contract (§ 6.2: all of this is the adapter's).

  load_creds() -> (account_id, api_key)       raises `Misconfigured` (exit 3)
  request(method, path, body=None, query=None) -> parsed JSON
                                              raises `Refused` (4) or `Unreachable` (5)
  parse_time_to_minutes(t) -> int

Credentials are read here and nowhere else: through `provider_config.require()`, the one
config helper, so they carry `skill_config`'s precedence and a missing one is the contract's
exit-3 message, naming the variables and never a value.

Telling 4 from 5 is the adapter's job (§ 4): an HTTP response of any status, including
Harvest's own 5xx, is *a response* and so a refusal; a failure to get one - DNS, a refused
connection, a timeout - is unreachable. The exit numbers are the contract's; this mapping is
not.

No third-party deps: stdlib `urllib`.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from provider import provider_config
from provider.errors import Refused, Unreachable

API_BASE = "https://api.harvestapp.com/v2"
USER_AGENT = "billables-daily-skill"

CREDENTIALS = ("HARVEST_ACCOUNT_ID", "HARVEST_API_KEY")

# Plugin route first: it is the one that does not leave a token in the skill folder. The
# values arrive through a SessionStart hook, so a user who fills the dialog and keeps typing
# in the same session sees this message and reasonably concludes the dialog did not work -
# hence the "already configured?" line. `provider_config` appends the rest.
SETUP = (
    "  fill in HARVEST_ACCOUNT_ID and HARVEST_API_KEY - get both from\n"
    "  https://id.getharvest.com/developers.\n"
    "  Already configured them? Start a new session: the values are published at\n"
    "  session start. If a new session still shows this, see references/first-run.md\n"
    "  \u00a7 'When the configuration does not arrive'.")

_CREDS_CACHE: tuple[str, str] | None = None


def parse_time_to_minutes(t: str) -> int:
    """Parse a Harvest-style time string ('8:15am', '08:15', '12:30pm') to minutes-since-midnight.

    Harvest answers in 12-hour spellings and the guards read what it holds, so this stays
    lenient however strict the contract is. Raises ValueError on unparseable or
    out-of-range input.
    """
    raw = t.strip().lower()
    suffix = ""
    if raw.endswith("am") or raw.endswith("pm"):
        suffix = raw[-2:]
        raw = raw[:-2].strip()
    try:
        h_str, m_str = raw.split(":")
        h, m = int(h_str), int(m_str)
    except (ValueError, IndexError):
        raise ValueError(f"cannot parse time: {t!r}")
    if suffix == "pm" and h != 12:
        h += 12
    if suffix == "am" and h == 12:
        h = 0
    if not (0 <= h < 24 and 0 <= m < 60):
        raise ValueError(f"time out of range: {t!r}")
    return h * 60 + m


def load_creds() -> tuple[str, str]:
    """The Harvest account id and token.

    Cached for the process: a listing makes one call per page, and re-resolving per request
    would make the credentials mutable mid-run, so a half-paged listing could start
    authenticating as a different account.
    """
    global _CREDS_CACHE
    if _CREDS_CACHE is not None:
        return _CREDS_CACHE
    found = provider_config.require(CREDENTIALS, SETUP)
    _CREDS_CACHE = (found["HARVEST_ACCOUNT_ID"], found["HARVEST_API_KEY"])
    return _CREDS_CACHE


def request(method: str, path: str, body=None, query=None):
    acct, key = load_creds()
    url = f"{API_BASE}/{path.lstrip('/')}"
    if query:
        cleaned = {k: v for k, v in query.items() if v is not None}
        if cleaned:
            url = f"{url}?{urllib.parse.urlencode(cleaned)}"

    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method.upper())
    req.add_header("Harvest-Account-Id", acct)
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("User-Agent", USER_AGENT)
    if body is not None:
        req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            text = resp.read().decode("utf-8")
            return json.loads(text) if text else {}
    except urllib.error.HTTPError as e:
        # HTTPError *is* the response: it owns a spooled temp file that stays open until
        # its destructor runs. Closing it here keeps a run of failed calls from leaking a
        # handle apiece - and from raising a ResourceWarning later, from a stack with no
        # relationship to the request that caused it.
        with e:
            body_text = e.read().decode("utf-8", "replace")[:300]
        raise Refused(f"Harvest answered {e.code}\n  {body_text}") from None
    except urllib.error.URLError as e:
        raise Unreachable(f"Harvest did not answer: {e.reason}") from None
    except (TimeoutError, OSError) as e:
        raise Unreachable(f"Harvest did not answer: {e}") from None
    except ValueError as e:
        raise Refused(f"Harvest sent something that is not JSON: {e}") from None

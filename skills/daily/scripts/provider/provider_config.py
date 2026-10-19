"""The one config helper adapters read their credentials through (contract § 5).

`require(names)` wraps `skill_config.setting()`, so a credential carries the same precedence
as every other setting (flag, `.env`, environment, default), and a missing one is a
`Misconfigured` (exit 3) whose message names the *variables* and the setup step and never a
value - neither the one that is missing nor one that is present.

Only an adapter calls it. The dispatcher selects an adapter and reads no credential;
`tests/test_provider_boundaries.py` holds that. A key is validated when read, not when
imported, so `--help` and the usage errors work on a machine with nothing configured.
"""
from __future__ import annotations

from typing import Sequence

import skill_config
from provider.errors import Misconfigured


def require(names: Sequence[str], setup: str = "") -> dict[str, str]:
    """Every named setting, or `Misconfigured` listing each one that did not resolve.

    `setup` is the adapter's own wording of how to supply them, appended under the
    contract's `Set it with:` line. The note about a shell the configuration cannot have
    reached is added here, because it is the same cause behind every adapter's absence.
    """
    found = {name: skill_config.setting(name) for name in names}
    missing = [name for name, value in found.items() if not value]
    if missing:
        raise Misconfigured(
            f"missing configuration: {', '.join(missing)}\n"
            f"  Set it with:  /plugin configure billables\n"
            + (setup.rstrip("\n") + "\n" if setup else "")
            + f"  (Exported install instead? Copy {skill_config.SKILL_ROOT / '.env.example'}\n"
            f"   -> {skill_config.ENV_PATH} and put them there.)"
            + skill_config.note_for_an_unreached_shell())
    return {name: value for name, value in found.items() if value}

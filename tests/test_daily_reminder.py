"""The daily run relays the category-stage reminder without growing (guided-setup T13,
US-3/AC-2, US-6/AC-3, D6).

No scheduler and no process: when `--status` says the rules were never written, the daily
run asks `--data-days` and relays its own `say:` line, once. The wording is the script's.
Daily reads the decline-for-good line under `## Preferences`; `--status` supplies whether
managed rules exist, so a `CURRENT`/`UNVERIFIED`/`OVERLAP` answer never reaches the offer.
"""
import re

import shipped
from shipped import SKILLS

DAILY = SKILLS / "daily"
TEXT = shipped.skill_md_text(DAILY)


def stale_bullet() -> str:
    found = re.search(r"^  - \*\*`STALE[^\n]*(?:\n(?!  - |\n)[^\n]*)*", TEXT, re.M)
    assert found, "Step 2 has no STALE bullet"
    return found.group(0)


def test_a_never_written_stale_asks_data_days_before_any_rebuild():
    branch = re.split(r"has not written", stale_bullet(), maxsplit=1)
    assert len(branch) == 2, "the STALE bullet has no never-written branch"
    assert "--data-days" in branch[1] and "--from-context" not in branch[1]
    assert re.search(r"rebuild nothing", branch[1])


def test_the_say_line_is_relayed_once_and_the_wording_is_the_scripts():
    bullet = stale_bullet()
    assert re.search(r"`say:`", bullet)
    assert re.search(r"\bonce\b", bullet)


def test_a_decline_for_good_line_under_preferences_means_no_offer():
    bullet = stale_bullet()
    assert "## Preferences" in bullet and re.search(r"declin|stop offering", bullet, re.I)
    example = (DAILY / "references" / "context.md.example").read_text(encoding="utf-8")
    prefs = example.split("## Preferences", 1)[1]
    assert re.search(r"Category stage reminder", prefs), "the template does not carry the line"


def test_rules_that_exist_are_not_offered_again_because_only_a_never_written_stale_asks():
    bullet = stale_bullet()
    assert re.search(r"never written|has not written|never been written", bullet, re.I)
    assert "CURRENT" not in bullet


def test_a_collecting_answer_rebuilds_nothing_and_writes_no_rule():
    bullet = stale_bullet()
    assert "COLLECTING" in bullet and re.search(r"no rule|nothing is written|do not rebuild|don't rebuild", bullet, re.I)


def test_the_reminder_did_not_make_daily_grow():
    assert len(TEXT.split()) <= 4991

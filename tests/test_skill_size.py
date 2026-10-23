"""Skill size bars (guided-setup T14, US-6/AC-3, issue #57).

The spec's bar: `daily` is no larger after this change than before it, and any NEW skill
stays under the plugin's 5,000-word ceiling. `setup` is not new and was far over the
ceiling at the start base, so it is held to "no larger than it was" rather than to a bar
it never met; this change took it from 9,529 words down.
"""
import pytest

import shipped

CEILING = 5000
# `wc -w skills/*/SKILL.md` at origin/main 50c6d76 (after the check-in answers merged),
# recorded by T1. A skill not listed here is new and is held to the ceiling.
AT_START_BASE = {"daily": 4991, "reconcile": 2661, "setup": 9529}


def words(skill) -> int:
    return len(shipped.skill_md_text(skill).split())


@pytest.mark.parametrize("skill", shipped.skill_dirs(), ids=lambda p: p.name)
def test_no_skill_grew_and_every_new_skill_is_under_the_ceiling(skill):
    if skill.name in AT_START_BASE:
        assert words(skill) <= AT_START_BASE[skill.name], (
            f"{skill.name} grew to {words(skill)} words; it was {AT_START_BASE[skill.name]}")
    else:
        assert words(skill) < CEILING, f"{skill.name} is {words(skill)} words; ceiling {CEILING}"


def test_daily_in_particular_has_not_grown():
    daily = next(s for s in shipped.skill_dirs() if s.name == "daily")
    assert words(daily) <= AT_START_BASE["daily"]

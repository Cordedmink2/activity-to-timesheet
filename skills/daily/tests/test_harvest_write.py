"""The Harvest adapter's guard, driven at the function.

The confirmation gate is no longer in the adapter: it lives once, in the dispatcher
(`test_provider_dispatcher.py`, contract section 2), and an adapter "never sees an
unconfirmed write and carries no gate of its own". What stays here is what Harvest does
with two clock times, which is the adapter's: the daylight-saving refusal and its message.
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from provider.harvest import guards

AUCKLAND = ZoneInfo("Pacific/Auckland")


@pytest.mark.parametrize("minutes,expected", [(0, "00:00"), (90, "01:30"), (255, "04:15"),
                                              (1439, "23:59")])
def test_clock_writes_plain_hh_mm(minutes, expected):
    assert guards.clock(minutes) == expected


@pytest.mark.parametrize("minutes,expected", [(165, "2.75"), (180, "3.0"), (100, "1.67"),
                                              (30, "0.5")])
def test_hours_are_decimal_with_a_trailing_zero_trimmed_to_one(minutes, expected):
    assert guards.hours(minutes) == expected


def test_an_ordinary_day_has_no_refusal():
    assert guards.refusal_for_a_straddled_change(dt.date(2026, 8, 12), 90, 255, AUCKLAND) is None


def test_the_straddling_entry_is_refused_with_both_replacements_named():
    text = guards.refusal_for_a_straddled_change(dt.date(2026, 4, 5), 90, 255, AUCKLAND)
    assert text is not None
    assert text.startswith("01:30-04:15 on 2026-04-05 runs straight through")
    assert "01:30 03:00   (1.5 hrs)" in text and "02:00 04:15   (2.25 hrs)" in text
    assert "2.75 hrs against the 3.75 hrs that really passed" in text


@pytest.mark.parametrize("start,end", [(90, 180), (120, 255)], ids=["first", "second"])
def test_the_refusal_never_refuses_its_own_advice(start, end):
    assert guards.refusal_for_a_straddled_change(dt.date(2026, 4, 5), start, end, AUCKLAND) is None

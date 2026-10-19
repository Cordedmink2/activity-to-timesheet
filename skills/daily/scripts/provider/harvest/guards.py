"""What Harvest does with two clock times, and the refusal that follows (the adapter's, § 6.2).

Harvest stores a start and an end and bills their difference. On the day the clocks go
back, an entry worked straight through the change is short by exactly the span that
happened twice, and nothing raises. `refusal_for_a_straddled_change()` says why such an
entry cannot be billed as one; the adapter's pre-flight checks raise it as `Refused`
(exit 4) before the dispatcher's gate, so an entry that must not be created is never
previewed either.

What the zone did on the date is `timezone.py`'s (`repeated_span()`); what Harvest does
with two clock times is this module's, and the message is the second half.
"""
from __future__ import annotations

from timezone import repeated_span, zone_label


def clock(minutes: int) -> str:
    """Minutes-since-midnight as plain `HH:MM`, so all four times in the refusal are written
    one way and can be compared by eye."""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def hours(minutes: int) -> str:
    """Minutes as the decimal hours Harvest bills them in - 165 -> `2.75`; trailing zeros
    trimmed to one (`3.0`), the shape `references/output-format.md` writes hours in."""
    text = f"{minutes / 60:.2f}".rstrip("0")
    return text + "0" if text.endswith(".") else text


def refusal_for_a_straddled_change(spent, start_min, end_min, zone) -> str | None:
    """Why this entry cannot be billed as one, or None if it can.

    `01:30`-`04:15` in `Pacific/Auckland` on 2026-04-05 bills 2.75 hrs for 3.75 hrs of work.
    A create refuses the entry it was handed, a patch the entry its change would *result*
    in, and the message is the same one.

    That span is an hour in most zones and is never assumed to be: `Australia/Lord_Howe`
    moves thirty minutes and `Antarctica/Troll` two hours, and every figure below is
    measured off the zone's own two readings.

    **It refuses only the entry that is unambiguously wrong**: the clock interval contains
    the repeated span with both ends strictly outside it. The tempting rule - "the clock
    interval and the elapsed time disagree" - refuses the two replacements this message
    recommends, because `01:30`-`03:00` also spans 1.5 clock hours and 2.5 real ones if its
    end is read as the unambiguous `03:00` an hour after the change. An entry *ending* at
    `03:00` or *starting* at `02:00` is one of the two recommendations under one reading and
    an hour short under the other, and this cannot refuse its own advice. Inside the span
    the guard cannot know which pass a bare `02:30` means, and both readings bill correctly
    for their own pass.

    It refuses rather than splitting: two entries out of one approval would put a body on
    the wire the user never previewed, which is what the gate exists to prevent.
    """
    span = repeated_span(spent, zone)
    if span is None:
        return None
    repeat_open, repeat_close = span
    if not (start_min < repeat_open and end_min > repeat_close):
        return None

    first, second = repeat_close - start_min, end_min - repeat_open
    repeated = repeat_close - repeat_open
    return (
        f"{clock(start_min)}-{clock(end_min)} on {spent} runs straight through the "
        f"daylight-saving change in {zone_label(zone)}.\n"
        f"  Harvest bills the difference between the two clock times, so this entry would "
        f"record {hours(end_min - start_min)} hrs against the {hours(first + second)} hrs "
        f"that really passed. Post two entries instead:\n"
        f"      {clock(start_min)} {clock(repeat_close)}   ({hours(first)} hrs)\n"
        f"      {clock(repeat_open)} {clock(end_min)}   ({hours(second)} hrs)\n"
        f"  Those two look like they overlap by {hours(repeated)} hrs and do not — they "
        f"abut. The clocks go back at one instant, and that instant reads "
        f"{clock(repeat_close)} as you reach it and {clock(repeat_open)} once it has "
        f"passed, so the first entry ends and the second begins at the same moment. "
        f"Closing the apparent overlap is what loses the {hours(repeated)} hrs that "
        f"happened twice, which is why this is refused rather than split for you. Say in "
        f"the day's notes that the clocks changed — the overlap is the first thing a "
        f"reviewer will query.")

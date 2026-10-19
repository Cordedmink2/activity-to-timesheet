# Profile names as category terms (#66)

A client's category terms come from two sources, and the matcher does not care which. Both go
through the same gate in `category_rules.py` against the sampled titles before anything is
written.

| Browser | Profile name in the window title? | What setup does |
|---|---|---|
| Edge | Yes, unaided: `<page> - <profile> - Microsoft Edge`, e.g. `… - ClientA - Alex - Microsoft Edge`, `… - Work - Microsoft Edge` | Offers the names `--inspect` prints as `PROFILE` lines. URL in title is an optional upgrade. |
| Chrome | No. Measured: two different profiles, both `New Tab - Google Chrome` | URL in title and its bracketed code stay required. Say why: nothing else tells the profiles apart. No second extension is added. |
| Firefox | Not verified | Say so. Claim nothing. |

## Reading a `PROFILE` line

`PROFILE "ClientA - Alex" — 12 titles in Edge; gate: write, matches 12 of 480 sampled titles`

- The name is whole: a profile can be `Name - Account`. When two segments end more than one
  distinct title they are read as one name; a name seen in a single title is read as its last
  segment alone, which may be only the account. Check it with the user against Local State.
- `gate: refuse` means the name matches too large a share of titles to separate clients. The
  general profile is the usual case. Do not use it as a term; choose another.
- A profile that is general (several clients) must not be used as one client's term, exactly as
  with a bracketed tag.
- `PROFILE none in the sampled titles` is the Chrome-only, or no-Edge, answer.

Not covered here: renaming a profile after rules were written (#99), which makes a term match
nothing without any error.

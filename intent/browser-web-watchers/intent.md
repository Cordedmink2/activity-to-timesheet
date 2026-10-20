# Intent: First-class browser address evidence in Firefox, Chrome and Edge

**Author:** Connor  **Date:** 2026-10-20
**Status:** Accepted — 2026-10-20 (Connor, in conversation with Hermes: "Yeah I think that sounds good")
**Type:** improvement
**Origin:** Connor, alongside the check-in answers intent.
**Appetite:** not set

## As raised
> "Also add the Firefox and chrome web watcher support (edge also supports the chrome extension).
> All this will have to be planned and reviewed carefully."

## Problem
Setup already recommends the ActivityWatch web watcher for Chrome-family browsers and Firefox, and
the daily run reads it, but only when it zooms into an unclear stretch. Everywhere else the run
relies on window titles, which name the page but not its address unless the URL in title extension
is installed. Firefox has no URL in title extension the plugin has been tested with, so Firefox
users' browser work is classified from page words alone and is often unattributable to a client.

## Desired outcome
1. A Firefox user with the web watcher gets browser work attributed to clients as reliably as an
   Edge or Chrome user with URL in title.
2. Edge, Chrome (and the other Chromium browsers the extension already supports) use the web
   watcher's addresses wherever they make attribution better, not only in zoom.
3. Setup installs and verifies the web watcher in each browser the user works in, with clear
   Edge-specific steps (Edge installs from the Chrome Web Store), and says plainly what is and isn't
   supported.
4. A user without the web watcher sees today's behaviour exactly.

## Who it is for
Billables users who do client work in a browser, especially Firefox users. Connor decides behaviour.

## Boundaries
- Addresses are read locally from the user's own activity source only (refusal 3).
- A browser address helps attribute work; it never decides whether the user was working (refusal 5).
- Personal browsing must not become billable because a tab was open.
- No client hosts or names ship in the plugin (refusal 4).
- URL in title stays required where it is today unless the work shows the web watcher fully covers it.

## Autonomy envelope
The implementer may decide alone: how and where web watcher evidence enters classification and
category rules; whether URL in title can become optional for any browser; managed-browser and
allow-list guidance; tests, docs, ADRs and decision-log entries. Priorities: never mis-bill personal
browsing; Firefox parity; least setup burden.

## Reserved decisions
- Dropping URL in title as a requirement for any browser (it changes what users must install).
- Cutting a release (AGENTS.md § Releasing).

## Success check
- On a Firefox profile with the web watcher and no URL in title, a day of client browsing classifies
  to the right clients with no more unattributed browser time than the same day in Edge.
- On Edge, setup's install link and verification both work and the bucket is found.
- Without the web watcher, `daily` output for a recorded test day is unchanged.
- `pytest` and `pyright` are green per AGENTS.md.

## Clarifications
### Session 2026-10-20 (Atlas, delegated)
Connor delegated every decision reserved for him across these five intents to Atlas on 2026-10-20
("Have atlas decide all that. This project needs to be fully finished up now."; card t_3c4f0453).
Foundational refusals and this accepted intent text are not delegated and are unchanged.
- Edge and Chrome share one web watcher bucket (plan Q1) → a browser counts as verified only when
  a recent event is corroborated by its foreground window; otherwise it is reported unproven by
  name. Why: honest evidence over an assumed bucket per browser.
- URL in title stays required for Chromium browsers (Reserved; not changed).
- Release cut → Atlas cuts it once every build gate has merged and `Checks` is green on main;
  the CHANGELOG records that Connor delegated this release on 2026-10-20.

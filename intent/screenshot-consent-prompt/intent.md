# Intent: Ask before each screenshot, so confidential screens aren't captured

**Author:** Connor  **Date:** 2026-10-20
**Status:** Accepted — 2026-10-20 (Connor, in conversation with Hermes: "Yeah I think that sounds good")
**Type:** improvement
**Origin:** Connor. Raised earlier as a feature request in another session (not found in the repo's
issues or session history on 2026-10-20); restated here.
**Appetite:** keep it small: little code, little to maintain, few ways to break.

## As raised
> "Every time a screenshot wants to be taken a little pop-up asks if it's safe to screenshot. I'd
> want this to be a pretty keep-it-simple feature so that it's not a pain to maintain and so it
> doesn't have lots of bugs and lots of code … maybe if we can utilise existing stuff."

## Problem
Many users won't turn screenshots on, or worry about leaving them on, because the capture can
record confidential material such as client data, HR screens or personal messages. Today the only
choice is all or nothing.

## Desired outcome
1. Users who want it get a small prompt before a capture and can say no; a refused capture writes
   nothing at all.
2. Saying yes is quick and doesn't get in the way of work. An ignored prompt **skips** the capture
   (Connor, 2026-10-20): the feature exists for confidentiality.
3. It is opt-in. Users who don't switch it on see today's behaviour exactly.

## Boundaries
- Keep it simple. Prefer existing operating-system or library features over new UI code. No new
  long-running process if one can be avoided.
- A refused capture must leave no image, even temporarily.
- A refused or missing capture is not evidence of being idle (foundational refusal 5); the daily
  run treats it as "no screenshot", as it does today.
- Nothing leaves the machine (refusal 3).

## Autonomy envelope
Researcher and dev may decide: the mechanism (for example a Windows toast or message box from the
existing capture script, or a reused component), timeout length, wording, tests and docs. They may
recommend a lighter alternative that serves the same goal, such as a "pause screenshots for 30
minutes" control or skipping captures when chosen apps are in front. If they recommend replacing
the per-capture prompt, that is an amendment brief for Connor, not a silent swap.

## Reserved decisions
- Cutting a release (AGENTS.md § Releasing).

## Success check
- With the prompt on, answering "no" leaves no file for that capture time; "yes" writes the normal
  capture; an ignored prompt writes no file.
- With the prompt off, captures are unchanged.
- The change adds a small amount of code, and the reviewer judges it maintainable.
- `pytest` and `pyright` green per AGENTS.md.

## Clarifications
### Session 2026-10-20 (Atlas, delegated)
Connor delegated every decision reserved for him across these five intents to Atlas on 2026-10-20
("Have atlas decide all that. This project needs to be fully finished up now."; card t_3c4f0453).
Foundational refusals and this accepted intent text are not delegated and are unchanged.
- Keep the per-capture prompt (no replacement) → yes. Researcher t_9d972ef2 found the lighter
  options (pause control, app-based skip) fail open, which defeats the goal; no amendment brief.
  A pause control may be added later only as an add-on, not a replacement.
- Dialog mechanism → the Windows message box with a timeout (MessageBoxTimeoutW via ctypes,
  default No, about 20 s, fail closed) from the existing Python capture script; fallback
  MessageBoxW in a thread with a join timeout. Zenity is not used: it adds a third-party install
  for no gain, and nothing else on Windows needs it now that aw-watcher-ask is not recommended.
- Release cut → Atlas cuts it once every build gate has merged and `Checks` is green on main;
  the CHANGELOG records that Connor delegated this release on 2026-10-20.

# Plan: Ask before each screenshot, so confidential screens aren't captured

**Spec:** [spec.md](spec.md) (re-gated and merged at 41b5670 via PR #107; this plan is re-pointed to 41b5670)  **Intent:** [intent.md](intent.md) (Accepted 2026-10-20)
**Author:** dev  **Date:** 2026-10-20  **Status:** Draft (plan gate: t_ad5cee76)
**Research:** researcher's comparison, card t_9d972ef2, `/home/ubuntu/artefacts/billables-2026-10-20/consent-prompt-options.md` (cited for US-4/AC-1; it recommends keeping the per-capture prompt, so no amendment brief is needed).

## Approach

One yes/no box, asked by the existing capture script, before anything is grabbed. About 45 production lines, no new process, no new package.

**1. The ask (`screenshot_capture.py`).** `ask_consent(timeout_s=20)` calls `MessageBoxTimeoutW` from `user32` through stdlib `ctypes`. Buttons Yes/No, default button **No**, topmost, no `MB_DEFAULT_DESKTOP_ONLY` (a locked screen must time out, not wait). It returns True only for Yes (6). No (7), timeout (32000), a closed box, a missing export or any exception return False: it fails closed. On a non-Windows machine it returns False.

**2. The gate, with an injectable seam.** One small function holds the whole rule:

    capture_once(dest, ask, consent=ask_consent, grab=take_screenshots)

If `ask` is off it calls `grab(dest)` and nothing else: today's path. If `ask` is on it calls `consent()` first, calls `grab(dest)` only on True, and otherwise writes one log line and returns. Pixels are grabbed only inside `take_screenshots()`, and that call sits after the consent call, so a no or timeout leaves no image anywhere, not even in memory (US-2/AC-1). `consent` and `grab` are parameters, so tests on `windows-latest` and `ubuntu-latest` run with fakes and no person.

**3. The opt-in is a task argument, not a setting: `--ask`.** The scheduled task's command line is today `pythonw "<script>" "<dir>"`. With the prompt on it gains a third argument, `--ask`. Reasons: the task runs outside any session and is documented as never seeing the configured value (setup Step 5), so a `.env` toggle would be the same reader/writer gap that `-ScreenshotsDir` exists to close; the flag is visible in `Get-ScheduledTask ...Actions.Arguments` where setup already reads back; and off means no flag, so the command line is byte-identical to main's (US-3/AC-2). `setup_screenshot_pipeline.ps1` gains one switch, `-AskFirst`, that appends `--ask`; the `--where` handling already shows the pattern for filtering a flag out of the positional list. The session-start hook's repair only rewrites the first argument (`repaired_arguments`), so `--ask` survives a plugin update; a test pins that.

**4. What a skip writes.** One line in `capture.log`, no content: `[YYYY-MM-DD HH:MM:SS] skipped`. The date is in it because the existing log lines carry only a time, and the daily run has to count skips per day. A failure to show the box at all (missing export, ctypes error) writes `[YYYY-MM-DD HH:MM:SS] prompt-error` instead, never `skipped`: otherwise a broken prompt would look like the user declining every capture. Neither line says anything about the screen. Nothing leaves the machine.

**5. How the daily and reconcile runs read it.** The idle decision is untouched: the AFK watcher alone settles idle (foundational refusal 5), and nothing here reads `capture.log` for that. Two reader changes, both for the capture-health line only:

- `afk_blocks.captures(date)` also counts `skipped` lines for that date in `capture.log` and returns `skipped` beside `count` and `last`. A missing log or no lines gives 0, so every day without skips renders byte-identically (the existing goldens pin this).
- `render_text` changes only the `captures:` line. Zero ticks with skips: `captures:    none for this date, N skipped by you  <- not a dead task`. Ticks with skips: the existing line plus `, N skipped by you`. Zero ticks and no skips keeps the existing dead-task wording. The skeleton's breaks, work start and end, active spans and ratios do not change; only the `captures:` line may differ (this is the reading of US-2/AC-2 the plan builds to, see Risks).
- `skills/daily` guidance (the `captures: none` bullet and `references/first-run.md`) and `skills/reconcile/SKILL.md` ("a run of capture-less days is one finding") each get a short rule: before calling capture-less days a dead task, check for `skipped` lines; those days are "captures skipped by you", an informational note, not maintenance. A day that was all skipped has no dated folder (nothing was grabbed, so none is created), so reconcile reads the log, with one `Select-String` command given in the guidance.

**6. Setup (`skills/setup/SKILL.md` Step 5).** One plain sentence offering the prompt ("Ask me before each screenshot: you click Yes or No; no answer means no screenshot. Off by default."), the choice recorded by passing `-AskFirst`, and a verify step per mode: prompt on, run `screenshot_capture.py <dir> --ask` once and answer Yes (files appear), then once and ignore it (none appear, a `skipped` line does); prompt off, the existing step. Plainly says a presenting or screen-sharing audience can see the box (E3), and that the interval must stay above the timeout. Changing it later is re-running setup with or without `-AskFirst` (the existing re-registration note already carries non-default arguments; `--ask` is added to that list).

**7. Interval guard.** With `-AskFirst`, `setup_screenshot_pipeline.ps1` throws if `-IntervalSeconds` is under 60. The box lives 20 s, so with the default 150 s no prompt can overlap the next (E2), and the task's `-MultipleInstances IgnoreNew` is the backstop.

**Size estimate** (production only; tests and docs excluded): `ask_consent` 12, `capture_once` + `__main__` wiring + flag filtering 15, skip/prompt-error log lines 4, `captures()` skip count 8, `render_text` 5, setup script switch + dry-run line + interval guard 8 = about 52. Ceiling: 80 (US-4/AC-3). If the build exceeds 80, stop and justify to the reviewer.

## Research and spike (autonomous-execution prerequisites)

Context: the intent wants a small, low-maintenance prompt that fails closed. The researcher compared five prompt mechanisms and two lighter options from sources (cited above). Evidence is enough to choose; it leaves three unknowns, all about `MessageBoxTimeoutW` being undocumented.

- **H1** On `windows-latest`, `MessageBoxTimeoutW(None, "t", "t", MB_YESNO|MB_DEFBUTTON2, 0, 1)` returns 32000 and closes (control: the same call with a 1 ms timeout and `MB_OK` returns 32000 too; a missing export raises `AttributeError`, which `ask_consent` turns into False). Expected: returns within 2 s. Safe boundary: one throwaway call in a test with a 1 ms timeout; it shows no lasting UI. Exit condition: observed code is not 32000 or the call hangs past 10 s, or the runner has no desktop. Then the smoke test is dropped (unit tests with the fake stay), the real-dialog check is stated as not verified by CI for Atlas's ship decision, and no conclusion is drawn about real machines.
- **H2** The export exists on Windows 10 and 11. Expected: present. Not testable here beyond the runner; the shared Windows end-to-end job asserts the real call on the runner (T8). Exit condition: if the export is missing on the runner, switch to D1's fallback (below) before building further.
- **H3** Focus behaviour (does it take typing focus and swallow keystrokes?) is not testable without a person: stated as not verified by CI for Atlas's ship decision (US-1/AC-3, T8); never marked passed. Default button No makes a stray Enter or Space a skip, which is the safe side.

A written experiment is not execution clearance: the spike is T1 and only runs the 1 ms call in CI.

**Cleanup and maintenance.** Temporary artefacts: the T1 smoke test (kept as a permanent `skipif not win32` test if H1 holds, deleted if not; owner dev, decided in T1's evidence). No services, jobs, scheduled tasks or packages are created; the existing `WorkScreenshots` task only gains `--ask` on opt-in. Maintenance owner: the repo maintainer; the health check is the verify step in setup plus the `prompt-error` line, which makes a prompt that stopped working visible in the daily capture line instead of silent. Unresolved real-Windows evidence is recorded PENDING-REAL-WINDOWS with the exact steps (T8), never marked passed.

## Decisions
- D1: `MessageBoxTimeoutW` via ctypes — alternatives: `MessageBoxW` in a thread with `join(timeout)` (documented API, about 5 lines more; **the fallback if H1/H2 fail or the reviewer rejects an undocumented export**), tkinter (no timeout, Tcl/Tk absent from the embeddable Python), toast (does not block; the answer returns through a second activated process, breaking US-4/AC-2), `wscript` Popup (VBScript is deprecated); why: shortest, built-in timeout code, no dependency or process; source: research note section 2 and 4.
- D2: Gate in a `capture_once` function with injected `consent` and `grab` — alternatives: monkeypatching module globals in tests, a class; why: the ordering test (grab never runs before a yes) and the no/timeout tests need no person and no Windows; source: research note, "Test in CI".
- D8 (Atlas, 2026-10-20, under Connor's delegation; do not re-ask): mechanism is `MessageBoxTimeoutW` via `ctypes`, default button No, about 20 s timeout, fail closed. Fallback is `MessageBoxW` in a thread with `join(timeout)` only if H1/H2 fail. No Zenity and no new Windows binary.
- D9: Tests cover the consent paths yes, no, timeout and dialog-failure with the dialog mocked (T10), plus a real `MessageBoxTimeoutW` timeout on the runner in the shared Windows end-to-end job (T8).
- D10: Windows proof is the shared end-to-end job on `windows-latest` in `.github/workflows/checks.yml` (Atlas, 2026-10-20), created by the earlier builds. This build extends it with named steps and creates no second job: run the real capture script with the prompt on and the dialog auto-answered yes and no through a test hook (a `consent` seam selected by an environment variable that exists only in the test, never in a shipped task), and a real `MessageBoxTimeoutW` call with a short timeout that returns 32000 on the runner.
- D11: Verification is the build worktree's own venv, `.venv/bin/python -m pytest -q tests skills/daily/tests` and `.venv/bin/pyright`, plus `Checks` green on the PR head. The spec's `auto` probes read the latest completed `Checks` conclusion on main, so at the build gate the run's `headSha` must contain the build.
- D3: Opt-in is the `--ask` task argument set by `-AskFirst` — alternatives: a `TIMESHEET_SCREENSHOT_PROMPT` setting (needs the config to reach a task that never sees it), a separate task; why: see Approach 3; command line unchanged when off.
- D4: The skip line carries the date and the word `skipped`; a prompt that could not be shown logs `prompt-error` — alternative: log the reason inside `skipped`; why: spec says the log names the time and "skipped" only; a distinct word keeps a broken prompt from being reported as the user's choice.
- D5: Readers learn about skips from `capture.log` — alternatives: write a marker file per skip (clutters the folder the readers list; a capture folder with a marker file is not "no capture"), create an empty dated folder (changes what reconcile's index reads as "machine used"); why: the log already exists, and a no/timeout must leave nothing in the capture folder (B2).
- D6: Lighter options are not planned. The research found a pause control and an app-based skip fail open and recommends keeping the prompt. A pause control is a possible follow-up for atlas to raise if Connor finds the prompt tedious (204 to 276 prompts a day by the researcher's count); it is outside this spec and not built or specified here.
- D7: Timeout 20 s, default No, topmost, wording "Take a work screenshot now?" — alternatives: 10 s (misses a slow click on a busy day), 60 s (blocks the 150 s cadence, risks overlap); why: well under the 150 s interval; source: research note section 4.

## Coverage
| Criterion | Plan section | Tasks |
|---|---|---|
| US-1/AC-1 | Approach 1, 2, 4; D8, D9 | T2, T3, T6, T10 |
| US-1/AC-2 | Approach 2 | T2, T6 |
| US-1/AC-3 | Research and spike (H3), Approach 1; D10 | T1, T8 |
| US-2/AC-1 | Approach 2 | T2 |
| US-2/AC-2 | Approach 4, 5 | T3, T6 |
| US-2/AC-3 | Approach 5 | T3, T5, T6 |
| US-3/AC-1 | Approach 6 | T5 |
| US-3/AC-2 | Approach 3, 7 | T4 |
| US-4/AC-1 | header (Research), D6 | T7 |
| US-4/AC-2 | Approach 3, Cleanup | T4, T7 |
| US-4/AC-3 | Approach (size estimate) | T7 |
| US-5/AC-1 | Verification; D11 | T9 |
| US-5/AC-2 | Verification; D11 | T9 |

## Risks and rollback
- **Habituation**: a user who clicks Yes without reading defeats the goal (research 3c). Mitigation: default No, wording that names the purpose, setup says it can be turned off. Not solved here; the pause control is the follow-up for atlas (D6).
- **Undocumented export removed or behaves differently** → fails closed (no capture, `prompt-error` in the log, visible in the daily capture line); D1 fallback is the documented API.
- **Focus theft or a box hidden behind other windows** (H3) → CI cannot drive it; stated plainly as not verified for Atlas's ship decision (T8); never marked passed. A box that never shows times out = skip.
- **Spec bar US-2/AC-2 cannot pass as written** (it asks for a skeleton byte-identical to a day with captures, but the `captures:` line is in the skeleton text and US-2/AC-3 requires it to change; gate finding F4). The spec's US-2/AC-2 bar is now amended to this scoped reading (F4): breaks, work start and end, active spans and ratios are identical, only the `captures:` line may differ. T6 produces that comparison.
- **US-5 auto probes (resolved, F1)** now read `Checks` on main. The build runs D11 and records the output.
- **Hotspots**: `skills/setup/SKILL.md` Step 5 and `skills/daily/SKILL.md` are being edited by other cards. Build starts from fresh `origin/main` after the other four builds (this lands last, after retention), keeps the daily SKILL.md edit to one pointer sentence (the 5,000-word ceiling from #57), and puts the rule in `references/first-run.md`. Read `docs/CONTRIBUTING.md` first and run its instruments for the skill changes.
- **Capture log grows**: one short line per skip, about 270 a day at most; no rotation exists today and none is added.
- **Rollback**: the prompt is off unless `--ask` is in the task. To turn it off, re-run setup without `-AskFirst` (registers with `-Force`, so the task is replaced). To remove the feature, revert the build PR; with no `--ask` in any task the script's behaviour is today's. Checked in T4 (dry-run output with and without the switch).

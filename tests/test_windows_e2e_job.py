"""The shared Windows end-to-end job (check-in-answers T14, plan D12/D16).

The job itself only runs on `windows-latest`; these checks run everywhere and pin its shape,
so it cannot be quietly emptied: the job exists, runs the setup script for real, and the driver
holds named step functions with real assertions. Later builds (web watchers, retention,
consent) add steps to the driver rather than editing these.

What the job cannot show stays unverified and is said so in the driver's docstring: the
watcher writing after a real away period, the logon trigger after sign-in, a person answering
the dialog, and focus.
"""
import ast
import re

from shipped import REPO

CHECKS = REPO / ".github" / "workflows" / "checks.yml"
DRIVER = REPO / "tests" / "e2e" / "windows_checkin_e2e.py"

STEPS = ("step_install_watcher", "step_start_server", "step_inject_answers",
         "step_assert_question_not_block", "step_assert_lunch_stays_break",
         "step_uninstall")


def job_text() -> str:
    text = CHECKS.read_text(encoding="utf-8")
    found = re.search(r"^  windows-e2e:\n(.*?)(?=^  \S|\Z)", text, re.M | re.S)
    assert found, "checks.yml has no `windows-e2e` job"
    return found.group(1)


def test_the_job_runs_on_windows_latest_and_runs_the_driver():
    body = job_text()
    assert "runs-on: windows-latest" in body
    assert "tests/e2e/windows_checkin_e2e.py" in body
    assert "activitywatch-${{ matrix.aw }}-windows-x86_64.zip" in body or \
        "windows-x86_64.zip" in body, "the job does not fetch the real Windows aw-server"
    assert re.search(r"3\.1[1-9]", body), "the pinned watcher needs Python 3.11+"


def test_the_driver_has_one_named_function_per_step_and_a_main_that_calls_them():
    tree = ast.parse(DRIVER.read_text(encoding="utf-8"))
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    for name in STEPS:
        assert name in funcs, f"driver has no `{name}`"
    called = {c.func.id for c in ast.walk(funcs["main"]) if isinstance(c, ast.Call)
              and isinstance(c.func, ast.Name)}
    assert set(STEPS) <= called, "main() does not run every step"


def test_the_assert_steps_really_assert_and_the_driver_says_what_it_cannot_show():
    src = DRIVER.read_text(encoding="utf-8")
    tree = ast.parse(src)
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    for name in ("step_assert_question_not_block", "step_assert_lunch_stays_break"):
        assert any(isinstance(n, ast.Assert) or (isinstance(n, ast.Call)
                   and getattr(n.func, "id", "") == "check") for n in ast.walk(funcs[name])), name
    doc = ast.get_docstring(tree) or ""
    for gap in ("real away period", "logon trigger", "real dialog", "focus"):
        assert gap in doc, f"the driver does not list '{gap}' as unverified"


def test_the_driver_injects_the_real_watcher_shape_and_runs_setup_for_real():
    src = DRIVER.read_text(encoding="utf-8")
    for needle in ("aw-watcher-ask-away_", "afktask", '"message"', "setup_checkin_watcher.ps1",
                   "Get-ScheduledTask", "Unregister-ScheduledTask", "call with ACME", "lunch"):
        assert needle in src, f"driver never mentions {needle}"
    assert "-DryRun" not in src, "the job must register the task for real"

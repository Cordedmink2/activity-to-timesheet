"""`setup_checkin_watcher.ps1`: the check-in watcher survives a reboot, with no admin.

One per-user scheduled task at logon (plan D2): interactive logon type (the dialog needs the
user's desktop), `RunLevel Limited`, restart on failure. The static assertions run
everywhere; the dry run needs Windows PowerShell 5.1 and runs on `windows-latest`.
What this cannot show (the logon trigger firing after a real sign-in, the watcher writing
after a real away period) is stated in the plan as not verified.
"""
import re
import subprocess

import pytest

from shipped import SKILLS
from test_install_scripts import requires_winps, winps

SCRIPT = SKILLS / "daily" / "scripts" / "setup_checkin_watcher.ps1"
PINNED = "0.0.6"


def text() -> str:
    return SCRIPT.read_text(encoding="utf-8-sig")


def test_the_script_ships():
    assert SCRIPT.is_file()


def test_it_registers_a_logon_task_that_never_asks_for_admin():
    body = text()
    assert "New-ScheduledTaskTrigger -AtLogOn" in body
    assert re.search(r"-LogonType\s+Interactive", body)
    assert re.search(r"-RunLevel\s+Limited", body)
    assert "Highest" not in body and "RunAs" not in body and "-Verb" not in body
    assert "-RestartCount" in body and "-RestartInterval" in body


def test_it_pins_the_watcher_version_and_installs_without_admin():
    body = text()
    assert f"aw-watcher-ask-away=={PINNED}" in body
    assert "pip install --user" in body


def test_it_has_a_dry_run_and_a_force_switch_like_the_screenshot_script():
    body = text()
    assert "[switch]$DryRun" in body and "[switch]$Force" in body and "$PythonExe" in body


def test_it_says_how_to_check_and_remove_the_task():
    body = text()
    assert "Get-ScheduledTask" in body and "Unregister-ScheduledTask" in body


@requires_winps
def test_the_dry_run_reports_the_task_it_would_register_and_registers_nothing():
    r = subprocess.run([winps(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT),
                        "-DryRun"], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    out = r.stdout
    assert "DRYRUN Trigger" in out and "AtLogOn" in out
    assert "DRYRUN RunLevel" in out and "Limited" in out
    assert "DRYRUN LogonType" in out and "Interactive" in out
    assert PINNED in out
    assert "Highest" not in out
    assert "nothing installed, no task registered" in out

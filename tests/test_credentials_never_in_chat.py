"""Credentials never touch chat, in every shipped skill (guided-setup T15, US-2/AC-3, D12).

Two ways a credential reaches the transcript: a skill asks the user to type or paste one
into the conversation, or a command prints one. "Shipped" is the export set: every file
under `skills/<skill>/` except `tests/`, caches and `.env`. The guard is proved by planting
a violation in a scratch copy and watching it fail, so a pattern that stopped matching is
caught; the plants are built here and never exist in the tree.
"""
import re
import shutil
from pathlib import Path

import pytest

from shipped import SKILLS

SECRET = r"(password|passphrase|token|api[ _-]?key|secret|credential)s?"
ASK = re.compile(
    rf"\b(paste|type|enter|send|share|give|provide|tell me|put)\b[^.\n]{{0,60}}\b{SECRET}\b"
    rf"[^.\n]{{0,60}}\b(chat|conversation|here|message|reply|prompt)\b", re.I)
# A sentence that forbids the act is not an ask.
FORBIDS = re.compile(r"\b(never|not|n't|no command|rather than|instead of|without)\b", re.I)
VAR = r"\$\{?!?[A-Za-z_]*(KEY|TOKEN|SECRET|PASSWORD|PASSWD)[A-Za-z_]*\}?"
PRINTS = re.compile(
    rf"\b(echo|printf|print|Write-Host|Write-Output)\b[^\n|;]*{VAR}"
    r"|\bprintenv\b|^\s*(env|set)\s*$|\bcat\b[^\n]*\.env\b|\bGet-Content\b[^\n]*\.env\b"
    r"|\$env:[A-Za-z_]*(KEY|TOKEN|SECRET|PASSWORD)", re.I)
SKIPPED = {"tests", "__pycache__", ".pytest_cache"}
TEXT = {".md", ".py", ".ps1", ".sh", ".example", ".txt"}


def violations(skills: Path) -> list[str]:
    found = []
    for path in sorted(skills.rglob("*")):
        rel = path.relative_to(skills)
        if not path.is_file() or path.suffix not in TEXT or path.name == ".env":
            continue
        if SKIPPED & set(rel.parts[1:]):
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            where = f"{rel.as_posix()}:{number}"
            if ASK.search(line) and not FORBIDS.search(line):
                found.append(f"{where} asks the user to put a credential in chat")
            if path.suffix != ".py" and PRINTS.search(line) and not FORBIDS.search(line):
                found.append(f"{where} prints a credential")
    return found


def test_no_shipped_skill_asks_for_or_prints_a_credential():
    assert violations(SKILLS) == []


@pytest.fixture
def scratch(tmp_path):
    copy = tmp_path / "skills"
    shutil.copytree(SKILLS, copy, ignore=shutil.ignore_patterns(
        "tests", "__pycache__", ".pytest_cache", ".env"))
    return copy


def plant(scratch: Path, relative: str, line: str) -> list[str]:
    path = scratch / relative
    path.write_text(path.read_text(encoding="utf-8") + "\n" + line + "\n", encoding="utf-8")
    return violations(scratch)


def test_a_planted_ask_to_paste_an_api_key_fails_naming_the_line(scratch):
    assert violations(scratch) == []
    found = plant(scratch, "onboard-client/SKILL.md",
                  "Paste your Harvest API key into the chat so I can test it.")
    assert any("onboard-client/SKILL.md" in f and "asks the user" in f for f in found)


def test_a_planted_password_ask_in_a_reference_fails(scratch):
    found = plant(scratch, "setup/references/install-commands.md",
                  "Type your password here when the installer asks.")
    assert any("install-commands.md" in f and "asks the user" in f for f in found)


def test_a_planted_echo_of_a_credential_in_a_check_fails(scratch):
    found = plant(scratch, "setup/references/checks.md", "echo $HARVEST_API_KEY")
    assert any("checks.md" in f and "prints a credential" in f for f in found)


def test_a_planted_dump_of_the_env_file_fails(scratch):
    found = plant(scratch, "troubleshoot/SKILL.md", "Run `cat .env` and read me the result.")
    assert any("troubleshoot/SKILL.md" in f and "prints a credential" in f for f in found)


def test_a_sentence_that_forbids_the_act_is_not_a_violation(scratch):
    assert plant(scratch, "setup/SKILL.md",
                 "Never ask the user to paste an API key into the chat.") == []

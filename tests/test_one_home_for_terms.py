"""Category terms have one home (guided-setup T3, US-6/AC-1).

A client's terms are written once, on its **Category terms** line in the workspace context
file. Rules are compiled from that file (`category_rules.py --from-context`) and nothing
else defines or transcribes them. "Shipped" means what `install/export_agent_skills.py`
copies: every file under `skills/<skill>/` except `tests/`, caches and `.env`.

The guard is proved the only way a guard can be: by planting a violation in a scratch copy
and watching it fail (`test_a_planted_*`), so a pattern that stopped matching is caught.
"""
import re
import shutil
from pathlib import Path

import pytest

from shipped import SKILLS

# The context template shows the line; the parser and compiler read it. Nothing else may
# define, hold or hand-transcribe terms.
ALLOWED = {"references/context.md.example", "scripts/category_rules.py",
           "scripts/context_terms.py"}
SKIPPED_DIRS = {"tests", "__pycache__", ".pytest_cache"}
TEXT_SUFFIXES = {".md", ".py", ".ps1", ".example", ".json", ".txt", ".sh"}

LITERAL_LIST = re.compile(r'"terms"\s*:\s*\[')
FILLED_LINE = re.compile(r"\*\*Category terms\*\*:\s*`[^<`]")
CONSTANT = re.compile(r"(?<![A-Za-z_])TERMS\s*=")
CANDIDATE_SHAPE = re.compile(
    r'\{"client",\s*"terms"\}|\{client,\s*terms\}|one candidate per client'
    r"|\bcandidates?\b[^.\n]*Category terms|Category terms[^.\n]*\bcandidates?\b", re.I)


def shipped_files(skills: Path):
    for path in sorted(skills.rglob("*")):
        rel = path.relative_to(skills)
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES or path.name == ".env":
            continue
        if SKIPPED_DIRS & set(rel.parts[1:]):
            continue
        yield "/".join(rel.parts[1:]), rel, path


def violations(skills: Path) -> list[str]:
    found = []
    for inner, rel, path in shipped_files(skills):
        if inner in ALLOWED:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            where = f"{rel.as_posix()}:{number}"
            if LITERAL_LIST.search(line):
                found.append(f"{where} defines a terms list")
            if FILLED_LINE.search(line):
                found.append(f"{where} holds a filled Category terms line")
            if path.suffix == ".py" and CONSTANT.search(line):
                found.append(f"{where} defines a TERMS constant")
            # The one cited exception: the adopt-existing-rules route, which names
            # `--candidates` for rules the plugin did not write.
            if "--candidates" in line and "adopt" in line:
                continue
            if "--candidates" in line or CANDIDATE_SHAPE.search(line):
                found.append(f"{where} transcribes Category terms into candidates")
    return found


def test_the_shipped_plugin_defines_terms_in_one_place_only():
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


def test_a_planted_second_definition_fails_the_guard(scratch):
    assert violations(scratch) == []
    found = plant(scratch, "setup/SKILL.md", 'Use {"client": "Acme", "terms": ["ACME"]} here.')
    assert any("defines a terms list" in f and "setup/SKILL.md" in f for f in found)


def test_a_planted_filled_terms_line_fails_the_guard(scratch):
    found = plant(scratch, "daily/SKILL.md", "**Category terms**: `ACME`, `AcmePortal`")
    assert any("filled Category terms line" in f for f in found)


def test_a_planted_terms_constant_fails_the_guard(scratch):
    found = plant(scratch, "daily/scripts/skill_config.py", 'TERMS = ["acme"]')
    assert any("TERMS constant" in f for f in found)


def test_a_planted_generic_transcription_instruction_fails_the_guard(scratch):
    found = plant(scratch, "daily/references/day-reading.md",
                  "Build one candidate per client from the Category terms lines you read.")
    assert any("transcribes Category terms" in f for f in found)


def test_a_planted_candidates_file_route_fails_the_guard(scratch):
    found = plant(scratch, "setup/SKILL.md", "Run category_rules.py --candidates <file>.")
    assert any("transcribes Category terms" in f for f in found)


def test_the_adopt_existing_rules_route_may_name_candidates(scratch):
    assert plant(scratch, "setup/references/choosing-terms.md",
                 "To adopt a rule the plugin did not write, use --candidates with adopts.") == []

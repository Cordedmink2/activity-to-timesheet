"""Setup's category stage waits for data, and the context file is the one home of terms
(guided-setup T7; US-3/AC-1, US-6/AC-1, US-6/AC-2)."""
import re

import shipped
from shipped import REPO, SKILLS

SETUP = SKILLS / "setup"
CHOOSING = SETUP / "references" / "choosing-terms.md"


def category_step() -> str:
    text = shipped.skill_md_text(SETUP)
    section = text.split("## Steps", 1)[1].split("\n## ", 1)[0]
    found = re.split(r"^### (.+)$", section, flags=re.M)[1:]
    bodies = [b for h, b in zip(found[0::2], found[1::2]) if re.search(r"categor", h, re.I)]
    assert len(bodies) == 1
    return bodies[0]


def test_the_stage_checks_the_recorded_data_before_it_inspects_anything():
    body = category_step()
    assert "--data-days" in body
    assert body.index("--data-days") < body.index("--inspect")


def test_under_the_threshold_the_stage_stops_and_writes_no_rule():
    body = category_step()
    assert "COLLECTING" in body and "READY" in body
    assert re.search(r"writes? no rule|write no rule|nothing (is )?written", body, re.I)
    assert re.search(r"come back", body, re.I)


def test_the_stage_writes_the_rules_from_the_context_file():
    body = category_step()
    assert "--from-context" in body
    assert body.index("context.md.example") < body.index("--from-context")


def test_the_stage_carries_no_second_copy_of_the_terms():
    body = category_step()
    assert '"terms"' not in body and "```json" not in body
    assert "--candidates" not in body


def test_the_term_rules_have_one_home():
    assert CHOOSING.is_file()
    text = CHOOSING.read_text(encoding="utf-8")
    for needed in ("client code", "full name", "up to eight", "HOST", "SEEN", "adopts",
                   "--adopts"):
        assert needed in text, f"choosing-terms.md lost {needed!r}"
    holders = [p.relative_to(REPO).as_posix() for p in SETUP.rglob("*.md")
               if "no domain words" in p.read_text(encoding="utf-8")]
    assert holders == [CHOOSING.relative_to(REPO).as_posix()]


def test_the_stage_cites_the_term_rules_instead_of_copying_them():
    assert "references/choosing-terms.md" in category_step()

"""Spike S1 (guided-setup T2, US-2/AC-1): what does setup still ask a person to do.

The audit table lives in `docs/skills/setup/human-only-audit.md`. The hypothesis was written
before the step bodies were read; the table is the result. These tests keep it honest: every
setup step is classified, each classification names a source phrase that is really in the
skill, and the human-only rows are exactly the bullets of "What only a person does".
"""
import re

from shipped import REPO, SKILLS, section

AUDIT = REPO / "docs" / "skills" / "setup" / "human-only-audit.md"
SETUP = (SKILLS / "setup" / "SKILL.md").read_text(encoding="utf-8")


def rows() -> list[dict[str, str]]:
    assert AUDIT.is_file(), "the audit table is not committed"
    out = []
    for line in AUDIT.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(cells) == 4 and cells[0] not in ("Step", "---") \
                and not set(cells[0]) <= {"-", " "}:
            out.append({"step": cells[0], "human": cells[1], "source": cells[2].strip("`"),
                        "note": cells[3]})
    return out


def test_every_setup_step_and_before_you_start_is_classified():
    steps = {r["step"] for r in rows()}
    wanted = {"Before you start"} | {f"Step {n}" for n in range(1, 8)}
    heads = set(re.findall(r"^### (\d)\.", SETUP, re.M))
    assert heads == {str(n) for n in range(1, 8)}
    assert wanted <= {s.split(" — ")[0] for s in steps}


def test_every_row_is_yes_no_or_pending_real_windows():
    for r in rows():
        assert r["human"] in {"Y", "N", "PENDING-REAL-WINDOWS"}, r


def test_every_row_names_a_phrase_that_is_in_the_skill():
    for r in rows():
        text = SETUP + "".join(
            p.read_text(encoding="utf-8") for p in (SKILLS / "setup").rglob("*.md"))
        assert r["source"] and r["source"] in text, f"source not found: {r}"


def test_human_only_rows_match_the_human_only_section_exactly():
    listed = re.findall(r"^- \*\*(.+?)\*\*", section(SETUP, "What only a person does"), re.M)
    audited = [r["note"] for r in rows() if r["human"] == "Y" and r["step"].startswith("Human")]
    assert listed and sorted(listed) == sorted(audited)

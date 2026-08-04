import subprocess
import sys
from pathlib import Path

SKILLS_DIR = Path(__file__).parent.parent

SKILL_NAMES = ["medo-hearing", "medo-propose-options", "medo-grow-prfaq"]


def test_build_generates_claude_and_agy_dist(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SKILLS_DIR / "build.py"), "--out", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    for name in SKILL_NAMES:
        claude_skill = tmp_path / "claude" / name / "SKILL.md"
        assert claude_skill.exists(), name
        text = claude_skill.read_text(encoding="utf-8")
        assert text.startswith("---") and f"name: {name}" in text

        agy_skill = tmp_path / "agy" / f"{name}.md"
        assert agy_skill.exists(), name
        assert not agy_skill.read_text(encoding="utf-8").startswith("---")

    hearing = (tmp_path / "agy" / "medo-hearing.md").read_text(encoding="utf-8")
    assert "medo requirements save" in hearing

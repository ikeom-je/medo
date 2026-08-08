import subprocess
import sys
from pathlib import Path

SKILLS_DIR = Path(__file__).parent.parent

SKILL_NAMES = ["medo-hearing", "medo-propose-options", "medo-grow-prfaq"]


def test_build_generates_skill_md_per_name(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SKILLS_DIR / "build.py"), "--out", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    for name in SKILL_NAMES:
        skill_md = tmp_path / name / "SKILL.md"
        assert skill_md.exists(), name
        text = skill_md.read_text(encoding="utf-8")
        assert text.startswith("---")
        assert f"name: {name}" in text
        assert "description:" in text

    hearing = (tmp_path / "medo-hearing" / "SKILL.md").read_text(encoding="utf-8")
    assert "medo requirements save" in hearing


def test_build_rejects_missing_frontmatter(tmp_path):
    src = tmp_path / "src"
    (src / "broken").mkdir(parents=True)
    (src / "broken" / "SKILL.md").write_text("no frontmatter here", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SKILLS_DIR / "build.py"), "--src", str(src), "--out", str(tmp_path / "out")],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "frontmatter" in (result.stdout + result.stderr)

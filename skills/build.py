"""Skill共通md(1フォルダ=1 Skill)をdist/へ検証付きでコピーする。"""

import argparse
import re
from pathlib import Path
from shutil import copyfile

SRC = Path(__file__).parent / "src"


def validate(src_text: str, name: str) -> None:
    """frontmatterの必須項目(name/description)を検証する。"""
    m = re.match(r"^---\n(.*?)\n---\n", src_text, re.DOTALL)
    if not m:
        raise ValueError(f"{name}: frontmatter(---区切り)がありません")
    fm = m.group(1)
    if not re.search(r"^name:\s*\S+", fm, re.MULTILINE):
        raise ValueError(f"{name}: frontmatterにnameがありません")
    if not re.search(r"^description:", fm, re.MULTILINE):
        raise ValueError(f"{name}: frontmatterにdescriptionがありません")


def build(src: Path, out: Path) -> None:
    for skill_dir in sorted(p for p in src.iterdir() if p.is_dir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        text = skill_md.read_text(encoding="utf-8")
        validate(text, skill_dir.name)

        dest_dir = out / skill_dir.name
        dest_dir.mkdir(parents=True, exist_ok=True)
        copyfile(skill_md, dest_dir / "SKILL.md")
    print(f"built skills into {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", type=Path, default=SRC)
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "dist")
    args = parser.parse_args()
    build(args.src, args.out)

"""Skill共通md -> Claude形式(SKILL.md)とagy形式(.md)への変換。"""

import argparse
import re
from pathlib import Path

SRC = Path(__file__).parent / "src"


def parse(src_text: str) -> tuple[str, str]:
    """frontmatterのname値と本文(frontmatter除去済み)を返す。"""
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", src_text, re.DOTALL)
    if not m:
        raise ValueError("frontmatter(---区切り)がありません")
    fm, body = m.groups()
    name_m = re.search(r"^name:\s*(\S+)", fm, re.MULTILINE)
    if not name_m:
        raise ValueError("frontmatterにnameがありません")
    return name_m.group(1), body.lstrip("\n")


def build(out: Path) -> None:
    for src_file in sorted(SRC.glob("*.md")):
        text = src_file.read_text(encoding="utf-8")
        name, body = parse(text)

        claude_dir = out / "claude" / name
        claude_dir.mkdir(parents=True, exist_ok=True)
        (claude_dir / "SKILL.md").write_text(text, encoding="utf-8")

        agy_dir = out / "agy"
        agy_dir.mkdir(parents=True, exist_ok=True)
        (agy_dir / f"{name}.md").write_text(body, encoding="utf-8")
    print(f"built skills into {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "dist")
    args = parser.parse_args()
    build(args.out)

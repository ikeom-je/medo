"""CLI呼び出し列の記録。Skillの再現性をホスト間で比較するための計測機構。

状態がすべてCLIにあるため、呼び出し列は決定論的な成果物になる。同じ初期状態から
各ホストに1周させてトレースを突き合わせると、Skillが飛ばした操作が見える。
"""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

# 値を残すオプション。「どの選択肢を選んだか」はホスト間比較の対象になる。
# ここに無いオプションの値は伏せる(顧客の生の声・ファイルパスが混ざるため)。
VALUE_SAFE_OPTIONS = frozenset({
    "--type", "--slide-kind", "--result", "--check", "--purpose", "--reaction",
    "--outcome", "--disposition", "--answer", "--view", "--format", "--kind",
    "--include-scope", "--editorial", "--generated-by", "--reviewed-by",
    "--requirements-version", "--responds-to", "--stakeholder", "--artifact",
    "--report", "--slides", "--derived-from", "--covers", "--focus", "--refs",
    "--from-artifact",
})


class Tracer:
    def __init__(self, path: Path):
        self._path = path

    @classmethod
    def from_env(cls) -> "Tracer | None":
        raw = os.environ.get("MEDO_TRACE")
        return cls(Path(raw)) if raw else None

    def record(self, argv: list[str], exit_code: int) -> None:
        entry = {
            "at": datetime.now(UTC).isoformat(timespec="seconds"),
            "command": _command(argv),
            "options": _options(argv),
            "exit_code": exit_code,
        }
        try:
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass  # 計測が本来の作業を止めない


def _command(argv: list[str]) -> list[str]:
    """先頭からオプションが現れるまでの語をコマンド名とする。

    clickはサブコマンドをオプションより前に取るため、最初のオプション以降の
    非オプション語はすべてオプションの値である(`--project p1` の `p1` など)。
    """
    words: list[str] = []
    for token in argv:
        if token.startswith("-"):
            break
        words.append(token)
    return words[:2]


def _options(argv: list[str]) -> dict[str, str]:
    options: dict[str, str] = {}
    for i, token in enumerate(argv):
        if not token.startswith("--"):
            continue
        value = argv[i + 1] if i + 1 < len(argv) and not argv[i + 1].startswith("--") else ""
        options[token] = value if token in VALUE_SAFE_OPTIONS else "<redacted>"
    return options

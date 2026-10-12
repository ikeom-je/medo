"""サブコマンド間で共有するヘルパー。

main.py 側に置くと commands/ から main.py を import することになり、
登録側と実装側の依存が双方向になる。
"""

import typer

from medo_core.config import get_storage
from medo_core.requirements import RequirementsStore
from medo_core.workflow import WorkflowRecorder


def fail(reason: str) -> None:
    """stderr に error: を出して非ゼロ終了する。推測で補完しない。"""
    typer.echo(f"error: {reason}", err=True)
    raise typer.Exit(code=1)


def recorder() -> WorkflowRecorder:
    return WorkflowRecorder(get_storage())


def latest_version(project: str) -> int:
    return RequirementsStore(get_storage()).latest_version(project)


def split_ids(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]

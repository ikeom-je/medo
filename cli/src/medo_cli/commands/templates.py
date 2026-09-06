"""雛形と registry の射影を返すコマンド。案件が無い状態でも呼べる。"""

import typer

from medo_core.templates import DISCUSSION_SLIDES_OUTLINE, REQUIREMENTS_TEMPLATE

from medo_cli.commands._common import fail


def requirements_template() -> None:
    """要件YAMLの雛形を出力する。埋めて `requirements save --file` に渡す。"""
    typer.echo(REQUIREMENTS_TEMPLATE)


def artifacts_outline(
    type: str = typer.Option(..., "--type", help="現在 outline があるのは slides のみ"),
    slide_kind: str = typer.Option(
        "", "--slide-kind", help="discussion(final は優先度6で未実装)"
    ),
) -> None:
    """生成物の章構成と表現の規約を出力する。"""
    if type != "slides":
        fail(f"{type} の章構成はありません")
    if slide_kind == "final":
        fail("slide_kind=final の章構成は未実装です(フェーズ2 優先度6)")
    if slide_kind != "discussion":
        fail(f"未知の slide_kind です: {slide_kind or '(未指定)'}")
    typer.echo(DISCUSSION_SLIDES_OUTLINE)

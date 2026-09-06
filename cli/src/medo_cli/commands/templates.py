"""雛形と registry の射影を返すコマンド。案件が無い状態でも呼べる。"""

import json

import typer

from medo_core.checks import CHECK_REGISTRY
from medo_core.templates import DISCUSSION_SLIDES_OUTLINE, REQUIREMENTS_TEMPLATE

from medo_cli.commands._common import fail

CONFIRMERS = ("consultant", "customer", "both")


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


def check_list(
    confirmer: str = typer.Option(
        "", "--confirmer",
        help="consultant|customer|both。指定すると both の項目も含む。全件は省略",
    ),
    format: str = typer.Option("digest", "--format", help="json|digest"),
) -> None:
    """checkの束縛・対象生成物type・確認者・段階を出力する。"""
    if confirmer and confirmer not in CONFIRMERS:
        fail(f"未知の confirmer です: {confirmer}")
    if format not in ("json", "digest"):
        fail(f"未知の format です: {format}")

    rows = [
        {
            "name": name,
            "binding": spec.binding,
            "target_type": spec.target_type,
            "slide_kind": spec.slide_kind,
            "confirmer": spec.confirmer,
            "phase": spec.phase,
        }
        for name, spec in CHECK_REGISTRY.items()
        if not confirmer or spec.confirmer in (confirmer, "both")
    ]
    if format == "json":
        typer.echo(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    for row in rows:
        target = f" target={row['target_type']}" if row["target_type"] else ""
        typer.echo(
            f"{row['name']}  binding={row['binding']}{target}"
            f"  confirmer={row['confirmer']}  phase={row['phase']}"
        )

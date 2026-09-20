"""深掘り調査の計画を返すコマンド。"""

import json

import typer

from medo_core.config import get_knowledge_root, get_storage
from medo_core.requirements import RequirementsStore
from medo_core.research import research_plan as build_research_plan
from medo_core.status import project_status

from medo_cli.commands._common import fail


def research_plan(
    project: str = typer.Option(..., "--project"),
    depth: str = typer.Option("structural", "--depth", help="scan|structural|deep"),
    format: str = typer.Option("digest", "--format", help="json|digest"),
) -> None:
    """深度プロファイルに沿う調査計画を返す。"""
    if format not in ("json", "digest"):
        fail(f"未知の format です: {format}")
    status = project_status(get_storage(), project, get_knowledge_root(), view="model")
    if "model" not in status:
        fail(f"案件 {project} に要件がありません(先に requirements save で作成します)")
    model = status["model"]
    try:
        plan = build_research_plan(
            depth,
            {"links": model["links"], "coverage": model["coverage"]},
            _node_texts(project),
        )
    except ValueError as e:
        fail(str(e))

    if format == "json":
        typer.echo(json.dumps(plan, ensure_ascii=False, indent=2))
        return
    _echo_digest(plan)


def _echo_digest(plan: dict) -> None:
    profile = plan["profile"]
    typer.echo(f"深度プロファイル: {profile['name']}")
    typer.echo(f"最大階層: {profile['max_hops']}")
    typer.echo(f"最大ページ数: {profile['max_pages']}")
    typer.echo(f"一次資料を優先: {'はい' if profile['prefer_primary'] else 'いいえ'}")
    typer.echo("埋める観点:")
    for aspect in plan["aspects"]:
        typer.echo(f"- {aspect['name']}: {aspect['description']}")
    typer.echo("停止条件:")
    for condition in plan["stop_conditions"]:
        typer.echo(f"- {condition}")
    typer.echo("解消を狙う診断項目:")
    findings = plan["findings_to_resolve"]
    if not any(findings.values()):
        typer.echo("- なし")
        return
    for section, items in findings.items():
        for name, nodes in items.items():
            typer.echo(f"- {section}.{name}")
            for node in nodes:
                typer.echo(f"    {node['id']}: {node['text'] or '(本文なし)'}")


def _node_texts(project: str) -> dict[str, str]:
    """ノードIDから本文への対応。IDだけでは何を調べるか決められない。"""
    doc = RequirementsStore(get_storage()).get(project)
    if doc is None:
        return {}
    return {
        node.id: getattr(node, "text", "") or getattr(node, "name", "")
        for section, nodes in doc
        if isinstance(nodes, list)
        for node in nodes
        if hasattr(node, "id") and node.id
    }

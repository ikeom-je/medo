"""深掘り調査の計画を返すコマンド。"""

import json
import os
from pathlib import Path

import typer

from medo_core.config import get_knowledge_root, get_storage
from medo_core.requirements import RequirementsStore
from medo_core.research import ASPECTS, Candidate, PROFILES, research_plan as build_research_plan
from medo_core.research import triage
from medo_core.status import project_status

from medo_cli.commands._common import fail
from medo_cli.jev import judge_candidates


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


def research_triage(
    project: str = typer.Option(..., "--project"),
    file: Path = typer.Option(
        ..., "--file", exists=True, readable=True, help="候補のJSON配列"
    ),
    depth: str = typer.Option("structural", "--depth"),
    opened: int = typer.Option(0, "--opened", help="これまでに開いたページ数"),
    format: str = typer.Option("digest", "--format"),
) -> None:
    """候補をJevで判定し、次に開く順を返す。"""
    if format not in ("json", "digest"):
        fail(f"未知の format です: {format}")
    try:
        raw_candidates = json.loads(file.read_text(encoding="utf-8"))
        if not isinstance(raw_candidates, list):
            raise ValueError("候補JSONのトップレベルは配列である必要があります")
        candidates = [Candidate.model_validate(candidate) for candidate in raw_candidates]
        profile = PROFILES[depth]
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        fail(f"候補または深度プロファイルが不正です: {e}")

    if not os.environ.get("TYPESAFE_API_KEY"):
        _echo_triage_unavailable(candidates, profile, opened, format)
        return

    try:
        aspects = {name: ASPECTS[name] for name in profile.aspects}
        verdicts = judge_candidates(candidates, aspects, _project_context(project))
        result = triage(candidates, verdicts, depth, opened)
    except (KeyError, RuntimeError, ValueError) as e:
        fail(str(e))
    result["judge"] = "available"
    _echo_triage(result, format)


def _echo_triage_unavailable(
    candidates: list[Candidate], profile, opened: int, format: str
) -> None:
    """判定できないときも通常時と同じ形を返す。形が変わると呼び出し側が壊れる。"""
    budget_left = max(0, profile.max_pages - opened)
    result = {
        "judge": "unavailable",
        "open": [candidate.url for candidate in candidates][:budget_left],
        "rejected": [],
        "diminishing_returns": False,
        "budget_left": budget_left,
    }
    if format == "json":
        typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
        return
    typer.echo("judge: unavailable")
    for candidate in candidates:
        typer.echo(candidate.url)


def _echo_triage(result: dict, format: str) -> None:
    if format == "json":
        typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
        return
    typer.echo("judge: available")
    for url in result["open"]:
        typer.echo(url)


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


def _project_context(project: str) -> dict:
    """案件を知らないモデルに「この案件の現状把握に効くか」は問えない。"""
    doc = RequirementsStore(get_storage()).get(project)
    if doc is None:
        return {}
    return {
        "industry": doc.industry,
        "goal": doc.goal,
        "challenges": [c.text for c in doc.challenges],
        "open_questions": [q.text for q in doc.open_questions],
    }

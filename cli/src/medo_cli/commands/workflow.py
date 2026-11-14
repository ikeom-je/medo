"""進行記録の記録コマンド。標準周回の各ステージが呼ぶ。

main.py は登録だけを行い、ここは main.py を import しない(逆流を避ける)。
"""

from datetime import date

import typer

from medo_cli.commands._common import fail as _fail
from medo_cli.commands._common import latest_version as _latest_version
from medo_cli.commands._common import recorder as _recorder
from medo_core.events import (
    ArtifactTarget,
    AsIsReportReviewed,
    CheckRecorded,
    RequirementsTarget,
    StakeholderResponded,
    ToBeCheckpointRecorded,
)

check_app = typer.Typer(help="発見プロセスの確認結果を記録する")
review_app = typer.Typer(help="AsIsレポートと討議用スライドのレビューを記録する")
respond_app = typer.Typer(help="ステークホルダーの反応を記録する")
checkpoint_app = typer.Typer(help="ToBeチェックポイントに回答する")


@check_app.command("add")
def check_add(
    project: str = typer.Option(..., "--project"),
    check: str = typer.Option(..., "--check"),
    result: str = typer.Option(..., "--result", help="completed|finding|undeterminable"),
    note: str = typer.Option("", "--note"),
    refs: str = typer.Option("", "--refs", help="finding の該当ノードID(カンマ区切り)"),
    disposition: str = typer.Option(
        "open",
        "--disposition",
        help=(
            "undeterminable の扱い: open|deferred|promoted。"
            "変更時は同じ項目をrecordし直して更新する"
        ),
    ),
    artifact: str | None = typer.Option(
        None, "--artifact", help="artifact束縛の check の対象ID"
    ),
) -> None:
    """チェック項目の確認結果を記録する。"""
    try:
        version = _latest_version(project)
        target = (
            ArtifactTarget(artifact_id=artifact)
            if artifact
            else RequirementsTarget(version=version)
        )
        event = CheckRecorded(
            target=target,
            occurred_on=date.today().isoformat(),
            requirements_version=version,
            round_id=0,
            check=check,
            result=result,
            note=note,
            finding_refs=[r.strip() for r in refs.split(",") if r.strip()],
            disposition=disposition,
        )
        event_id = _recorder().record(project, event)
    except Exception as e:
        _fail(str(e))
    typer.echo(f"recorded: {event_id}")


@review_app.command("add")
def review_add(
    project: str = typer.Option(..., "--project"),
    report: str = typer.Option(..., "--report", help="レビュー対象の as-is-report ID"),
    slides: str = typer.Option(..., "--slides", help="同時にレビューした討議用スライドID"),
    outcome: str = typer.Option(..., "--outcome", help="approved|changes_requested"),
    refs: str = typer.Option("", "--refs", help="要件側の所見ノードID(カンマ区切り)"),
    slide_findings: list[str] = typer.Option(
        [], "--slide-finding", help="スライド固有の所見(複数可)"
    ),
    reviewed_by: str = typer.Option("human", "--reviewed-by"),
) -> None:
    """AsIsレポートと討議用スライドのレビュー結果を記録する。"""
    try:
        event = AsIsReportReviewed(
            target=ArtifactTarget(artifact_id=report),
            occurred_on=date.today().isoformat(),
            requirements_version=_latest_version(project),
            round_id=0,
            outcome=outcome,
            reviewed_slides_id=slides,
            finding_refs=[r.strip() for r in refs.split(",") if r.strip()],
            slide_findings=list(slide_findings),
            reviewed_by=reviewed_by,
        )
        event_id = _recorder().record(project, event)
    except Exception as e:
        _fail(str(e))
    typer.echo(f"recorded: {event_id}")


@respond_app.command("add")
def respond_add(
    project: str = typer.Option(..., "--project"),
    stakeholder: str = typer.Option(..., "--stakeholder"),
    purpose: str = typer.Option(
        ..., "--purpose", help="as_is_alignment|to_be_go_ahead|phase_signoff"
    ),
    reaction: str = typer.Option(
        ..., "--reaction", help="empathized|acknowledged|agreed|objected|unclear"
    ),
    artifact: str | None = typer.Option(None, "--artifact", help="生成物宛ての場合の対象ID"),
    note: str = typer.Option("", "--note"),
) -> None:
    """本人が対話で得た他者の反応を記録する(本人性の検証はしない)。"""
    try:
        version = _latest_version(project)
        target = (
            ArtifactTarget(artifact_id=artifact)
            if artifact
            else RequirementsTarget(version=version)
        )
        event = StakeholderResponded(
            target=target,
            occurred_on=date.today().isoformat(),
            requirements_version=version,
            round_id=0,
            stakeholder_id=stakeholder,
            purpose=purpose,
            reaction=reaction,
            note=note,
        )
        event_id = _recorder().record(project, event)
    except Exception as e:
        _fail(str(e))
    typer.echo(f"recorded: {event_id}")


@checkpoint_app.command("answer")
def checkpoint_answer(
    project: str = typer.Option(..., "--project"),
    responds_to: str = typer.Option(..., "--responds-to", help="回答対象の節目イベントID"),
    answer: str = typer.Option(..., "--answer", help="generate|defer"),
    focus: str = typer.Option("", "--focus", help="この周回で検証する仮説ID"),
) -> None:
    """ToBeを出す/更新するかの判断を記録する。"""
    try:
        version = _latest_version(project)
        event = ToBeCheckpointRecorded(
            target=RequirementsTarget(version=version),
            occurred_on=date.today().isoformat(),
            requirements_version=version,
            round_id=0,
            answer=answer,
            responds_to=responds_to,
        )
        event_id = _recorder().record(project, event)
        if focus:
            _recorder().set_focus(project, responds_to, focus)
    except Exception as e:
        _fail(str(e))
    typer.echo(f"recorded: {event_id}")

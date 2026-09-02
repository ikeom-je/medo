"""medo CLI。事実と計算の決定論的インターフェース。失敗時は推測せずエラーを返す。"""

import os
import json
import sys
from datetime import date
from pathlib import Path
from typing import Literal

import typer
import yaml
from medo_core.artifacts import Artifact, ArtifactStore, GrownFrom, OptionMeta, RejectedOption
from medo_core.facts import Fact, FactStore
from medo_core.fermi import FermiModel, evaluate
from medo_core.config import get_knowledge_root, get_storage
from medo_core.knowledge import (
    KnowledgeEntry,
    KnowledgeStore,
    ProjectKnowledgeEntry,
    resolve_knowledge_backend,
)
from medo_core.requirements import RequirementsDoc, RequirementsStore
from medo_core.status import project_status, stale_artifact_ids
from medo_cli.trace import Tracer

app = typer.Typer(no_args_is_help=True, help="Medo(目処) — クラウド非依存の上流工程Agent CLI")
requirements_app = typer.Typer(no_args_is_help=True)
knowledge_app = typer.Typer(no_args_is_help=True)
artifacts_app = typer.Typer(no_args_is_help=True)
facts_app = typer.Typer(no_args_is_help=True)
fermi_app = typer.Typer(no_args_is_help=True)
app.add_typer(requirements_app, name="requirements", help="要件ドキュメント(バージョン管理)")
app.add_typer(knowledge_app, name="knowledge", help="技術ナレッジ(案件横断)/ 案件固有ナレッジ")
app.add_typer(artifacts_app, name="artifacts", help="生成物の保存・一覧")
app.add_typer(facts_app, name="facts", help="市場・国策・業界動向・個社ファクト(出典必須)")
app.add_typer(fermi_app, name="fermi", help="フェルミ推定(仮定明示・コードが計算)")


def _fail(reason: str) -> None:
    typer.echo(f"error: {reason}", err=True)
    raise typer.Exit(code=1)


@requirements_app.command("save")
def requirements_save(
    project: str = typer.Option(...),
    file: Path = typer.Option(..., exists=True, readable=True),
    editorial: list[str] = typer.Option(
        [],
        "--editorial",
        help=(
            "誤字・言い回しの修正のみと宣言するセクション名"
            "(text以外に差分があるセクションの宣言は無視される)"
        ),
    ),
) -> None:
    try:
        data = yaml.safe_load(file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("YAMLのトップレベルはマッピングである必要があります")
        doc = RequirementsDoc.model_validate({**data, "project": project})
        version = RequirementsStore(get_storage()).save(
            project, doc, editorial_sections=tuple(editorial)
        )
    except Exception as e:  # yaml.YAMLError, ValueError, pydantic.ValidationError
        _fail(f"要件のスキーマ不正: {e}")
    typer.echo(f"saved: v{version}")


@requirements_app.command("get")
def requirements_get(
    project: str = typer.Option(...),
    version: int | None = typer.Option(None),
    format: Literal["json", "digest"] = typer.Option("json"),
):
    doc = RequirementsStore(get_storage()).get(project, version)
    if doc is None:
        _fail(f"プロジェクト '{project}' の要件が見つかりません")
    if format == "json":
        typer.echo(json.dumps(doc.model_dump(mode="json"), ensure_ascii=False, indent=2))
    else:
        typer.echo(f"{doc.project} v{doc.version}: {doc.goal}")
        if doc.background:
            typer.echo(f"  背景: {doc.background}")
        for p in doc.principles:
            typer.echo(f"  理念 [{p.confidence}] {p.text}")
        for c in doc.challenges:
            typer.echo(f"  課題 [{c.confidence}] {c.text}")
        for f in doc.functional:
            typer.echo(f"  - [{f.confidence}] {f.text}")
        for q in doc.open_questions:
            typer.echo(f"  ? {q.text}")


@requirements_app.command("diff")
def requirements_diff(project: str = typer.Option(...)):
    storage = get_storage()
    req_store = RequirementsStore(storage)
    current = req_store.latest_version(project)
    if current == 0:
        _fail(f"プロジェクト '{project}' の要件が見つかりません")
    typer.echo(
        json.dumps(
            {
                "requirements": req_store.diff(project),
                "stale_artifacts": stale_artifact_ids(storage, project, get_knowledge_root()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


@app.command()
def status(project: str = typer.Option(...)):
    """プロジェクトの現在地(要件・ファクト・生成物・next_step)をJSONで出力する。"""
    report = project_status(get_storage(), project, get_knowledge_root())
    typer.echo(json.dumps(report, ensure_ascii=False, indent=2))


def _knowledge_entry_payload(entry) -> dict:
    return (
        {"entry": entry.model_dump(mode="json"), "stale": entry.is_stale()}
        if hasattr(entry, "is_stale")
        else entry.model_dump(mode="json")
    )


@knowledge_app.command("search")
def knowledge_search(
    query: str = typer.Argument(""),
    project: str | None = typer.Option(None, help="指定時は案件固有ナレッジを検索"),
    kind: str | None = typer.Option(None, help="tech|market|policy|trend|company(案件横断のみ)"),
    format: Literal["json", "digest"] = typer.Option("digest"),
):
    if project:
        storage = get_storage()
        doc = RequirementsStore(storage).get(project)
        backend_name = doc.knowledge_backend if doc else "markdown"
        backend = resolve_knowledge_backend(
            backend_name,
            project,
            get_knowledge_root(),
            Path(os.environ.get("MEDO_HOME", str(Path.home() / ".medo"))),
        )
        entries = backend.search(project, query)
        if format == "json":
            typer.echo(
                json.dumps([e.model_dump(mode="json") for e in entries], ensure_ascii=False, indent=2)
            )
            return
        if not entries:
            typer.echo("(該当なし)")
            return
        for e in entries:
            typer.echo(f"{e.entry_id} {e.statement[:60]} (出典: {e.source}, {e.retrieved})")
        return

    entries = KnowledgeStore(get_knowledge_root()).search(query, kind=kind)
    if format == "json":
        typer.echo(
            json.dumps([_knowledge_entry_payload(e) for e in entries], ensure_ascii=False, indent=2)
        )
        return
    if not entries:
        typer.echo("(該当なし)")
        return
    for e in entries:
        stale = " [STALE]" if e.is_stale() else ""
        typer.echo(f"{e.entry_id} [{e.kind}]{stale} {e.statement[:60]}")


@knowledge_app.command("get")
def knowledge_get(
    kind: str = typer.Option(..., help="tech|market|policy|trend|company"),
    id: str = typer.Option(..., "--id"),
    format: Literal["json", "digest"] = typer.Option("json"),
):
    entry = KnowledgeStore(get_knowledge_root()).get(kind, id)
    if entry is None:
        _fail(f"ナレッジに {kind}/{id} が見つかりません")
    if format == "json":
        typer.echo(json.dumps(_knowledge_entry_payload(entry), ensure_ascii=False, indent=2))
        return
    stale = " [STALE]" if entry.is_stale() else ""
    typer.echo(f"{entry.entry_id}{stale} {entry.statement[:60]}")


@knowledge_app.command("save")
def knowledge_save(
    statement: str = typer.Option(...),
    source: str = typer.Option(...),
    project: str | None = typer.Option(None, help="指定時は案件固有ナレッジとして保存"),
    kind: str | None = typer.Option(
        None, help="案件横断ナレッジのみ必須: tech|market|policy|trend|company"
    ),
    value: float | None = typer.Option(None),
    unit: str = typer.Option(""),
    retrieved: str | None = typer.Option(None, help="取得日 YYYY-MM-DD(省略時は今日)"),
    note: str = typer.Option(""),
):
    retrieved = retrieved or date.today().isoformat()
    if project:
        try:
            entry = ProjectKnowledgeEntry(
                project=project,
                statement=statement,
                source=source,
                retrieved=retrieved,
                note=note,
            )
        except Exception as e:
            _fail(f"案件固有ナレッジのスキーマ不正: {e}")
        storage = get_storage()
        doc = RequirementsStore(storage).get(project)
        backend_name = doc.knowledge_backend if doc else "markdown"
        backend = resolve_knowledge_backend(
            backend_name,
            project,
            get_knowledge_root(),
            Path(os.environ.get("MEDO_HOME", str(Path.home() / ".medo"))),
        )
        entry_id = backend.append(entry)
        typer.echo(f"saved: {entry_id}")
        return

    if not kind:
        _fail("--project 未指定の場合は --kind が必須です")
    try:
        entry = KnowledgeEntry(
            kind=kind,
            statement=statement,
            value=value,
            unit=unit,
            source=source,
            retrieved=retrieved,
            note=note,
        )
    except Exception as e:
        _fail(f"ナレッジのスキーマ不正: {e}")
    entry_id = KnowledgeStore(get_knowledge_root()).save(entry)
    typer.echo(f"saved: {entry_id}")


@facts_app.command("save")
def facts_save(
    project: str = typer.Option(...),
    kind: str = typer.Option(..., help="market | policy | trend | company"),
    statement: str = typer.Option(...),
    source: str = typer.Option(..., help="market/policy/trendはURL、companyは由来表記"),
    value: float | None = typer.Option(None),
    unit: str = typer.Option(""),
    retrieved: str | None = typer.Option(None, help="取得日 YYYY-MM-DD(省略時は今日)"),
    note: str = typer.Option(""),
):
    try:
        fact = Fact(
            kind=kind,
            statement=statement,
            value=value,
            unit=unit,
            source=source,
            retrieved=retrieved or date.today().isoformat(),
            note=note,
        )
    except Exception as e:
        _fail(f"ファクトのスキーマ不正: {e}")
    fact_id = FactStore(get_storage()).save(project, fact)
    typer.echo(f"saved: {fact_id}")


@facts_app.command("list")
def facts_list(
    project: str = typer.Option(...),
    format: Literal["json", "digest"] = typer.Option("digest"),
):
    facts = FactStore(get_storage()).list(project)
    if format == "json":
        payload = [{"fact": f.model_dump(mode="json"), "stale": f.is_stale()} for f in facts]
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    if not facts:
        typer.echo("(ファクトなし)")
        return
    for f in facts:
        stale = " [STALE]" if f.is_stale() else ""
        typer.echo(f"{f.fact_id} [{f.kind}]{stale} {f.statement} (出典: {f.source}, {f.retrieved})")


@artifacts_app.command("save")
def artifacts_save(
    project: str = typer.Option(...),
    artifact_type: str = typer.Option(..., "--type"),
    file: Path = typer.Option(..., exists=True, readable=True),
    cites: str = typer.Option("", help="引用ナレッジエントリID(カンマ区切り)"),
    cites_facts: str = typer.Option("", help="引用ファクトID(カンマ区切り)"),
    options: str = typer.Option("", help="mini-prfaq用: name:approach_type をカンマ区切り"),
    grown_from: str = typer.Option("", help="prfaq用: <mini-prfaq-vN>:<打ち手名>"),
    generated_by: str | None = typer.Option(None),
    requirements_version: int = typer.Option(...),
    slide_kind: str | None = typer.Option(
        None, "--slide-kind", help="slides用: discussion|final"
    ),
    derived_from: str = typer.Option(
        "", "--derived-from", help="内容依存の親artifact ID(カンマ区切り)"
    ),
    covers: str = typer.Option("", "--covers", help="扱った課題ID(カンマ区切り)"),
    rejected: list[str] = typer.Option(
        [],
        "--rejected",
        help="見送った案: <名前>:<理由>[:<受け入れたリスク>](複数可)",
    ),
):
    try:
        option_metas = [
            OptionMeta(name=name, approach_type=approach)
            for name, _, approach in (o.partition(":") for o in options.split(",") if o)
        ]
        gf = None
        if grown_from:
            art, _, opt = grown_from.partition(":")
            gf = GrownFrom(artifact=art, option=opt)
        artifact = Artifact(
            project=project,
            type=artifact_type,
            requirements_version=requirements_version,
            cited_knowledge=[c for c in cites.split(",") if c],
            cited_facts=[c for c in cites_facts.split(",") if c],
            options=option_metas,
            grown_from=gf,
            generated_by=generated_by,
            slide_kind=slide_kind,
            derived_from=[c for c in derived_from.split(",") if c],
            covered_challenge_ids=[c for c in covers.split(",") if c] if covers else None,
            rejected_options=[
                RejectedOption(name=n, reason=r, accepted_risk=risk)
                for n, r, risk in (
                    (*v.split(":", 2), "", "")[:3] for v in rejected
                )
            ],
            content=file.read_text(encoding="utf-8"),
        )
    except Exception as e:
        _fail(f"生成物のスキーマ不正: {e}")
    artifact_id = ArtifactStore(get_storage()).save(project, artifact)
    typer.echo(f"saved: {artifact_id}")


@artifacts_app.command("get")
def artifacts_get(
    project: str = typer.Option(...),
    id: str = typer.Option(..., "--id", help="例: mini-prfaq-v1"),
):
    artifact = ArtifactStore(get_storage()).get(project, id)
    if artifact is None:
        _fail(f"生成物 {id} が見つかりません")
    typer.echo(json.dumps(artifact.model_dump(mode="json"), ensure_ascii=False, indent=2))


@artifacts_app.command("list")
def artifacts_list(project: str = typer.Option(...)):
    items = ArtifactStore(get_storage()).list(project)
    for a in items:
        by = f" by {a.generated_by}" if a.generated_by else ""
        typer.echo(f"{a.type}-v{a.version} (req v{a.requirements_version}){by}")
    if not items:
        typer.echo("(生成物なし)")


@fermi_app.command("calc")
def fermi_calc(
    project: str = typer.Option(...),
    file: Path | None = typer.Option(None, exists=True, readable=True, help="モデルYAML"),
    from_artifact: str | None = typer.Option(None, help="保存済みfermi生成物から再計算(例: fermi-v1)"),
):
    storage = get_storage()
    try:
        if from_artifact and file:
            raise ValueError("--file と --from-artifact は同時に指定できません")
        if from_artifact:
            saved = ArtifactStore(storage).get(project, from_artifact)
            if saved is None:
                raise ValueError(f"生成物 {from_artifact} が見つかりません")
            model = FermiModel.model_validate(json.loads(saved.content)["model"])
        elif file:
            model = FermiModel.model_validate(yaml.safe_load(file.read_text(encoding="utf-8")))
        else:
            raise ValueError("--file か --from-artifact のどちらかを指定してください")
        facts = {f.fact_id: f for f in FactStore(storage).list(project)}
        result = evaluate(model, facts)
    except Exception as e:
        _fail(f"フェルミ計算に失敗: {e}")
    artifact = Artifact(
        project=project,
        type="fermi",
        requirements_version=RequirementsStore(storage).latest_version(project),
        cited_facts=result.cited_facts,
        content=json.dumps(
            {"model": model.model_dump(mode="json"), "result": result.model_dump(mode="json")},
            ensure_ascii=False,
            indent=2,
        ),
    )
    artifact_id = ArtifactStore(storage).save(project, artifact)
    typer.echo(f"saved: {artifact_id}")
    typer.echo(f"{result.name} = {result.value}")


def main() -> None:
    """console_script のエントリーポイント。MEDO_TRACE 指定時は呼び出しを記録する。"""
    tracer = Tracer.from_env()
    code = 0
    try:
        app()
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        raise
    finally:
        if tracer:
            tracer.record(sys.argv[1:], exit_code=code)


if __name__ == "__main__":
    main()

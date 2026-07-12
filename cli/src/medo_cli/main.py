"""medo CLI。事実と計算の決定論的インターフェース。失敗時は推測せずエラーを返す。"""

import json
from pathlib import Path
from typing import Literal

import typer
import yaml
from medo_core.artifacts import Artifact, ArtifactStore
from medo_core.catalog import CatalogStore
from medo_core.config import get_storage
from medo_core.requirements import RequirementsDoc, RequirementsStore

app = typer.Typer(no_args_is_help=True, help="Medo(目処) — Google Cloud上流工程Agent CLI")
requirements_app = typer.Typer(no_args_is_help=True)
catalog_app = typer.Typer(no_args_is_help=True)
artifacts_app = typer.Typer(no_args_is_help=True)
app.add_typer(requirements_app, name="requirements", help="要件ドキュメント(バージョン管理)")
app.add_typer(catalog_app, name="catalog", help="鮮度メタ付きカタログ照会")
app.add_typer(artifacts_app, name="artifacts", help="生成物の保存・一覧")


def _fail(reason: str) -> None:
    typer.echo(f"error: {reason}", err=True)
    raise typer.Exit(code=1)


@requirements_app.command("save")
def requirements_save(
    project: str = typer.Option(...),
    file: Path = typer.Option(..., exists=True, readable=True),
):
    try:
        data = yaml.safe_load(file.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("YAMLのトップレベルはマッピングである必要があります")
        doc = RequirementsDoc.model_validate({**data, "project": project})
    except Exception as e:  # yaml.YAMLError, ValueError, pydantic.ValidationError
        _fail(f"要件のスキーマ不正: {e}")
    version = RequirementsStore(get_storage()).save(project, doc)
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
        for f in doc.functional:
            typer.echo(f"  - [{f.confidence}] {f.text}")
        for q in doc.open_questions:
            typer.echo(f"  ? {q}")


@requirements_app.command("diff")
def requirements_diff(project: str = typer.Option(...)):
    storage = get_storage()
    req_store = RequirementsStore(storage)
    current = req_store.latest_version(project)
    if current == 0:
        _fail(f"プロジェクト '{project}' の要件が見つかりません")
    stale = ArtifactStore(storage).stale_artifacts(project, current)
    typer.echo(
        json.dumps(
            {
                "requirements": req_store.diff(project),
                "stale_artifacts": [f"{a.type}-v{a.version}" for a in stale],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _entry_payload(entry) -> dict:
    return {"entry": entry.model_dump(mode="json"), "stale": entry.is_stale()}


@catalog_app.command("search")
def catalog_search(
    query: str = typer.Argument(""),
    service: str | None = typer.Option(None),
    limit: int = typer.Option(10),
    format: Literal["json", "digest"] = typer.Option("digest"),
):
    entries = CatalogStore(get_storage()).search(query, service=service, limit=limit)
    if format == "json":
        typer.echo(json.dumps([_entry_payload(e) for e in entries], ensure_ascii=False, indent=2))
        return
    if not entries:
        typer.echo("(該当なし)")
        return
    for e in entries:
        stale = " [STALE]" if e.is_stale() else ""
        typer.echo(f"{e.entry_id} [{e.launch_stage}]{stale} {e.summary[:60]}")


@catalog_app.command("get")
def catalog_get(
    service: str,
    feature: str,
    format: Literal["json", "digest"] = typer.Option("json"),
):
    entry = CatalogStore(get_storage()).get(service, feature)
    if entry is None:
        _fail(f"カタログに {service}/{feature} が見つかりません")
    if format == "json":
        typer.echo(json.dumps(_entry_payload(entry), ensure_ascii=False, indent=2))
        return
    stale = " [STALE]" if entry.is_stale() else ""
    typer.echo(f"{entry.entry_id} [{entry.launch_stage}]{stale} {entry.summary[:60]}")


@artifacts_app.command("save")
def artifacts_save(
    project: str = typer.Option(...),
    artifact_type: str = typer.Option(..., "--type"),
    file: Path = typer.Option(..., exists=True, readable=True),
    cites: str = typer.Option("", help="引用カタログエントリID(カンマ区切り)"),
    generated_by: str | None = typer.Option(None),
    requirements_version: int = typer.Option(...),
):
    try:
        artifact = Artifact(
            project=project,
            type=artifact_type,
            requirements_version=requirements_version,
            cited_catalog_entries=[c for c in cites.split(",") if c],
            generated_by=generated_by,
            content=file.read_text(encoding="utf-8"),
        )
    except Exception as e:
        _fail(f"生成物のスキーマ不正: {e}")
    artifact_id = ArtifactStore(get_storage()).save(project, artifact)
    typer.echo(f"saved: {artifact_id}")


@artifacts_app.command("list")
def artifacts_list(project: str = typer.Option(...)):
    items = ArtifactStore(get_storage()).list(project)
    for a in items:
        by = f" by {a.generated_by}" if a.generated_by else ""
        typer.echo(f"{a.type}-v{a.version} (req v{a.requirements_version}){by}")
    if not items:
        typer.echo("(生成物なし)")


if __name__ == "__main__":
    app()

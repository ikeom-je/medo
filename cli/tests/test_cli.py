import json
from pathlib import Path

import pytest
from medo_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()


# Medoの実際のユースケース(AI/ML活用によるGCPアーキ提案)をfixtureに反映する。
# 飲食店がインバウンド客の電話予約に対応しきれず、多言語AI音声応対と
# ノーショウ予測でGCPのAI/ML機能を活用したい、という具体案件を想定する。
REQ_YAML = """\
project: yoyaku
goal: 飲食店の多言語対応AI自動音声予約システム
background: インバウンド客の増加と人手不足が同時進行
principles:
  - text: 地域の食文化を海外客に開く
    confidence: confirmed
challenges:
  - text: 外国語の電話予約に対応できず機会損失
    confidence: confirmed
industry: 飲食
functional:
  - text: ネット予約とLINE通知
    confidence: confirmed
  - text: 多言語対応AIエージェントによる電話予約の自動応対・空席照会
    confidence: confirmed
  - text: 過去の予約データに基づくノーショウ(無断キャンセル)確率の事前予測
    confidence: assumed
non_functional:
  performance: 音声応対のレスポンスを2秒以内に抑える
  budget_cap: 月額ランニングコストを低く抑える
open_questions:
  - ピーク時の同時電話着信数は?
  - 既存のPOSシステムや座席管理システムとの連携APIは存在するか?
"""

ENTRY = {
    "service": "vertex-ai",
    "feature": "context-caching",
    "launch_stage": "GA",
    "since": "2025-11-01",
    "summary": "電話応対のシステムプロンプト(店舗情報・予約ルール)をキャッシュし入力コストと応答遅延を削減",
    "pricing_refs": [],
    "caveats": [],
    "sources": ["https://cloud.google.com/vertex-ai/docs/release-notes"],
    "last_verified": "2020-01-01",
}


@pytest.fixture(autouse=True)
def medo_home(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MEDO_BACKEND", "local")
    monkeypatch.setenv("MEDO_HOME", str(tmp_path))
    return tmp_path


def _save_requirements(tmp_path: Path) -> None:
    f = tmp_path / "req.yaml"
    f.write_text(REQ_YAML, encoding="utf-8")
    result = runner.invoke(app, ["requirements", "save", "--project", "yoyaku", "--file", str(f)])
    assert result.exit_code == 0, result.output


def test_requirements_save_and_get(medo_home: Path):
    _save_requirements(medo_home)
    result = runner.invoke(app, ["requirements", "get", "--project", "yoyaku", "--format", "json"])
    assert result.exit_code == 0
    doc = json.loads(result.output)
    assert doc["goal"] == "飲食店の多言語対応AI自動音声予約システム" and doc["version"] == 1


def test_requirements_get_missing_project_fails(medo_home: Path):
    result = runner.invoke(app, ["requirements", "get", "--project", "nashi"])
    assert result.exit_code == 1
    assert "error:" in result.output


def test_catalog_search_marks_stale(medo_home: Path):
    from medo_core.catalog import CatalogEntry, CatalogStore
    from medo_core.storage import LocalJsonStorage

    CatalogStore(LocalJsonStorage(medo_home)).upsert(CatalogEntry(**ENTRY))
    result = runner.invoke(app, ["catalog", "search", "caching", "--format", "json"])
    assert result.exit_code == 0
    items = json.loads(result.output)
    assert items[0]["entry"]["feature"] == "context-caching"
    assert items[0]["stale"] is True


def test_catalog_get_digest_and_json_format(medo_home: Path):
    from medo_core.catalog import CatalogEntry, CatalogStore
    from medo_core.storage import LocalJsonStorage

    CatalogStore(LocalJsonStorage(medo_home)).upsert(CatalogEntry(**ENTRY))

    result = runner.invoke(app, ["catalog", "get", "vertex-ai", "context-caching", "--format", "digest"])
    assert result.exit_code == 0
    assert "vertex-ai__context-caching" in result.output
    assert "[STALE]" in result.output

    result = runner.invoke(app, ["catalog", "get", "vertex-ai", "context-caching", "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["entry"]["feature"] == "context-caching"


def test_requirements_get_invalid_format_fails(medo_home: Path):
    _save_requirements(medo_home)
    result = runner.invoke(app, ["requirements", "get", "--project", "yoyaku", "--format", "yaml"])
    assert result.exit_code != 0


def test_requirements_get_digest_shows_business_context(medo_home: Path):
    _save_requirements(medo_home)
    result = runner.invoke(app, ["requirements", "get", "--project", "yoyaku", "--format", "digest"])
    assert result.exit_code == 0
    assert "課題 [confirmed] 外国語の電話予約に対応できず機会損失" in result.output
    assert "理念 [confirmed] 地域の食文化を海外客に開く" in result.output


def test_requirements_save_invalid_yaml_fails(medo_home: Path):
    f = medo_home / "bad.yaml"
    f.write_text("- just\n- a\n- list\n", encoding="utf-8")
    result = runner.invoke(app, ["requirements", "save", "--project", "yoyaku", "--file", str(f)])
    assert result.exit_code == 1
    assert "error:" in result.output


def test_catalog_get_missing_entry_fails(medo_home: Path):
    result = runner.invoke(app, ["catalog", "get", "vertex-ai", "nashi"])
    assert result.exit_code == 1
    assert "error:" in result.output


def test_requirements_diff_missing_project_fails(medo_home: Path):
    result = runner.invoke(app, ["requirements", "diff", "--project", "nashi"])
    assert result.exit_code == 1
    assert "error:" in result.output


def test_facts_save_and_list_with_stale_flag(medo_home: Path):
    result = runner.invoke(
        app,
        [
            "facts", "save", "--project", "yoyaku", "--kind", "market",
            "--statement", "訪日外国人旅行者数 3,687万人", "--value", "36870000",
            "--unit", "人", "--source", "https://www.jnto.go.jp/statistics/",
            "--retrieved", "2020-01-01",
        ],
    )
    assert result.exit_code == 0 and "fact-1" in result.output

    result = runner.invoke(app, ["facts", "list", "--project", "yoyaku", "--format", "json"])
    items = json.loads(result.output)
    assert items[0]["fact"]["fact_id"] == "fact-1"
    assert items[0]["stale"] is True


def test_facts_save_rejects_non_url_source_for_market(medo_home: Path):
    result = runner.invoke(
        app,
        [
            "facts", "save", "--project", "yoyaku", "--kind", "market",
            "--statement", "x", "--source", "ヒアリングで聞いた",
        ],
    )
    assert result.exit_code == 1
    assert "error:" in result.output


def test_artifacts_list_empty_and_after_save(medo_home: Path):
    result = runner.invoke(app, ["artifacts", "list", "--project", "yoyaku"])
    assert result.exit_code == 0
    assert "(生成物なし)" in result.output

    _save_requirements(medo_home)
    arch = medo_home / "arch.md"
    arch.write_text(
        "# 案A: 多言語AI音声予約\n"
        "店舗情報・予約ルールをVertex AI Context Cachingに保持し、"
        "Geminiで多言語音声応対の入力コストと遅延を削減する。\n",
        encoding="utf-8",
    )
    runner.invoke(
        app,
        [
            "artifacts", "save", "--project", "yoyaku", "--type", "architecture",
            "--file", str(arch), "--generated-by", "claude",
            "--requirements-version", "1",
        ],
    )
    result = runner.invoke(app, ["artifacts", "list", "--project", "yoyaku"])
    assert result.exit_code == 0
    assert "architecture-v1" in result.output


def test_artifacts_save_and_diff_flow(medo_home: Path):
    _save_requirements(medo_home)
    arch = medo_home / "arch.md"
    arch.write_text(
        "# 案A: 多言語AI音声予約\n"
        "店舗情報・予約ルールをVertex AI Context Cachingに保持し、"
        "Geminiで多言語音声応対の入力コストと遅延を削減する。\n",
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        [
            "artifacts", "save", "--project", "yoyaku", "--type", "architecture",
            "--file", str(arch), "--cites", "vertex-ai__context-caching",
            "--generated-by", "claude", "--requirements-version", "1",
        ],
    )
    assert result.exit_code == 0 and "architecture-v1" in result.output

    _save_requirements(medo_home)  # v2を保存 → v1依存のarchitectureが陳腐化
    result = runner.invoke(app, ["requirements", "diff", "--project", "yoyaku"])
    assert result.exit_code == 0
    d = json.loads(result.output)
    assert d["requirements"]["to"] == 2
    assert d["stale_artifacts"] == ["architecture-v1"]


def test_artifacts_save_mini_prfaq_and_get(medo_home: Path):
    _save_requirements(medo_home)
    doc = medo_home / "options.md"
    doc.write_text("# 打ち手候補セット", encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "artifacts", "save", "--project", "yoyaku", "--type", "mini-prfaq",
            "--file", str(doc), "--cites-facts", "fact-1",
            "--options", "多言語AI音声予約:業務改革,予約代行:既存解決",
            "--generated-by", "claude",
            "--requirements-version", "1",
        ],
    )
    assert result.exit_code == 0 and "mini-prfaq-v1" in result.output

    result = runner.invoke(
        app, ["artifacts", "get", "--project", "yoyaku", "--id", "mini-prfaq-v1"]
    )
    payload = json.loads(result.output)
    assert payload["options"][0]["name"] == "多言語AI音声予約"
    assert payload["cited_facts"] == ["fact-1"]


def test_artifacts_save_prfaq_requires_grown_from(medo_home: Path):
    _save_requirements(medo_home)
    doc = medo_home / "prfaq.md"
    doc.write_text("# PRFAQ", encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "artifacts", "save", "--project", "yoyaku", "--type", "prfaq",
            "--file", str(doc), "--generated-by", "claude",
            "--requirements-version", "1",
        ],
    )
    assert result.exit_code == 1 and "error:" in result.output

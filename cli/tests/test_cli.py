import json
from pathlib import Path

import pytest
from medo_cli.main import app
from typer.testing import CliRunner

runner = CliRunner()


# Medoの実際のユースケース(AI/ML活用によるアーキ提案)をfixtureに反映する。
# 飲食店がインバウンド客の電話予約に対応しきれず、多言語AI音声応対と
# ノーショウ予測でAI/ML機能を活用したい、という具体案件を想定する。
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
    "kind": "tech",
    "statement": "電話応対のcontext cachingで入力コストと応答遅延を削減",
    "source": "https://cloud.google.com/vertex-ai/docs/release-notes",
    "retrieved": "2020-01-01",
}

FERMI_YAML = """\
name: 多言語予約対応の市場機会
variables:
  visitors: {fact: fact-1}
  dining_rate: {assume: 0.8}
formula: visitors * dining_rate
"""


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


def _save_minimal_requirements(tmp_path: Path, project: str) -> None:
    doc = {"project": project}
    f = tmp_path / f"{project}-req.json"
    f.write_text(json.dumps(doc), encoding="utf-8")
    result = runner.invoke(
        app, ["requirements", "save", "--project", project, "--file", str(f)]
    )
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


def test_knowledge_search_marks_stale(medo_home: Path):
    from medo_core.knowledge import KnowledgeEntry, KnowledgeStore

    KnowledgeStore(medo_home / "knowledge").save(KnowledgeEntry(**ENTRY))
    result = runner.invoke(app, ["knowledge", "search", "caching", "--format", "json"])
    assert result.exit_code == 0
    items = json.loads(result.output)
    assert items[0]["entry"]["statement"].startswith("電話応対")
    assert items[0]["stale"] is True


def test_knowledge_get_digest_and_json_format(medo_home: Path):
    from medo_core.knowledge import KnowledgeEntry, KnowledgeStore

    KnowledgeStore(medo_home / "knowledge").save(KnowledgeEntry(**ENTRY))

    result = runner.invoke(
        app, ["knowledge", "get", "--kind", "tech", "--id", "tech-1", "--format", "digest"]
    )
    assert result.exit_code == 0
    assert "tech-1" in result.output
    assert "[STALE]" in result.output

    result = runner.invoke(
        app, ["knowledge", "get", "--kind", "tech", "--id", "tech-1", "--format", "json"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["entry"]["statement"].startswith("電話応対")


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


def test_knowledge_get_missing_entry_fails(medo_home: Path):
    result = runner.invoke(app, ["knowledge", "get", "--kind", "tech", "--id", "nashi"])
    assert result.exit_code == 1
    assert "error:" in result.output


def test_knowledge_save_project_scope_and_search(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDO_HOME", str(tmp_path))
    result = runner.invoke(
        app,
        [
            "knowledge", "save",
            "--project", "yoyaku",
            "--statement", "顧客の予約システムは現在Excel管理",
            "--source", "hearing Skill 2026-07-27対話",
        ],
    )
    assert result.exit_code == 0
    assert "saved: yoyaku-1" in result.stdout

    search = runner.invoke(app, ["knowledge", "search", "Excel", "--project", "yoyaku"])
    assert search.exit_code == 0
    assert "yoyaku-1" in search.stdout


def test_knowledge_save_project_scope_rejects_missing_source(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDO_HOME", str(tmp_path))
    result = runner.invoke(
        app, ["knowledge", "save", "--project", "yoyaku", "--statement", "x", "--source", ""]
    )
    assert result.exit_code == 1
    assert "error:" in result.stdout + result.stderr


def test_requirements_diff_missing_project_fails(medo_home: Path):
    result = runner.invoke(app, ["requirements", "diff", "--project", "nashi"])
    assert result.exit_code == 1
    assert "error:" in result.output


def test_status_flow_next_steps(medo_home: Path):
    result = runner.invoke(app, ["status", "--project", "yoyaku"])
    assert result.exit_code == 0
    assert json.loads(result.output)["next_step"] == "hearing"

    _save_requirements(medo_home)
    result = runner.invoke(app, ["status", "--project", "yoyaku"])
    assert json.loads(result.output)["next_step"] == "propose-options"


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


def test_artifacts_save_accepts_derived_from_and_slide_kind(tmp_path):
    _save_requirements(tmp_path)
    content = tmp_path / "report.md"
    content.write_text("# 現状", encoding="utf-8")
    runner.invoke(app, [
        "artifacts", "save", "--project", "yoyaku", "--type", "as-is-report",
        "--requirements-version", "1", "--generated-by", "claude", "--file", str(content),
    ])
    slides = tmp_path / "slides.md"
    slides.write_text("---\nmarp: true\n---\n# 現状", encoding="utf-8")

    result = runner.invoke(app, [
        "artifacts", "save", "--project", "yoyaku", "--type", "slides",
        "--slide-kind", "discussion", "--derived-from", "as-is-report-v1",
        "--requirements-version", "1", "--generated-by", "gemini", "--file", str(slides),
    ])

    assert result.exit_code == 0
    assert "saved: slides-v1" in result.stdout


def test_artifacts_save_rejects_slides_without_slide_kind(tmp_path):
    _save_requirements(tmp_path)
    slides = tmp_path / "slides.md"
    slides.write_text("# x", encoding="utf-8")

    result = runner.invoke(app, [
        "artifacts", "save", "--project", "yoyaku", "--type", "slides",
        "--requirements-version", "1", "--generated-by", "claude", "--file", str(slides),
    ])

    assert result.exit_code == 1
    assert "slide_kind" in result.stderr


def test_artifacts_save_records_covered_challenges(tmp_path):
    _save_requirements(tmp_path)
    content = tmp_path / "c.md"
    content.write_text("# 比較", encoding="utf-8")

    result = runner.invoke(app, [
        "artifacts", "save", "--project", "yoyaku", "--type", "comparison",
        "--covers", "ch-1,ch-2", "--requirements-version", "1",
        "--generated-by", "claude", "--file", str(content),
    ])

    assert result.exit_code == 0


def test_fermi_calc_saves_artifact_and_recalcs(medo_home: Path):
    _save_requirements(medo_home)
    runner.invoke(
        app,
        [
            "facts", "save", "--project", "yoyaku", "--kind", "market",
            "--statement", "訪日客数", "--value", "36870000",
            "--source", "https://www.jnto.go.jp/statistics/",
        ],
    )
    model = medo_home / "model.yaml"
    model.write_text(FERMI_YAML, encoding="utf-8")

    result = runner.invoke(app, ["fermi", "calc", "--project", "yoyaku", "--file", str(model)])
    assert result.exit_code == 0, result.output
    assert "fermi-v1" in result.output and "29496000" in result.output

    result = runner.invoke(app, ["fermi", "calc", "--project", "yoyaku", "--from-artifact", "fermi-v1"])
    assert result.exit_code == 0 and "fermi-v2" in result.output


def test_fermi_calc_missing_fact_fails(medo_home: Path):
    _save_requirements(medo_home)
    model = medo_home / "model.yaml"
    model.write_text(FERMI_YAML, encoding="utf-8")
    result = runner.invoke(app, ["fermi", "calc", "--project", "yoyaku", "--file", str(model)])
    assert result.exit_code == 1 and "error:" in result.output


def test_requirements_save_accepts_new_sections(tmp_path):
    doc = {
        "project": "p1",
        "as_is": [{"text": "紙の伝票を手入力", "visibility": "internal"}],
    }
    f = tmp_path / "req.json"
    f.write_text(json.dumps(doc), encoding="utf-8")

    result = runner.invoke(app, ["requirements", "save", "--project", "p1", "--file", str(f)])

    assert result.exit_code == 0
    assert "saved: v1" in result.stdout


def test_requirements_save_reports_validation_error_without_guessing(tmp_path):
    doc = {"project": "p1", "gaps": [{"text": "乖離", "from_as_is": ["as-99"]}]}
    f = tmp_path / "req.json"
    f.write_text(json.dumps(doc), encoding="utf-8")

    result = runner.invoke(app, ["requirements", "save", "--project", "p1", "--file", str(f)])

    assert result.exit_code == 1
    assert "as-99" in result.stderr


def test_requirements_save_declares_editorial_sections(tmp_path):
    doc = {"project": "p1", "to_be": [{"text": "自動化"}]}
    f = tmp_path / "req.json"
    f.write_text(json.dumps(doc), encoding="utf-8")
    runner.invoke(app, ["requirements", "save", "--project", "p1", "--file", str(f)])

    saved = json.loads(f.read_text(encoding="utf-8"))
    saved["to_be"] = [{"id": "tb-1", "text": "自動化されている"}]
    f.write_text(json.dumps(saved), encoding="utf-8")
    result = runner.invoke(
        app,
        [
            "requirements",
            "save",
            "--project",
            "p1",
            "--file",
            str(f),
            "--editorial",
            "to_be",
        ],
    )

    assert result.exit_code == 0
    assert "saved: v2" in result.stdout


def test_check_add_records_result(tmp_path):
    _save_minimal_requirements(tmp_path, "p1")

    result = runner.invoke(app, [
        "check", "add", "--project", "p1", "--check", "reality_gap", "--result", "completed",
    ])

    assert result.exit_code == 0
    assert "recorded: ev-" in result.stdout


def test_check_add_rejects_undeterminable_without_note(tmp_path):
    _save_minimal_requirements(tmp_path, "p1")

    result = runner.invoke(app, [
        "check", "add", "--project", "p1", "--check", "to_be_articulation",
        "--result", "undeterminable",
    ])

    assert result.exit_code == 1
    assert "note" in result.stderr


def test_check_add_accepts_disposition(tmp_path):
    _save_minimal_requirements(tmp_path, "p1")

    result = runner.invoke(app, [
        "check", "add", "--project", "p1", "--check", "to_be_articulation",
        "--result", "undeterminable", "--note", "方向性が未定",
        "--disposition", "promoted",
    ])

    assert result.exit_code == 0


def test_respond_add_rejects_unknown_stakeholder(tmp_path):
    _save_minimal_requirements(tmp_path, "p1")

    result = runner.invoke(app, [
        "respond", "add", "--project", "p1", "--stakeholder", "sh-99",
        "--purpose", "to_be_go_ahead", "--reaction", "agreed",
    ])

    assert result.exit_code == 1
    assert "sh-99" in result.stderr


def test_checkpoint_answer_requires_existing_milestone(tmp_path):
    _save_minimal_requirements(tmp_path, "p1")

    result = runner.invoke(app, [
        "checkpoint", "answer", "--project", "p1", "--responds-to", "ev-99",
        "--answer", "generate",
    ])

    assert result.exit_code == 1


def test_requirements_save_records_milestone_through_cli(tmp_path):
    """実利用の経路で節目が記録されないと、actionsが機能しない。"""
    from medo_core.config import get_storage
    from medo_core.events import EventStore

    doc = {"project": "p1", "as_is": [{"text": "実態", "visibility": "internal"}]}
    f = tmp_path / "req.json"
    f.write_text(json.dumps(doc), encoding="utf-8")
    runner.invoke(app, ["requirements", "save", "--project", "p1", "--file", str(f)])

    events = EventStore(get_storage()).list("p1")

    assert [event.condition for event in events if event.kind == "milestone"] == [
        "internal_as_is_first_added"
    ]

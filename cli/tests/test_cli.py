import json
from datetime import date
from pathlib import Path

import pytest
from medo_cli.main import app
from medo_core.facts import Fact, FactStore, Verification
from medo_core.storage import LocalJsonStorage
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
    payload = json.loads(result.output)
    assert payload["entries"][0]["entry"]["statement"].startswith("電話応対")
    assert payload["entries"][0]["stale"] is True
    assert payload["truncated"] is False


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


def test_status_counts_facts_without_requirements(medo_home: Path, monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 7, 12)

    monkeypatch.setattr("medo_core.facts.date", FixedDate)
    storage = LocalJsonStorage(medo_home)
    FactStore(storage).save("yoyaku", Fact(
        kind="market", statement="未検証", source="https://example.com",
        retrieved="2026-07-01", verification=Verification(status="unverified"),
    ))
    storage.put("projects/yoyaku/facts/fact-2", {
        "fact_id": "fact-2", "kind": "market", "statement": "旧データ",
        "source": "https://example.com", "retrieved": "2025-01-01",
    })

    result = runner.invoke(app, ["status", "--project", "yoyaku", "--format", "json"])

    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["requirements"] is None
    assert report["facts"] == {"count": 2, "stale": 1, "unverified": 1, "legacy": 1}
    assert report["artifacts"] == []
    assert report["next_step"] == "hearing"


def test_status_readiness_view_includes_the_phase_judgement(medo_home: Path):
    """Skillは1回の呼び出しでフェーズ完了の可否まで読む。"""
    _save_requirements(medo_home)

    result = runner.invoke(app, [
        "status", "--project", "yoyaku", "--view", "readiness", "--format", "json",
    ])

    assert result.exit_code == 0
    assert "phase" in json.loads(result.output)["readiness"]


def test_research_plan_outputs_profile_aspects_stop_conditions_and_findings(medo_home: Path):
    _save_minimal_requirements(medo_home, "research-project")

    result = runner.invoke(
        app,
        ["research", "plan", "--project", "research-project", "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    plan = json.loads(result.output)
    assert plan["profile"]["name"] == "structural"
    assert plan["aspects"][0]["name"] == "actor_org"
    assert plan["stop_conditions"]
    assert plan["findings_to_resolve"] == {"links": {}, "coverage": {}}


def test_research_triage_returns_unjudged_candidates_when_typesafe_is_unavailable(
    medo_home: Path, monkeypatch: pytest.MonkeyPatch
):
    from medo_cli.commands import research as research_commands

    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.setattr(
        research_commands,
        "judge_candidates",
        lambda *_: pytest.fail("TYPESAFE_API_KEY がなければJevを呼ばない"),
    )
    candidates = medo_home / "candidates.json"
    candidates.write_text(
        json.dumps([{"url": "https://example.com", "title": "候補"}]), encoding="utf-8"
    )

    result = runner.invoke(
        app,
        ["research", "triage", "--project", "research-project", "--file", str(candidates)],
    )

    assert result.exit_code == 0, result.output
    assert "judge: unavailable" in result.output
    assert "https://example.com" in result.output


def test_facts_save_and_list_with_stale_flag(medo_home: Path, monkeypatch):
    from medo_cli import main
    from medo_cli.fetch import FetchResult

    monkeypatch.setattr(main, "fetch_body", lambda *_: FetchResult(body="訪日外国人旅行者数 3,687万人"))
    monkeypatch.setattr(main, "judge_support", lambda *_: "supported")
    result = runner.invoke(
        app,
        [
            "facts", "save", "--project", "yoyaku", "--kind", "market",
            "--statement", "訪日外国人旅行者数 3,687万人", "--value", "36870000",
            "--unit", "人", "--source", "https://www.jnto.go.jp/statistics/",
            "--retrieved", "2020-01-01", "--quote", "訪日外国人旅行者数 3,687万人",
        ],
    )
    assert result.exit_code == 0 and "fact-1" in result.output

    result = runner.invoke(app, ["facts", "list", "--project", "yoyaku", "--format", "json"])
    items = json.loads(result.output)
    assert items[0]["fact"]["fact_id"] == "fact-1"
    assert items[0]["fact"]["verification"]["status"] == "verified"
    assert items[0]["verification"]["support"] == "supported"
    assert items[0]["stale"] is True
    digest = runner.invoke(app, ["facts", "list", "--project", "yoyaku"])
    assert "[STALE]" in digest.output


def test_facts_digest_marks_legacy_and_doubtful(medo_home: Path):
    storage = LocalJsonStorage(medo_home)
    storage.put("projects/yoyaku/facts/fact-1", {
        "fact_id": "fact-1", "kind": "market", "statement": "旧データ",
        "source": "https://example.com", "retrieved": "2026-07-01",
    })
    FactStore(storage).save("yoyaku", Fact(
        fact_id="fact-2", kind="market", statement="要確認データ", quote="3人",
        source="https://example.com", retrieved="2026-07-01",
        verification=Verification(status="verified", support="doubtful"),
    ))
    result = runner.invoke(app, ["facts", "list", "--project", "yoyaku"])
    assert "fact-1 [market] [LEGACY]" in result.output
    assert "fact-2 [market] [DOUBTFUL]" in result.output


def test_company_save_is_not_applicable(medo_home: Path, monkeypatch):
    from medo_cli import main

    monkeypatch.setattr(main, "fetch_body", lambda *_: pytest.fail("company は取得しない"))
    result = runner.invoke(app, [
        "facts", "save", "--project", "yoyaku", "--kind", "company",
        "--statement", "月間予約数", "--source", "ヒアリング",
    ])
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["facts", "list", "--project", "yoyaku", "--format", "json"])
    assert json.loads(result.output)[0]["verification"]["status"] == "not-applicable"


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


def test_facts_save_requires_quote_for_url_kind(medo_home: Path):
    result = runner.invoke(app, [
        "facts", "save", "--project", "yoyaku", "--kind", "market",
        "--statement", "市場規模", "--source", "https://example.com",
    ])
    assert result.exit_code != 0 and "--quote" in result.output


def test_facts_save_declared_unverifiable_skips_fetch(medo_home: Path, monkeypatch):
    from medo_cli import main

    monkeypatch.setattr(main, "fetch_body", lambda *_: pytest.fail("取得しない"))
    result = runner.invoke(app, [
        "facts", "save", "--project", "yoyaku", "--kind", "policy",
        "--statement", "政策を公表", "--source", "https://example.com",
        "--quote", "政策を公表", "--unverifiable-reason", "PDF抽出不良",
    ])
    assert result.exit_code == 0, result.output
    saved = FactStore(LocalJsonStorage(medo_home)).list("yoyaku")[0]
    assert saved.verification.reason == "declared: PDF抽出不良"


def test_facts_save_rejects_empty_unverifiable_reason(medo_home: Path):
    result = runner.invoke(app, [
        "facts", "save", "--project", "yoyaku", "--kind", "policy",
        "--statement", "政策を公表", "--source", "https://example.com",
        "--quote", "政策を公表", "--unverifiable-reason", " ",
    ])
    assert result.exit_code != 0 and "--unverifiable-reason" in result.output


def test_facts_save_fetch_failure_warns_and_saves_unverified(medo_home: Path, monkeypatch):
    from medo_cli import main
    from medo_cli.fetch import FetchResult

    monkeypatch.setattr(main, "fetch_body", lambda *_: FetchResult(reason="HTTP 403"))
    result = runner.invoke(app, [
        "facts", "save", "--project", "yoyaku", "--kind", "trend",
        "--statement", "市場拡大", "--source", "https://example.com", "--quote", "市場拡大",
    ])
    assert result.exit_code == 0 and "warning:" in result.output
    saved = FactStore(LocalJsonStorage(medo_home)).list("yoyaku")[0]
    assert saved.verification.reason == "fetch-failed: HTTP 403"


def test_facts_save_rejects_mismatched_quote_with_remedy(medo_home: Path, monkeypatch):
    from medo_cli import main
    from medo_cli.fetch import FetchResult

    monkeypatch.setattr(main, "fetch_body", lambda *_: FetchResult(body="市場規模は3.3兆円(2024年)"))
    result = runner.invoke(app, [
        "facts", "save", "--project", "yoyaku", "--kind", "market",
        "--statement", "市場規模は3.2兆円", "--value", "3.2", "--unit", "兆円",
        "--source", "https://example.com", "--quote", "市場規模は3.2兆円(2024年)",
    ])
    assert result.exit_code != 0
    assert "本文" in result.output and "近い箇所" in result.output
    assert "--unverifiable-reason" in result.output
    assert FactStore(LocalJsonStorage(medo_home)).list("yoyaku") == []


def test_facts_save_warns_for_doubtful_and_unjudged(medo_home: Path, monkeypatch):
    from medo_cli import main
    from medo_cli.fetch import FetchResult

    monkeypatch.setattr(main, "fetch_body", lambda *_: FetchResult(body="市場規模は3.2兆円"))
    args = ["facts", "save", "--project", "yoyaku", "--kind", "market",
            "--statement", "市場規模は3.2兆円", "--value", "3.2", "--unit", "兆円",
            "--source", "https://example.com", "--quote", "市場規模は3.2兆円"]
    monkeypatch.setattr(main, "judge_support", lambda *_: "doubtful")
    doubtful = runner.invoke(app, args)
    assert doubtful.exit_code == 0 and "warning:" in doubtful.output
    monkeypatch.setattr(main, "judge_support", lambda *_: (_ for _ in ()).throw(RuntimeError("timeout")))
    unjudged = runner.invoke(app, args)
    assert unjudged.exit_code == 0 and "timeout" in unjudged.output
    facts = FactStore(LocalJsonStorage(medo_home)).list("yoyaku")
    assert [fact.verification.support for fact in facts] == ["doubtful", "unjudged"]


def test_facts_save_rejects_value_missing_from_matching_quote(medo_home: Path, monkeypatch):
    from medo_cli import main
    from medo_cli.fetch import FetchResult

    monkeypatch.setattr(main, "fetch_body", lambda *_: FetchResult(body="市場規模は3.3兆円"))
    result = runner.invoke(app, [
        "facts", "save", "--project", "yoyaku", "--kind", "market",
        "--statement", "市場規模は3.2兆円", "--value", "3.2", "--unit", "兆円",
        "--source", "https://example.com", "--quote", "市場規模は3.3兆円",
    ])
    assert result.exit_code != 0
    assert "一致する数値" in result.output and "--unverifiable-reason" in result.output


def test_facts_verify_legacy_preserves_fact_data(medo_home: Path, monkeypatch):
    from medo_cli import main
    from medo_cli.fetch import FetchResult

    storage = LocalJsonStorage(medo_home)
    original = {
        "fact_id": "fact-1", "kind": "market", "statement": "市場規模は3.2兆円",
        "value": 3.2, "unit": "兆円", "source": "https://example.com",
        "retrieved": "2026-07-01", "note": "旧データ",
    }
    storage.put("projects/yoyaku/facts/fact-1", original)
    monkeypatch.setattr(main, "fetch_body", lambda *_: FetchResult(body="市場規模は3.2兆円"))
    monkeypatch.setattr(main, "judge_support", lambda *_: "supported")

    result = runner.invoke(app, [
        "facts", "verify", "--project", "yoyaku", "--fact", "fact-1",
        "--quote", "市場規模は3.2兆円",
    ])

    assert result.exit_code == 0, result.output
    assert result.output.strip() == "verified: fact-1"
    saved = storage.get("projects/yoyaku/facts/fact-1")
    assert all(saved[key] == value for key, value in original.items())
    assert saved["quote"] == "市場規模は3.2兆円"
    assert saved["verification"]["status"] == "verified"
    assert saved["verification"]["support"] == "supported"
    assert len(storage.list("projects/yoyaku/facts")) == 1


def test_facts_verify_fetch_failure_saves_unverified(medo_home: Path, monkeypatch):
    from medo_cli import main
    from medo_cli.fetch import FetchResult

    storage = LocalJsonStorage(medo_home)
    storage.put("projects/yoyaku/facts/fact-1", {
        "fact_id": "fact-1", "kind": "trend", "statement": "市場拡大",
        "source": "https://example.com", "retrieved": "2026-07-01",
        "quote": "旧抜粋", "verification": {
            "status": "unverified", "reason": "fetch-failed: old",
        },
    })
    monkeypatch.setattr(main, "fetch_body", lambda *_: FetchResult(reason="HTTP 403"))

    result = runner.invoke(app, [
        "facts", "verify", "--project", "yoyaku", "--fact", "fact-1",
        "--quote", "市場拡大",
    ])

    assert result.exit_code == 0, result.output
    assert "unverified: fact-1 (fetch-failed: HTTP 403)" in result.output
    saved = storage.get("projects/yoyaku/facts/fact-1")
    assert saved["quote"] == "市場拡大"
    assert saved["verification"]["reason"] == "fetch-failed: HTTP 403"


def test_facts_verify_mismatched_quote_preserves_legacy(medo_home: Path, monkeypatch):
    from medo_cli import main
    from medo_cli.fetch import FetchResult

    storage = LocalJsonStorage(medo_home)
    original = {
        "fact_id": "fact-1", "kind": "market", "statement": "市場規模は3.2兆円",
        "value": 3.2, "unit": "兆円", "source": "https://example.com",
        "retrieved": "2026-07-01",
    }
    storage.put("projects/yoyaku/facts/fact-1", original)
    monkeypatch.setattr(main, "fetch_body", lambda *_: FetchResult(body="市場規模は3.3兆円"))

    result = runner.invoke(app, [
        "facts", "verify", "--project", "yoyaku", "--fact", "fact-1",
        "--quote", "市場規模は3.2兆円",
    ])

    assert result.exit_code != 0
    assert "error:" in result.output and "本文中の近い箇所" in result.output
    assert storage.get("projects/yoyaku/facts/fact-1") == original
    assert FactStore(storage).get("yoyaku", "fact-1").verification.status == "legacy"


@pytest.mark.parametrize("state", ["verified", "company", "missing"])
def test_facts_verify_rejects_ineligible_fact(medo_home: Path, monkeypatch, state: str):
    from medo_cli import main

    storage = LocalJsonStorage(medo_home)
    original = {
        "fact_id": "fact-1", "kind": "company" if state == "company" else "market",
        "statement": "市場規模", "source": "ヒアリング" if state == "company" else "https://example.com",
        "retrieved": "2026-07-01",
    }
    if state == "verified":
        original["quote"] = "市場規模"
        original["verification"] = {"status": "verified"}
    if state != "missing":
        storage.put("projects/yoyaku/facts/fact-1", original)
    monkeypatch.setattr(main, "fetch_body", lambda *_: pytest.fail("取得しない"))

    result = runner.invoke(app, [
        "facts", "verify", "--project", "yoyaku", "--fact", "fact-1",
        "--quote", "市場規模",
    ])

    assert result.exit_code != 0 and "error:" in result.output
    if state != "missing":
        assert storage.get("projects/yoyaku/facts/fact-1") == original


def test_facts_verify_declared_unverifiable_saves_quote(medo_home: Path, monkeypatch):
    from medo_cli import main

    storage = LocalJsonStorage(medo_home)
    storage.put("projects/yoyaku/facts/fact-1", {
        "fact_id": "fact-1", "kind": "policy", "statement": "政策を公表",
        "source": "https://example.com", "retrieved": "2026-07-01",
    })
    monkeypatch.setattr(main, "fetch_body", lambda *_: pytest.fail("取得しない"))

    result = runner.invoke(app, [
        "facts", "verify", "--project", "yoyaku", "--fact", "fact-1",
        "--quote", "政策を公表", "--unverifiable-reason", "PDF抽出不良",
    ])

    assert result.exit_code == 0, result.output
    assert "unverified: fact-1 (declared: PDF抽出不良)" in result.output
    saved = storage.get("projects/yoyaku/facts/fact-1")
    assert saved["quote"] == "政策を公表"
    assert saved["verification"]["reason"] == "declared: PDF抽出不良"


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


def test_fermi_calc_saves_artifact_and_recalcs(medo_home: Path, monkeypatch):
    _save_requirements(medo_home)
    from medo_cli import main
    from medo_cli.fetch import FetchResult

    monkeypatch.setattr(main, "fetch_body", lambda *_: FetchResult(reason="HTTP 403"))
    runner.invoke(
        app,
        [
            "facts", "save", "--project", "yoyaku", "--kind", "market",
            "--statement", "訪日客数", "--value", "36870000",
            "--source", "https://www.jnto.go.jp/statistics/", "--quote", "訪日客数 36870000人",
        ],
    )
    model = medo_home / "model.yaml"
    model.write_text(FERMI_YAML, encoding="utf-8")

    result = runner.invoke(app, ["fermi", "calc", "--project", "yoyaku", "--file", str(model)])
    assert result.exit_code == 0, result.output
    assert "fermi-v1" in result.output and "29496000" in result.output
    assert "warning:" in result.output and "fact-1" in result.output

    saved = runner.invoke(app, ["artifacts", "get", "--project", "yoyaku", "--id", "fermi-v1"])
    content = json.loads(json.loads(saved.output)["content"])
    assert content["result"]["unverified_facts"] == ["fact-1"]
    assert content["result"]["doubtful_facts"] == []

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


def test_workflow_commands_are_available_after_split():
    """分割後もコマンド体系は変わらない(Skill契約を壊さない)。"""
    result = runner.invoke(app, ["check", "--help"])

    assert result.exit_code == 0


def test_requirements_template_saves_verbatim_without_creating_nodes(medo_home: Path):
    """雛形をそのまま保存できないと、Skillへの案内として成立しない。"""
    result = runner.invoke(app, ["requirements", "template"])
    assert result.exit_code == 0

    path = medo_home / "req.yaml"
    path.write_text(result.output, encoding="utf-8")
    saved = runner.invoke(app, ["requirements", "save", "--project", "p1", "--file", str(path)])
    assert saved.exit_code == 0 and "saved: v1" in saved.output

    status = runner.invoke(app, ["status", "--project", "p1"])
    assert json.loads(status.output)["diagnostic_phase"] == "discovery"


def test_requirements_template_needs_no_project(medo_home: Path):
    """まだ案件が無い状態で最初に呼ぶコマンドなので、案件IDを要求してはならない。"""
    assert runner.invoke(app, ["requirements", "template"]).exit_code == 0


def test_artifacts_outline_returns_the_discussion_chapters(medo_home: Path):
    result = runner.invoke(
        app, ["artifacts", "outline", "--type", "slides", "--slide-kind", "discussion"]
    )

    assert result.exit_code == 0 and "本日の検証テーマ" in result.output


def test_artifacts_outline_rejects_an_unknown_slide_kind(medo_home: Path):
    result = runner.invoke(
        app, ["artifacts", "outline", "--type", "slides", "--slide-kind", "poster"]
    )

    assert result.exit_code == 1 and "error:" in result.output


def test_artifacts_outline_returns_the_final_chapters(medo_home: Path):
    result = runner.invoke(
        app, ["artifacts", "outline", "--type", "slides", "--slide-kind", "final"]
    )

    assert result.exit_code == 0
    assert "SCQA" in result.output and "ネクストアクション" in result.output


def test_artifacts_outline_rejects_a_type_without_an_outline(medo_home: Path):
    result = runner.invoke(app, ["artifacts", "outline", "--type", "prfaq"])

    assert result.exit_code == 1 and "error:" in result.output


def test_check_list_reports_which_checks_need_an_artifact(medo_home: Path):
    """artifact束縛のcheckは --artifact なしでは拒否される。Skillは事前に知る必要がある。"""
    result = runner.invoke(app, ["check", "list", "--format", "json"])
    assert result.exit_code == 0

    by_name = {row["name"]: row for row in json.loads(result.output)}

    assert (
        by_name["as_is_articulation"]["binding"],
        by_name["as_is_articulation"]["target_type"],
        by_name["reality_gap"]["binding"],
    ) == ("artifact_bound", "as-is-report", "persistent")


def test_check_list_includes_shared_checks_when_filtering_by_customer(medo_home: Path):
    """confirmer=both は顧客にも確認する項目。完全一致で絞ると章6から漏れる。

    スライド設計は convergence 段階の投影対象に feasibility を挙げているが、
    registry 上の feasibility は both である。
    """
    result = runner.invoke(
        app, ["check", "list", "--confirmer", "customer", "--format", "json"]
    )

    assert [row["name"] for row in json.loads(result.output)] == [
        "engagement_scope",
        "reality_gap",
        "past_attempts",
        "hidden_stakeholders",
        "as_is_articulation",
        "decision_maker",
        "to_be_articulation",
        "feasibility",
        "scope_agreement",
    ]


def test_check_list_filtered_by_consultant_excludes_customer_only_checks(medo_home: Path):
    """customer 専用の3項目だけが落ち、both は残る。"""
    result = runner.invoke(
        app, ["check", "list", "--confirmer", "consultant", "--format", "json"]
    )
    names = {row["name"] for row in json.loads(result.output)}

    assert names & {"as_is_articulation", "to_be_articulation", "scope_agreement"} == set()
    assert {"source_quality", "expression_safety", "feasibility"} <= names


def test_check_list_digest_is_the_default(medo_home: Path):
    result = runner.invoke(app, ["check", "list"])

    assert result.exit_code == 0 and "as_is_articulation" in result.output


def test_check_list_rejects_an_unknown_confirmer(medo_home: Path):
    result = runner.invoke(app, ["check", "list", "--confirmer", "vendor"])

    assert result.exit_code == 1 and "error:" in result.output


def test_research_plan_reports_a_missing_project_as_an_error(medo_home: Path):
    """案件が未作成なら model 枝は返らない。生のトレースバックはCLIの契約違反。"""
    result = runner.invoke(app, ["research", "plan", "--project", "unknown"])

    assert result.exit_code == 1 and "error:" in result.output


def test_jev_score_is_normalized_to_the_verdict_contract():
    """scoreはレベル番号の範囲で返る(3段なら0〜2)。そのまま渡すとVerdictの検証で落ちる。"""
    from medo_cli.jev import _normalized_score

    answer = {"score": 1.6, "legend": {"0": "低", "1": "中", "2": "高"}}

    assert _normalized_score(answer) == 0.8


def test_triage_keeps_the_same_shape_when_the_judge_is_unavailable(
    medo_home: Path, monkeypatch
):
    """形が変われば呼び出し側が壊れる。判定できないことは形ではなくフラグで伝える。"""
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    path = medo_home / "cands.json"
    path.write_text(json.dumps([{"url": "https://example.com/a", "title": "a"}]), "utf-8")

    result = runner.invoke(
        app,
        ["research", "triage", "--project", "p", "--file", str(path), "--format", "json"],
    )
    payload = json.loads(result.output)

    assert payload["judge"] == "unavailable"
    assert set(payload) >= {"open", "rejected", "diminishing_returns", "budget_left"}


def test_jev_state_carries_the_project_so_relevance_can_be_judged(monkeypatch):
    """案件を知らないモデルに「この案件の現状把握に効くか」は問えない。"""
    import medo_cli.jev as jev

    sent = {}

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return json.dumps({"answers": {}}).encode()

    def _fake_urlopen(request, *args, **kwargs):
        sent["body"] = json.loads(request.data)
        return _Response()

    monkeypatch.setenv("TYPESAFE_API_KEY", "dummy")
    monkeypatch.setattr(jev, "urlopen", _fake_urlopen)
    jev.judge_candidates([], {"policy": "国の施策"}, {"goal": "生産計画の自動化"})

    assert sent["body"]["state"]["project"] == {"goal": "生産計画の自動化"}


def test_jev_support_uses_one_noul_and_threshold(monkeypatch):
    import medo_cli.jev as jev

    sent = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps({"answers": {"support": {"noul": 0.5}}}).encode()

    def fake_urlopen(request, timeout):
        sent["body"] = json.loads(request.data)
        sent["timeout"] = timeout
        return Response()

    monkeypatch.setenv("TYPESAFE_API_KEY", "dummy")
    monkeypatch.setattr(jev, "urlopen", fake_urlopen)
    assert jev.judge_support("2024年の市場", "2024年の市場", {"kind": "market"}) == "supported"
    assert list(sent["body"]["questions"]) == ["support"]
    assert sent["body"]["questions"]["support"]["type"] == "noul"
    assert sent["timeout"] == 10

    class DoubtfulResponse(Response):
        def read(self):
            return json.dumps({"answers": {"support": {"noul": 0.49}}}).encode()

    monkeypatch.setattr(jev, "urlopen", lambda *args, **kwargs: DoubtfulResponse())
    assert jev.judge_support("主張", "抜粋", {}) == "doubtful"


def test_jev_support_failure_is_reportable(monkeypatch):
    import medo_cli.jev as jev

    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="TYPESAFE_API_KEY"):
        jev.judge_support("主張", "抜粋", {})

    monkeypatch.setenv("TYPESAFE_API_KEY", "dummy")
    monkeypatch.setattr(jev, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(
        TimeoutError("timed out")))
    with pytest.raises(RuntimeError, match="timed out"):
        jev.judge_support("主張", "抜粋", {})


def test_research_plan_digest_renders_every_field(medo_home: Path):
    """既定はdigest。json経路しか試さないと、フィールド改名で既定出力が壊れる。"""
    _save_minimal_requirements(medo_home, "digest-project")

    result = runner.invoke(app, ["research", "plan", "--project", "digest-project"])

    assert result.exit_code == 0
    assert "一次資料の重み" in result.output and "取得規範" in result.output


def test_research_triage_digest_renders_the_judged_path(medo_home: Path, monkeypatch):
    """判定できた側の出力が未テストだと、辞書キーの改名で既定出力が落ちる。"""
    import medo_cli.commands.research as research_commands
    from medo_core.research import Verdict

    _save_minimal_requirements(medo_home, "judged-project")
    candidates = medo_home / "cands.json"
    candidates.write_text(
        json.dumps([{"url": "https://example.go.jp/a", "title": "告示", "hop": 1}]),
        encoding="utf-8",
    )
    monkeypatch.setenv("TYPESAFE_API_KEY", "dummy")
    monkeypatch.setattr(
        research_commands,
        "judge_candidates",
        lambda *a, **k: [
            Verdict(
                url="https://example.go.jp/a",
                relevance=0.3,
                aspect="policy",
                is_primary=0.9,
                worth_descending=0.7,
            )
        ],
    )

    result = runner.invoke(
        app,
        ["research", "triage", "--project", "judged-project", "--file", str(candidates)],
    )

    assert result.exit_code == 0, result.output
    assert "judge: available" in result.output
    assert "https://example.go.jp/a" in result.output


def test_check_list_exposes_engagement_stage_options(medo_home: Path):
    """守備範囲の段階はSkill本文ではなくCLIが持つ(どのホストでも同じ語彙になる)。"""
    result = runner.invoke(app, ["check", "list", "--format", "json"])
    rows = {row["name"]: row for row in json.loads(result.output)}

    assert rows["engagement_scope"]["options"] == [
        "現状整理まで", "合意形成まで", "打ち手の提案まで", "意思決定まで",
    ]
    assert rows["reality_gap"]["options"] == []


def test_knowledge_save_accepts_practice_without_url(medo_home: Path):
    """進め方のノウハウには引けるURLが無い。kindごとURLを必須にすると保存できない。"""
    result = runner.invoke(app, [
        "knowledge", "save", "--kind", "practice",
        "--statement", "決裁者の合意より先に現場の反応を取ったほうが早い",
        "--source", "medo-review 2026-09-23対話",
    ])

    assert result.exit_code == 0, result.output
    assert "saved:" in result.output


def test_knowledge_index_reports_counts_without_opening_entries(medo_home: Path):
    from medo_core.knowledge import KnowledgeEntry, KnowledgeStore

    KnowledgeStore(medo_home / "knowledge").save(KnowledgeEntry(**ENTRY))
    result = runner.invoke(app, ["knowledge", "index", "--format", "json"])

    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)
    assert rows[0]["entry_count"] == 1
    assert rows[0]["stale_count"] == 1

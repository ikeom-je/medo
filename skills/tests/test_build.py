import subprocess
import sys
from pathlib import Path

SKILLS_DIR = Path(__file__).parent.parent

SKILL_NAMES = [
    "medo-investigate", "medo-review", "medo-dialogue", "medo-decide",
    "medo-hearing", "medo-propose-options", "medo-grow-prfaq",
]

STAGE_SKILLS = ["medo-investigate", "medo-review", "medo-dialogue", "medo-decide"]


def _built(tmp_path, name: str) -> str:
    subprocess.run(
        [sys.executable, str(SKILLS_DIR / "build.py"), "--out", str(tmp_path)], check=True
    )
    return (tmp_path / name / "SKILL.md").read_text(encoding="utf-8")


def test_stage_skills_start_and_end_from_status(tmp_path):
    """開始時と終了時の2回、現在地をCLIから読む契約になっている。"""
    counts = {name: _built(tmp_path, name).count("--view summary") for name in STAGE_SKILLS}

    assert all(count >= 2 for count in counts.values()), counts


def test_stage_skills_keep_the_body_thin(tmp_path):
    """本文が厚いとモデルが変わったときの遵守率が落ちる(移植性の条件4)。"""
    too_long = {
        name: len(_built(tmp_path, name).splitlines())
        for name in STAGE_SKILLS
        if len(_built(tmp_path, name).splitlines()) > 80
    }

    assert too_long == {}


def test_investigate_gets_the_schema_and_outline_from_the_cli(tmp_path):
    """スキーマと章構成を本文に書き写すと実装との二重管理になる。"""
    text = _built(tmp_path, "medo-investigate")

    assert "medo requirements template" in text and "medo artifacts outline" in text


def test_investigate_can_stop_after_recording_requirements(tmp_path):
    """最小構成で使い始められること(移植性 §7)。スライドまで一本道にしない。"""
    assert "ここで終えてよい" in _built(tmp_path, "medo-investigate")


def test_review_reads_the_current_target_from_the_workflow_branch(tmp_path):
    """current_target は summary にも model にも無い。workflow 枝にしかない。"""
    assert "--view workflow" in _built(tmp_path, "medo-review")


def test_review_looks_up_which_checks_need_an_artifact(tmp_path):
    """artifact束縛のcheckは対象IDなしでは記録できず、手順どおり実行して失敗する。"""
    assert "medo check list" in _built(tmp_path, "medo-review")


def test_dialogue_does_not_attach_an_artifact_to_the_go_ahead(tmp_path):
    """to_be_go_ahead は要件宛て。--artifact を付けると拒否される。

    手順5(顧客が答えたチェックの記録)には正当な --artifact が出るため、
    手順4の go_ahead ブロックだけを切り出して見る。
    """
    text = _built(tmp_path, "medo-dialogue")
    go_ahead = text[text.index("--purpose to_be_go_ahead") : text.index("5. 顧客が答えた")]

    assert "--artifact" not in go_ahead


def test_dialogue_checks_whether_the_target_was_reviewed(tmp_path):
    """open_findings はレビュー未実施でも空。空を承認の証拠にできない。"""
    assert "review.approved" in _built(tmp_path, "medo-dialogue")


def test_decide_picks_one_focus_hypothesis_per_round(tmp_path):
    """論点を1つに絞らないと、蓄積した課題すべてに一律で向き合い周回が発散する。"""
    assert "--focus" in _built(tmp_path, "medo-decide")


def test_decide_keeps_node_ids_stable(tmp_path):
    """idを書き換えると過去のイベント・生成物の参照が別のノードを指す。"""
    assert "id は書き換えない" in _built(tmp_path, "medo-decide")


def test_build_generates_skill_md_per_name(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SKILLS_DIR / "build.py"), "--out", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    for name in SKILL_NAMES:
        skill_md = tmp_path / name / "SKILL.md"
        assert skill_md.exists(), name
        text = skill_md.read_text(encoding="utf-8")
        assert text.startswith("---")
        assert f"name: {name}" in text
        assert "description:" in text


def test_build_rejects_missing_frontmatter(tmp_path):
    src = tmp_path / "src"
    (src / "broken").mkdir(parents=True)
    (src / "broken" / "SKILL.md").write_text("no frontmatter here", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SKILLS_DIR / "build.py"), "--src", str(src), "--out", str(tmp_path / "out")],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "frontmatter" in (result.stdout + result.stderr)


def test_hearing_is_a_pointer_to_investigate(tmp_path):
    """旧スキーマのYAMLを案内し続けると、フェーズ2の要件を保存できない。"""
    text = _built(tmp_path, "medo-hearing")

    assert "medo-investigate" in text and "medo requirements save" not in text


def test_every_skill_reports_actions_from_status(tmp_path):
    """次に何をすべきかはCLIが返す。Skillが自前で判断すると本文が肥大する。"""
    missing = [
        name
        for name in SKILL_NAMES
        if name != "medo-hearing" and "--view summary" not in _built(tmp_path, name)
    ]

    assert missing == []


def test_every_skill_records_codex_as_a_possible_author(tmp_path):
    """3ホストで実行できる設計なのに、Codexが自分を記録できないと来歴が追えない。"""
    missing = [
        name
        for name in SKILL_NAMES
        if "--generated-by" in _built(tmp_path, name) and "codex" not in _built(tmp_path, name)
    ]

    assert missing == []


def test_grow_prfaq_applies_the_reframing_rule(tmp_path):
    """規約は顧客提出物であるprfaqの文章生成にも適用する。"""
    assert "medo artifacts outline" in _built(tmp_path, "medo-grow-prfaq")


def test_no_skill_carries_more_than_three_contract_items(tmp_path):
    """4項目以上の行動規範は遵守率が落ちる(移植性 §4)。"""
    over = {}
    for name in SKILL_NAMES:
        text = _built(tmp_path, name)
        if "## 契約" not in text:
            continue
        body = text[text.index("## 契約") :]
        over[name] = len([line for line in body.splitlines() if line.startswith("- ")])

    assert {name: n for name, n in over.items() if n > 3} == {}

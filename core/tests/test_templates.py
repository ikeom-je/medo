import re

import yaml

from medo_core.requirements import RequirementsDoc, RequirementsStore
from medo_core.storage import LocalJsonStorage
from medo_core.templates import (
    DISCUSSION_CHAPTER_INPUTS,
    DISCUSSION_SLIDES_OUTLINE,
    FINAL_CHAPTER_INPUTS,
    FINAL_SLIDES_OUTLINE,
    NODE_EXAMPLES,
    REFRAMING_RULE,
    REQUIREMENTS_TEMPLATE,
    WRITABLE_SECTIONS,
)


def _example_of(section: str) -> dict:
    """雛形のコメントアウトされた例を1件ぶん復元する。"""
    lines = REQUIREMENTS_TEMPLATE.splitlines()
    start = lines.index(f"# {section}:")
    body = []
    for line in lines[start:]:
        if not line.startswith("#"):
            break
        body.append(line[2:] if line.startswith("# ") else line[1:])
    return yaml.safe_load("\n".join(body))[section][0]


def test_template_is_valid_yaml_mapping():
    assert isinstance(yaml.safe_load(REQUIREMENTS_TEMPLATE), dict)


def test_template_keys_match_the_writable_sections_exactly():
    """余分なキーや誤字が混ざってもpydanticは黙って捨てるため、ここで落とす。"""
    assert set(yaml.safe_load(REQUIREMENTS_TEMPLATE)) == set(WRITABLE_SECTIONS)


def test_writable_sections_cover_every_field_the_user_supplies():
    """モデルに足したセクションを雛形へ足し忘れると、Skillはそれを埋められない。"""
    owned_by_store = {"version", "project"}

    assert set(RequirementsDoc.model_fields) - owned_by_store == set(WRITABLE_SECTIONS)


def test_saving_the_template_verbatim_creates_no_nodes(tmp_path):
    """空ノードにもIDが採番される。空のto_beが1件あるだけで段階判定が変わる。"""
    doc = RequirementsDoc.model_validate(
        {**yaml.safe_load(REQUIREMENTS_TEMPLATE), "project": "p1"}
    )
    RequirementsStore(LocalJsonStorage(tmp_path)).save("p1", doc)
    saved = RequirementsStore(LocalJsonStorage(tmp_path)).get("p1")

    assert [len(getattr(saved, s)) for s in NODE_EXAMPLES] == [0] * len(NODE_EXAMPLES)


def test_every_commented_example_is_covered_by_the_drift_check():
    """雛形に例を足しても NODE_EXAMPLES に載せ忘れると、乖離検査から漏れる。"""
    commented = {
        line[2:-1] for line in REQUIREMENTS_TEMPLATE.splitlines()
        if line.startswith("# ") and line.endswith(":") and " " not in line[2:-1]
    }

    assert commented == set(NODE_EXAMPLES)


def test_every_example_matches_its_node_model():
    """ノード型のフィールド改名を雛形へ反映し忘れると、Skillが誤った案内をする。"""
    unknown = {
        section: sorted(set(_example_of(section)) - set(model.model_fields))
        for section, model in NODE_EXAMPLES.items()
        if set(_example_of(section)) - set(model.model_fields)
    }

    assert unknown == {}


def test_every_example_saves_through_the_store(tmp_path):
    """pydantic検証を通ってもStore側のドメイン規則で落ちる例がある。"""
    filled = {
        **yaml.safe_load(REQUIREMENTS_TEMPLATE),
        **{section: [_example_of(section)] for section in NODE_EXAMPLES},
        "project": "p1",
    }
    doc = RequirementsDoc.model_validate(filled)

    assert RequirementsStore(LocalJsonStorage(tmp_path)).save("p1", doc) == 1


def test_outline_opens_with_the_verification_theme():
    """いきなり耳の痛い実態認識から入ると顧客が防衛的になる。章0を先頭に置く。"""
    assert DISCUSSION_SLIDES_OUTLINE.index("本日の検証テーマ") < DISCUSSION_SLIDES_OUTLINE.index(
        "公開情報と現場実態"
    )


def test_outline_forbids_the_uniform_euphemism():
    """利害対立を環境変化の物語に押し込めると、真因が議題から消える。

    肯定的な変換例にも「タイムラグ」は出るため、禁止文そのものを固定する。
    """
    assert "画一的な言い換えは禁止" in DISCUSSION_SLIDES_OUTLINE


def test_outline_separates_what_to_drop_from_what_to_keep():
    """線引きが無いとリフレーミングが不誠実な美化に堕ちる。"""
    assert "誰が悪いか" in DISCUSSION_SLIDES_OUTLINE and "何が起きているか" in (
        DISCUSSION_SLIDES_OUTLINE
    )


def test_outline_keeps_the_strawman_to_be_chapter():
    """仮説ToBeを見せる枠が無いと、往復のプローブが顧客の目に触れない。"""
    assert "叩き台の理想像" in DISCUSSION_SLIDES_OUTLINE


def test_outline_refuses_the_blank_handover_in_the_closing_chapter():
    """assumed を並べて教えを請うだけでは、事前調査不足の丸投げになる。"""
    assert "見立て" in DISCUSSION_SLIDES_OUTLINE and "選択肢" in DISCUSSION_SLIDES_OUTLINE


def test_every_chapter_input_exists_on_the_model():
    """章が使うセクションがモデルから消えると、埋められない案内になる。"""
    sections = {s for inputs in DISCUSSION_CHAPTER_INPUTS.values() for s in inputs}

    assert sections <= set(RequirementsDoc.model_fields)


def test_every_chapter_appears_in_the_outline():
    assert all(chapter in DISCUSSION_SLIDES_OUTLINE for chapter in DISCUSSION_CHAPTER_INPUTS)


def test_final_chapters_reference_real_inputs():
    """章の入力が実在しないセクション・生成物を指すと、Skillが埋められない。"""
    inputs = {name for chapter in FINAL_CHAPTER_INPUTS.values() for name in chapter}
    known = set(WRITABLE_SECTIONS) | {"rejected_options", "fermi", "prfaq"}

    assert inputs <= known


def test_every_final_chapter_appears_in_the_outline():
    assert all(chapter in FINAL_SLIDES_OUTLINE for chapter in FINAL_CHAPTER_INPUTS)


def test_final_outline_keeps_the_comparison_inside_the_prfaq():
    """最終提案スライドの親は prfaq ちょうど1件で、mini-prfaq を直接参照できない。"""
    assert "mini-prfaq" not in FINAL_SLIDES_OUTLINE
    assert "rejected_options" in FINAL_SLIDES_OUTLINE


def test_final_outline_names_the_criteria_behind_the_choice():
    """評価軸を示さない採否は属人的な結論に見える。"""
    assert "principles" in FINAL_SLIDES_OUTLINE and "kpis" in FINAL_SLIDES_OUTLINE


def test_final_outline_takes_numbers_only_from_stored_calculations():
    """効果の数値をスライド生成で作り出さない(設計原則: 数値の通り道にLLMを挟まない)。"""
    assert "fermi" in FINAL_SLIDES_OUTLINE


def test_final_outline_asks_for_the_phase_signoff():
    """Askが何の承認依頼かを書かないと、反応を記録する対象が定まらない。"""
    assert "phase_signoff" in FINAL_SLIDES_OUTLINE


def test_final_outline_controls_disclosure_of_the_conflict_chapter():
    """合同会議で対立構造をそのまま投影すると会議が紛糾する。"""
    conflict_chapter = FINAL_SLIDES_OUTLINE[FINAL_SLIDES_OUTLINE.index("## 章3"):]

    assert "開示" in conflict_chapter[: conflict_chapter.index("## 章4")]


def test_both_outlines_carry_the_same_reframing_rule():
    """規約を2箇所に書き分けると、片方だけが更新される。"""
    assert REFRAMING_RULE in DISCUSSION_SLIDES_OUTLINE
    assert REFRAMING_RULE in FINAL_SLIDES_OUTLINE


def test_the_reframing_rule_does_not_hardcode_chapter_numbers():
    """適用章は討議用(章2・章3)と最終提案(章3)で違う。規約本文に書くと片方が誤りになる。"""
    assert not re.search(r"章\d", REFRAMING_RULE)

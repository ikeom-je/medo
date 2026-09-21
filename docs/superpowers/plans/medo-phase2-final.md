# フェーズ2 優先度6: 最終提案スライドと `phase_signoff` ゲート 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 標準周回で合意した現状と理想を、完全版PRFAQ → 最終提案スライド(Ask)→ 決裁者の `phase_signoff` まで運べるようにする。フェーズ2の完了定義「共感できるドキュメント+提案スライドまで」の最後の一区間を閉じる。

**Architecture:** ドメイン層(`Artifact.slide_kind` / `rejected_options` / `PURPOSE_TARGETS` / `phase_readiness`)は優先度1〜4で実装済み。本計画が足すのは**判断材料の出口**である — 章構成をCLIが返し、フェーズ完了の診断を `actions` に写し、Skillがその出口を使う。**新しいドメイン概念は増やさない**。

**Tech Stack:** Python 3.12 / pydantic v2 / typer / pytest / ruff(line-length 100)。Skillは3ホスト共通の `<name>/SKILL.md` 形式。

**Spec:**
- [スライド設計](../specs/phase2-slides-design.md) §4(最終提案スライド・`rejected_options`・章4の素材)
- [ワークフローモデル](../specs/phase2-workflow-model.md) §6・§7(`phase_readiness`・`phase_signoff` の target・artifact束縛checkの現在対象)
- [status契約](../specs/phase2-status-contract.md) §3・§4・§5(`actions` 8〜8d・`readiness.phase`・後方互換)
- [Skill構成と移植性](../specs/phase2-skill-portability.md) §3(`medo-grow-prfaq` の用途)
- 索引: [medo-phase2-design.md](../specs/medo-phase2-design.md)

## Global Constraints

- **状態はすべてCLIに置く**。判断材料(章構成・診断・次にできること)はCLIが返し、SKILL.md本文に書き写さない(移植性 条件4)
- **診断はゲートではない**。`phase_readiness` が `not_ready` でも最終提案スライドの生成・保存を妨げない
- **数値・事実の通り道にLLMを挟まない**。スライドが引用する効果の数値は保存済みの `fermi` 生成物とファクトのみ。pricing計算機は後送りであり、スライド生成が金額を作り出さない
- **Skillを増やさない**。最終提案は `medo-grow-prfaq` の延長として扱う(`description` の近いSkillが並ぶと選択がブレる)
- **後方互換を壊さない**。`--view summary` の `artifacts` 配列は「型ごと最新版」のまま(status契約 §5)。`next_step` の値域も変えない
- 表現の分担: コード=How / テストコード=What / コミットログ=Why / コードコメント=Why not
- **各Taskのコミット前に `uv run pytest` と `uv run ruff check .` が両方通ること**

## 事前に確認した実装の制約

計画は下記を実測して書いている。**実装前にこの表を読むこと**。

| 制約 | 実測した内容 | 出典 |
|---|---|---|
| 最終提案スライドの保存はすでに通る | `Artifact` は `slide_kind="final"` を受け、親は `prfaq` ちょうど1件が必須 | `core/src/medo_core/artifacts.py` `ALLOWED_PARENTS` |
| CLIも保存に必要な引数を持つ | `--slide-kind` / `--derived-from` / `--rejected` / `--covers` | `cli/src/medo_cli/main.py` `artifacts_save` |
| `rejected_options` を持てるのは3type | `mini-prfaq` / `comparison` / `prfaq` のみ。**`slides` では拒否される** | `core/src/medo_core/artifacts.py` `REJECTION_TYPES` |
| `--rejected` の書式 | `<名前>:<理由>[:<受け入れたリスク>]` を複数回指定 | `cli/src/medo_cli/main.py` |
| 最終提案スライドは `mini-prfaq` を親にできない | 親は `prfaq` ちょうど1件。比較結果は `prfaq` に**取り込んでおく**前提 | `docs/superpowers/specs/phase2-artifact-lifecycle.md` |
| staleは親から連鎖する | staleな `prfaq` から作った最終提案スライドは即座にstaleを継承する | `core/src/medo_core/artifacts.py` |
| `phase_readiness` は実装済みだが `--view full` にしか出ない | `project_status` の `view == "full"` 枝だけが呼び、第5のトップレベル要素として置いている | `core/src/medo_core/status.py` |
| `phase_readiness` は未収束でも条件を並べる | `prfaq` があれば `convergence_not_ready` と `final_slides_missing_or_stale` が同時に立つ。**失敗条件をそのまま行動に写すと、未収束・staleな親から資料を作らせる** | `core/src/medo_core/diagnostics.py` |
| `phase_signoff` の target は最終提案スライド | `PURPOSE_TARGETS["phase_signoff"] = ("artifact", "slides", "final")`。`respond add --artifact <slides-vN>` が必須 | `core/src/medo_core/workflow.py` |
| 承認は現在の対象にしか効かない | `EffectiveResponse.on_current_target` が偽なら `phase_signoff_missing` が立つ。決裁者が複数でも1名の `agreed` で充足する(`any`) | `core/src/medo_core/responses.py` / `diagnostics.py` |
| artifact束縛checkの現在対象はtypeだけで決まる | `_current_artifact_ids` は `a.type` をキーにする。**`slides` の2種類が互いを上書きする**(Task 2で修正) | `core/src/medo_core/context.py` |
| 同じ関数が後方互換の生成物一覧にも使われている | `_summary` の `artifacts` 配列と stale集合が同じ辞書の `.values()` を読む。**キーを変えると後方互換の形も変わる** | `core/src/medo_core/status.py` |
| `artifacts outline --slide-kind final` は現在 exit 1 | `fail("slide_kind=final の章構成は未実装です(フェーズ2 優先度6)")` | `cli/src/medo_cli/commands/templates.py` |
| CLIテストの慣習 | `runner = CliRunner()` は stderr を分離していない。失敗系は `result.output` に `error:` を見る。`medo_home` は autouse fixture | `cli/tests/test_cli.py` |
| coreテストの慣習 | `test_status.py` は `_project(tmp_path)` で案件を組み、`_codes(status)` で action コードを取る。`test_checks.py` は `effective_checks(..., current_artifact_ids={...})` に辞書を直接渡す | `core/tests/` |

## スコープ外

- `build-mock` / `decision-roadmap` / `propose-architecture` / pricing / 簡易Webアプリ(詳細設計が未了)
- 出典検証の強化(URLフェッチ+数値突合)
- **生成文面そのものの品質評価**(実案件で行う)。ただしSkill本文を変更するため、**既存のevalケース再実行はTask 5に含める**([testing.md](../../../.claude/steering/testing.md) Skill evalケース)

---

## File Structure

| ファイル | 責務 |
|---|---|
| `core/src/medo_core/templates.py`(変更) | `FINAL_CHAPTER_INPUTS` / `FINAL_SLIDES_OUTLINE` / 共有する `REFRAMING_RULE` |
| `core/tests/test_templates.py`(変更) | 章構成と入力の対応・規約の共有 |
| `cli/src/medo_cli/commands/templates.py`(変更) | `--slide-kind final` の出力 |
| `cli/tests/test_cli.py`(変更) | outline と status の出力形式 |
| `core/src/medo_core/context.py`(変更) | `current_check_targets`(新)と `_current_artifact_ids`(既存・type別)の分離 |
| `core/src/medo_core/checks.py`(変更) | `(type, slide_kind)` での失効判定 |
| `core/src/medo_core/status.py`(変更) | `readiness.phase` の投影と、フェーズ完了の `actions` |
| `core/tests/test_checks.py` / `test_status.py`(変更) | 失効しないこと・行動が出ること・後方互換 |
| `skills/src/medo-grow-prfaq/SKILL.md`(変更) | 再開分岐 + 最終提案スライド + 承認の記録 |
| `skills/tests/test_build.py`(変更) | 上記の検証 |
| `README.md` / `docs/usage.md` / `docs/setup.md` / `.claude/specs/phase2/*`(変更) | Task 5で同期 |

---

## Task 1: 最終提案スライドの章構成をCLIが返す

**Files:** Modify `core/src/medo_core/templates.py` / `core/tests/test_templates.py` / `cli/src/medo_cli/commands/templates.py` / `cli/tests/test_cli.py`

**Interfaces:**
- Produces: `FINAL_CHAPTER_INPUTS: dict[str, tuple[str, ...]]` / `FINAL_SLIDES_OUTLINE: str` / `REFRAMING_RULE: str`
- CLI `medo artifacts outline --type slides --slide-kind final` → exit 0

**なぜ必要か**: 最終提案スライドは合意形成の最後の成果物だが、章構成の正本がどこにも無い。SKILL.mdに書き写すと本文が肥大し実装と二重管理になるため、討議用と同じく `templates.py` に置いてCLIが返す。

**設計上の要点**:
- 章は[スライド設計](../specs/phase2-slides-design.md) §4の7章。**章3にはリフレーミング必須と開示制御の両方**を書く(最終提案の場は決裁者と関係部門の合同会議になりやすい)
- **章4の素材は `prfaq` に取り込まれている前提**で書く。`mini-prfaq` を直接参照させない(親は `prfaq` ちょうど1件)。評価軸として `principles` / `kpis` を入力に含める
- **章5は効果の桁感と制約を含むが、数値を作らない**。効果は保存済み `fermi` 生成物、予算・体制の制約は `constraints` / `non_functional` から引く
- **章7(Ask)は `phase_signoff` の依頼である**ことを明記する。何に対する承認かが曖昧だと、記録する対象が定まらない
- **リフレーミング規約は1つの定数を両outlineが連結する**。ただし**規約本文から「章2・章3に必須」の限定を外し**、適用章は各outlineの章見出し側(`★リフレーミング必須`)で示す。討議用は章2・章3、最終提案は章3であり、規約本文に章番号を書くと片方が誤りになる

- [ ] **Step 1: 失敗するテストを書く**

`core/tests/test_templates.py` に追加(import に `FINAL_CHAPTER_INPUTS` / `FINAL_SLIDES_OUTLINE` / `REFRAMING_RULE` を足す):

```python
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
```

`cli/tests/test_cli.py` の `test_artifacts_outline_reports_final_is_not_available_yet` を**置き換える**:

```python
def test_artifacts_outline_returns_the_final_chapters(medo_home: Path):
    result = runner.invoke(
        app, ["artifacts", "outline", "--type", "slides", "--slide-kind", "final"]
    )

    assert result.exit_code == 0
    assert "SCQA" in result.output and "ネクストアクション" in result.output
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest core/tests/test_templates.py cli/tests/test_cli.py -q`
Expected: FAIL — `FINAL_CHAPTER_INPUTS` / `FINAL_SLIDES_OUTLINE` / `REFRAMING_RULE` が `ImportError`、CLIは exit 1

- [ ] **Step 3: `REFRAMING_RULE` を切り出す** — `DISCUSSION_SLIDES_OUTLINE` 末尾の規約ブロックを定数化し、見出しから章番号の限定を外して連結で組み立てる。既存テスト(`test_outline_forbids_the_uniform_euphemism` 等)がそのまま通ること

- [ ] **Step 4: `FINAL_CHAPTER_INPUTS` と `FINAL_SLIDES_OUTLINE` を追加** — 討議用と同じ体裁(`## 章N: <名前>` + 入力 + 注意)

- [ ] **Step 5: CLIの分岐を差し替える** — `slide_kind == "final"` を出力にし、`--slide-kind` のヘルプから「未実装」を削る

- [ ] **Step 6: 検証してコミット** — `uv run pytest` / `uv run ruff check .`

```
feat(core): 最終提案スライドの章構成をCLIが返す

合意形成の最後の成果物である最終提案スライドは章構成の正本を持たず、
Skill本文に書き写すしかなかった。討議用と同じくCLIが返せば、実装との
乖離をテストで落とせる。
```

---

## Task 2: artifact束縛checkの現在対象を `(type, slide_kind)` で決める

**Files:** Modify `core/src/medo_core/context.py` / `core/src/medo_core/checks.py` / `core/src/medo_core/status.py` / `core/tests/test_checks.py` / `core/tests/test_status.py`

**Interfaces:**
- Produces: `medo_core.context.current_check_targets(artifacts) -> dict[tuple[str, str | None], str]`
- Changes: `checks.effective_checks(current_targets=...)`(キーがtuple)/ `status._runnable_checks` / stale集合
- **変えない**: `_current_artifact_ids`(type別)は後方互換の生成物一覧のために残す

**なぜ必要か**: `_current_artifact_ids` は `a.type` をキーにするため、最終提案スライドを保存した瞬間に「現在の slides」が入れ替わり、**討議用スライド束縛の `expression_safety` が失効する**。討議用スライド自体はストアに残っているのに投影上の現在対象から外れ、確認済みの項目が未確認へ戻って `check_missing` で収束判定も落ちる。優先度6で `slides` が2種類になるまで表面化しなかった欠陥である。

**設計上の要点**:
- **解決子を2つに分ける**(Codex指摘)。check束縛用は `(type, slide_kind)`、後方互換の `artifacts` 配列は type別のまま。同じ辞書を使い回すと `--view summary` の形が変わり、フェーズ1のSkillが壊れる(status契約 §5)
- `CheckSpec` はすでに `slide_kind` を持つ。registry側は `(spec.target_type, spec.slide_kind)` で引く。`slide_kind` を持たない生成物のキーは `(type, None)`
- **stale集合は新しい解決子を使う**。討議用と最終提案のどちらがstaleでも `regenerate_stale_artifacts` に出す(type別だと片方が隠れる)
- 既存テスト `test_checks.py` の `current_artifact_ids={"as-is-report": ...}` はキー契約が変わるため更新する

- [ ] **Step 1: 失敗するテストを書く**

`core/tests/test_checks.py`:

```python
def test_final_slides_do_not_expire_the_discussion_expression_safety():
    """討議用スライド束縛のcheckが、最終提案スライドの保存で失効してはならない。"""
    events = [_recorded("ev-1", "expression_safety", "completed",
                        target=ArtifactTarget(artifact_id="slides-v1"))]

    states = effective_checks(
        events, phase="convergence", latest_requirements_version=1, manifests=[],
        current_targets={("slides", "discussion"): "slides-v1",
                         ("slides", "final"): "slides-v2"},
    )

    assert states["expression_safety"].state == "completed"


def test_regenerated_discussion_slides_still_expire_the_check():
    """同じ種別で作り直したときは失効する(この挙動は変えない)。"""
    events = [_recorded("ev-1", "expression_safety", "completed",
                        target=ArtifactTarget(artifact_id="slides-v1"))]

    states = effective_checks(
        events, phase="convergence", latest_requirements_version=1, manifests=[],
        current_targets={("slides", "discussion"): "slides-v3"},
    )

    assert states["expression_safety"].state == "unverified"
```

`core/tests/test_status.py`:

```python
def test_compat_artifact_list_stays_keyed_by_type(tmp_path):
    """フェーズ1のSkillは artifacts 配列を型で引いている(status契約 §5)。"""
    storage = _project_with_both_slide_kinds(tmp_path)

    status = project_status(storage, "p1", tmp_path)

    assert len([row for row in status["artifacts"] if row["type"] == "slides"]) == 1


def test_stale_action_sees_both_slide_kinds(tmp_path):
    """type別に畳むと、staleな討議用スライドが最終提案の陰に隠れる。"""
    storage = _project_with_both_slide_kinds(tmp_path, stale_discussion=True)

    actions = project_status(storage, "p1", tmp_path)["actions"]
    regenerate = [a for a in actions if a["code"] == "regenerate_stale_artifacts"]

    assert regenerate and "slides-v1" in regenerate[0]["refs"]
```

- [ ] **Step 2: テストが失敗することを確認** — Run: `uv run pytest core/tests/test_checks.py core/tests/test_status.py -q`

- [ ] **Step 3: `current_check_targets` を追加し、`checks` 側の引数名とキーを変える** — 既存テストの呼び出しも合わせて更新する

- [ ] **Step 4: `status` の利用箇所を振り分ける** — `_runnable_checks` と stale集合は新解決子、`_summary` の `artifacts` 配列は従来の `_current_artifact_ids`

- [ ] **Step 5: 検証してコミット**

```
fix(core): artifact束縛checkの現在対象をslide_kindまで見て決める

slidesが討議用と最終提案の2種類になると、typeだけで最新版を決める実装は
最終提案の保存で討議用束縛のcheckを失効させ、確認済みの項目を未確認へ戻す。
後方互換の生成物一覧は型ごと最新版のまま保つ必要があるため、解決子を分ける。
```

---

## Task 3: フェーズ完了の診断と行動を status が返す

**Files:** Modify `core/src/medo_core/status.py` / `core/tests/test_status.py` / `cli/tests/test_cli.py`

**Interfaces:**
- `medo status --view readiness` → `{"readiness": {"state", "failed_conditions", "phase": {"state", "failed_conditions"}}}`
- `--view full` も同じ位置に置く(第5のトップレベル要素をやめる)
- `build_actions(ctx, model, ready, phase_ready)` → `generate_final_slides` / `request_phase_signoff` / `complete_phase`

**なぜ必要か**: `phase_readiness` は実装済みだが `--view full` にしか出ず、**対応する `actions` が無い**。標準周回が収束した後、Skillは `proceed_to_propose_options` の1件だけを見て、そこから先(PRFAQ→最終提案スライド→承認依頼)を自力で判断するしかない。

**設計上の要点**:
- **条件は肯定形で判定する**(Codex指摘)。`phase_readiness.failed_conditions` をそのまま写すと、標準周回が未収束でも `prfaq` がstaleでも `final_slides_missing_or_stale` は同時に立つため、**staleな親から資料を作らせる行動**を推奨してしまう(staleは親から連鎖する)
  - 8b `generate_final_slides`: `readiness.state == "ready"` かつ `prfaq` が fresh かつ 最終提案スライドが無いかstale
  - 8c `request_phase_signoff`: `readiness.state == "ready"` かつ `prfaq` と最終提案スライドがともに fresh で `phase_signoff_missing`。refsは未取得の決裁者
  - 8d `complete_phase`: `phase_readiness.state == "ready"`
- **`proceed_to_propose_options` は `phase_readiness` が `not_evaluable` のときだけ出す**。PRFAQができた後も出し続けると、Skillが候補提案へ戻る
- **巻き戻りには理由を付ける**(agy指摘)。`purpose="phase_signoff"` の `agreed` があるのに `on_current_target` が偽なら、8cに `reason="スライドが更新されたため再承認が必要"` を返す
- `convergence_not_ready` / `prfaq_missing_or_stale` に新しい行動は足さない(標準周回側の行動と `regenerate_stale_artifacts` が既に覆う)
- **`decision_makers` の算出が `view == "full"` の中にある**。共通部へ引き上げ、full・readiness・actions が同じ値を使う

- [ ] **Step 1: 失敗するテストを書く**

`core/tests/test_status.py`(`_project` を土台に、PRFAQ・最終提案スライド・`phase_signoff` を段階的に足すヘルパー `_phase_project(tmp_path, *, prfaq=False, final=False, signoff=False)` を追加する):

```python
def test_readiness_view_carries_the_phase_judgement(tmp_path):
    """フェーズ完了の可否は収束の次の問いであり、別viewを呼ばせない。"""
    status = project_status(_phase_project(tmp_path, prfaq=True), "p1", tmp_path,
                            view="readiness")

    assert set(status) == {"project", "diagnostic_phase", "readiness"}
    assert status["readiness"]["phase"]["state"] in {"ready", "not_ready", "not_evaluable"}


def test_actions_ask_for_final_slides_once_the_prfaq_is_fresh(tmp_path):
    """PRFAQができた後も候補提案へ戻す行動を出すと、往復が閉じない。"""
    codes = _codes(project_status(_phase_project(tmp_path, prfaq=True), "p1", tmp_path))

    assert "generate_final_slides" in codes and "proceed_to_propose_options" not in codes


def test_no_final_slides_are_asked_for_from_a_stale_prfaq(tmp_path):
    """staleな親から作った資料は即座にstaleを継承する。"""
    codes = _codes(project_status(_phase_project(tmp_path, prfaq="stale"), "p1", tmp_path))

    assert "generate_final_slides" not in codes


def test_actions_request_the_phase_signoff_from_the_decision_maker(tmp_path):
    """承認依頼の宛先が出ないと、誰に持っていくかSkillが判断できない。"""
    actions = project_status(_phase_project(tmp_path, prfaq=True, final=True),
                             "p1", tmp_path)["actions"]
    request = [a for a in actions if a["code"] == "request_phase_signoff"]

    assert request and request[0]["refs"] == ["sh-1"]


def test_regenerated_slides_explain_why_the_signoff_is_needed_again(tmp_path):
    """理由の無い巻き戻りはバグに見える。"""
    storage = _phase_project(tmp_path, prfaq=True, final=True, signoff=True)
    _save_final_slides(storage)  # 承認後にスライドを作り直す
    actions = project_status(storage, "p1", tmp_path)["actions"]
    request = [a for a in actions if a["code"] == "request_phase_signoff"]

    assert request and "再承認" in request[0]["reason"]


def test_actions_report_the_phase_is_complete(tmp_path):
    """完了を返さないと、次フェーズへ進んでよいかが分からない。"""
    codes = _codes(project_status(
        _phase_project(tmp_path, prfaq=True, final=True, signoff=True), "p1", tmp_path))

    assert "complete_phase" in codes


def test_full_view_keeps_the_phase_judgement_inside_readiness(tmp_path):
    """枝の外にトップレベル要素を足すと、投影規則が崩れる。"""
    status = project_status(_phase_project(tmp_path, prfaq=True), "p1", tmp_path,
                            view="full")

    assert "phase_readiness" not in status and "phase" in status["readiness"]


def test_next_step_is_unchanged_by_the_final_stage(tmp_path):
    """フェーズ1のSkillは next_step を完全一致で分岐している。"""
    status = project_status(
        _phase_project(tmp_path, prfaq=True, final=True, signoff=True), "p1", tmp_path)

    assert status["next_step"] in {
        "hearing", "propose-options", "grow-prfaq",
        "regenerate-stale-artifacts", "up-to-date",
    }
```

`cli/tests/test_cli.py`:

```python
def test_status_readiness_view_includes_the_phase_judgement(medo_home: Path):
    """Skillは1回の呼び出しでフェーズ完了の可否まで読む。"""
    # 既存の status テストと同じ手順で案件を組み、--view readiness --format json を叩く
    assert "phase" in json.loads(result.output)["readiness"]
```

- [ ] **Step 2: テストが失敗することを確認**

- [ ] **Step 3: `phase_readiness` を共通部へ上げ、`readiness` 枝の中に入れる** — `--view full` の第5要素を廃止する

- [ ] **Step 4: `build_actions` に 8b〜8d を足す** — 肯定条件で判定し、8の条件を `phase.state == "not_evaluable"` で絞る

- [ ] **Step 5: 検証してコミット**

```
feat(core): フェーズ完了の診断と行動をstatusが返す

phase_readinessは実装済みでも--view fullにしか出ず、対応する行動が無い。
標準周回の収束後、Skillは提案から承認依頼までを自力で判断するしかなかった。
失敗条件をそのまま写すと未収束・staleな親から資料を作らせるため、肯定条件で
判定する。
```

---

## Task 4: `medo-grow-prfaq` を最終提案スライドと承認の記録まで延ばす

**Files:** Modify `skills/src/medo-grow-prfaq/SKILL.md` / `skills/tests/test_build.py`

**Interfaces:**
- Consumes: Task 1〜3(`artifacts outline --slide-kind final` / `actions` の 8〜8d)
- Produces: `slides(final)` の保存と `respond add --purpose phase_signoff` までの手順

**なぜ必要か**: 完全版PRFAQで手順が終わっており、**顧客の意思決定にかけるための資料と、その承認の記録に到達しない**。フェーズ2の完了定義は「共感できるドキュメント+提案スライドまで」であり、PRFAQは通過点である。

**設計上の要点**:
- **`actions` を見て再開位置を分岐する**(Codex指摘)。線形に追記するだけだと、`request_phase_signoff` の状態で再実行したときにPRFAQとスライドを作り直し、**現在のスライドへの承認を自分で無効化する**。移植性の条件2(どのSkillも `status` から単独で開始できる)に反する
  - `generate_final_slides` があればスライドから、`request_phase_signoff` があれば記録から始める
- **承認は「得た反応」の記録である**(Codex指摘)。依頼しただけで `agreed` を記録しない。未取得ならその旨を報告して終える
- **PRFAQ保存とスライド生成のあいだにユーザー確認を置く**(agy指摘)。長文のPRFAQと7章のスライドを一息に生成すると、ユーザーが読む前にスライド化が進み訂正の機会が失われる
- 却下案は **`prfaq` 保存時に `--rejected` で記録し、比較の観点と評価はPRFAQ本文に取り込む**(スライドには保存できず、`mini-prfaq` を親にもできない)
- **契約は3項目のまま**(既存テスト `test_no_skill_carries_more_than_three_contract_items` が縛る)。本文80行以内

- [ ] **Step 1: 失敗するテストを書く**

`skills/tests/test_build.py`:

```python
def test_grow_prfaq_reaches_the_final_slides(tmp_path):
    """PRFAQで止まると、顧客の意思決定にかける資料に到達しない。"""
    text = _built(tmp_path, "medo-grow-prfaq")

    assert "--slide-kind final" in text and "phase_signoff" in text


def test_grow_prfaq_records_rejected_options_on_the_prfaq(tmp_path):
    """--rejected はスライドでは拒否される(REJECTION_TYPES)。"""
    text = _built(tmp_path, "medo-grow-prfaq")
    prfaq_step = text[text.index("--type prfaq") : text.index("--slide-kind final")]

    assert "--rejected" in prfaq_step


def test_grow_prfaq_resumes_from_the_actions(tmp_path):
    """再実行でPRFAQを作り直すと、現在のスライドへの承認が無効になる。"""
    text = _built(tmp_path, "medo-grow-prfaq")

    assert "generate_final_slides" in text and "request_phase_signoff" in text


def test_grow_prfaq_records_only_reactions_it_actually_received(tmp_path):
    """依頼しただけで agreed を記録すると、承認の意味が失われる。"""
    text = _built(tmp_path, "medo-grow-prfaq")

    assert "得られた反応" in text or "実際に得た" in text
```

- [ ] **Step 2: テストが失敗することを確認** — Run: `uv run pytest skills/tests/test_build.py -q`

- [ ] **Step 3: SKILL.md を更新** — 手順1で `actions` による再開分岐、手順6(prfaq保存)に `--rejected` と比較の取り込み、ユーザー確認、最終提案スライドの生成・保存、承認の依頼と記録。既存の手順(ナレッジ追記・status報告)は末尾に残す

- [ ] **Step 4: 検証してコミット**

```
feat(skills): 最終提案スライドと承認の記録までをgrow-prfaqに延ばす

完全版PRFAQで手順が終わっており、顧客の意思決定にかける資料とその承認の
記録に到達しない。線形に追記すると再開時にスライドを作り直して承認を無効化
するため、actionsで再開位置を分岐する。
```

---

## Task 5: ドキュメント同期・eval再実行・通し確認

**Files:** Modify `.claude/specs/phase2/tasks.md` / `.claude/specs/phase2/spec.md` / `README.md` / `docs/usage.md` / `docs/setup.md`

**なぜ必要か**: `.claude/specs/phase2/tasks.md` が優先度5を「未着手(別計画)」と書いたままで、実態(PR #103〜#105で完了)とずれている。次に読むAgentが誤った現在地から始める。READMEは優先度5まで実態と一致しているが、本計画の完了で優先度6の行が古くなる。またSkill本文を変更したため、evalケースの再実行が要る([testing.md](../../../.claude/steering/testing.md))。

- [ ] **Step 1: `.claude/specs/phase2/tasks.md` を更新** — 優先度5を完了(PR番号付き)に、優先度6を本計画へのリンク付きで追加。Task 21の状態を更新
- [ ] **Step 2: `README.md` のフェーズ表の優先度6の行を更新**(他の行は既に実態と一致している)
- [ ] **Step 3: `docs/usage.md` に最終提案スライドから承認までの一区間を追記**
- [ ] **Step 4: Skill evalケースを再実行** — 既存の実案件1件で `medo-grow-prfaq` を回し、引用ID・章構成が安定していること、**依頼しただけで `phase_signoff` を記録しないこと**を目視確認する
- [ ] **Step 5: まっさらな `MEDO_HOME` で通し確認** — 要件保存 → 標準周回 → prfaq → 最終提案スライド → `respond add --purpose phase_signoff` → `medo status --view readiness` の `readiness.phase.state == "ready"` まで。**ユーザーと共同で実行し、結果を `docs/setup.md`(手動スモークの正本)へ追記する**
- [ ] **Step 6: 検証してコミット**

---

## 完了の定義

- [ ] `medo artifacts outline --type slides --slide-kind final` が7章とリフレーミング規約を返す
- [ ] 最終提案スライドを保存しても討議用スライド束縛の `expression_safety` が失効しない
- [ ] `--view summary` の `artifacts` 配列が「型ごと最新版」のまま(後方互換)
- [ ] `medo status --view readiness` が `readiness.phase` を返し、`--view full` も同じ位置に置く
- [ ] `actions` が `generate_final_slides` / `request_phase_signoff` / `complete_phase` を**肯定条件で**返す
- [ ] `medo-grow-prfaq` が `actions` から再開位置を分岐し、最終提案スライドと承認の記録まで案内する(本文80行以内・契約3項目以内)
- [ ] Skill evalケースを再実行し、結果を記録した
- [ ] まっさらな `MEDO_HOME` から `readiness.phase.state == "ready"` まで到達できる
- [ ] すべてのTaskで `uv run pytest` / `uv run ruff check .` が通った状態でコミットされている

## 次にやること(本計画のスコープ外)

- 出典検証の強化(URLフェッチ+数値突合)— 他と技術的に独立
- ナレッジ来歴 / `knowledge-digest` / `decision-roadmap` / `build-mock` / `propose-architecture` / pricing / 簡易Webアプリ — **着手前に設計ドキュメントを起こす**

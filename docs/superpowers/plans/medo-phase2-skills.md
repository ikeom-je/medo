# フェーズ2 優先度5: Skill 4本と討議用スライド生成 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 標準周回の4ステージそれぞれに対応するSkillを用意し、ホストLLM(Claude Code / Codex / agy)がフェーズ2の決定論層を実際に回せるようにする。

**Architecture:** Skill本文には**手順だけ**を書き、判断材料(次にできること・要件スキーマ・スライドの章構成・checkの束縛と確認者)はすべてCLIが返す。スキーマや章構成をSKILL.mdに書き写すとモデルが変わったときの遵守率が落ち、かつ実装との二重管理になるため、**雛形と registry の射影を core に置いてCLIが出力する**。実装との乖離はテストで落とす。

**Tech Stack:** Python 3.12 / pydantic v2 / typer 0.26 / pytest / ruff(line-length 100)。Skillは3ホスト共通の `<name>/SKILL.md` 形式(YAML frontmatter + 本文)。

**Spec:**
- [Skill構成と移植性](../specs/phase2-skill-portability.md)(承認済み)
- [スライド設計](../specs/phase2-slides-design.md)(承認済み)
- 索引: [medo-phase2-design.md](../specs/medo-phase2-design.md)

## Global Constraints

設計正本から逐語で引くプロジェクト全体の要件。**全Taskの要件に暗黙に含まれる**。

- **状態はすべてCLIに置く**。ホストのコンテキストやメモリには何も残さない(条件1)
- **どのSkillも `medo status` から現在地を読んで単独で開始できる**。前のSkillの実行を前提にしない(条件2)
- **Skill間の受け渡しはCLI経由のみ**。コンテキスト越しに受け渡さない(条件3)
- **Skill本文を薄く保ち、判断材料はCLIが返す**。判定ロジック・検証・整合性チェックはすべてCLI側に置く(条件4)
- **全Skillの共通契約は3項目に絞る**(4項目以上は遵守率が落ちる):
  1. 開始時と終了時に `medo status --view summary` を実行し、`actions`(次にできること。案件が未作成なら `next_step`)をユーザーに報告する。詳しい理由が要るときだけ `--view readiness` を追加で呼ぶ
  2. CLIが失敗したら推測で補完せず、エラー内容をそのまま報告する
  3. stale・未確認・仮説の項目を引用するときは、その旨を明記する
- **ホスト固有の機能に依存しない**。使ってよいのは3ホストすべてが持つ能力(ファイル読み書き・シェル実行・Web検索)に限る
- **Skillは単一の `SKILL.md` で自己完結させる**。バンドルした参照ファイルの読み込み挙動はホストごとに差がある
- **サブエージェント機構を使わない**。Claude Codeの `Task` 相当が Codex・agy に無い
- **Skillを増やしすぎない**。Skillの選択は `description` frontmatter のマッチングで行われるため、似た説明が並ぶと選択がブレる
- 表現の分担: コード=How / テストコード=What / コミットログ=Why / コードコメント=Why not
- **各Taskのコミット前に `uv run pytest` と `uv run ruff check .` が両方通ること**。落ちているテストを残したまま次のTaskへ進まない

## 事前に確認した実装の制約

計画の各手順は下記を実測して書いている。**実装者はSKILL.mdを書き換える前にこの表を読むこと**。

| 制約 | 実測した内容 | 出典 |
|---|---|---|
| `Bottleneck` は `confirmed` のみ保存できる | `confidence: open` の bottleneck を保存すると `error: bottleneck bn-1 は confirmed のみ保存できます(未検証の真因は hypotheses(kind='cause')に置く)` | `core/src/medo_core/requirements.py` |
| 空ノードも保存されIDが採番される | 中身が空の `to_be` を1件でも保存すると `diagnostic_phase` が `convergence` に変わり、Discovery段階の診断が飛ぶ | `core/src/medo_core/diagnostics.py` の `diagnostic_phase` |
| artifact束縛の check は `--artifact` が必須 | `source_quality`(research)/ `as_is_articulation`(as-is-report)/ `expression_safety`(slides, discussion)。指定なしは拒否される | `core/src/medo_core/checks.py` `CHECK_REGISTRY` |
| `respond add` は purpose ごとに対象が決まっている | `as_is_alignment` → `as-is-report` artifact / `to_be_go_ahead` → **requirements(`--artifact` を付けてはいけない)** / `phase_signoff` → `final` slides(本計画ではスコープ外) | `core/src/medo_core/workflow.py` `PURPOSE_TARGETS` |
| `workflow.review.current_target` は workflow 枝にしかない | `--view summary` にも `--view model` にも含まれない。`--view workflow` を呼ぶ必要がある | `core/src/medo_core/status.py` |
| `--reaction` の値域 | `empathized` / `acknowledged` / `agreed` / `objected` / `unclear`(`corrected` や `silent` は無い) | `core/src/medo_core/events.py` |
| `--answer` の値域 | `generate` / `defer` の2値のみ | 同上 |
| `Stakeholder` に `name` フィールドは無い | 誰かは `text` に書く。`name` を持つのは `Kpi` | `core/src/medo_core/nodes.py` |
| CLIテストの慣習 | `runner = CliRunner()` は stderr を分離していない。失敗系は `result.output` に `error:` を見る。`medo_home` は autouse fixture で `Path` を返す | `cli/tests/test_cli.py` |

## スコープ外

- **最終提案スライド(`slide_kind="final"`)と `phase_signoff` ゲート**は優先度6。本計画は討議用(`discussion`)のみを扱う
- `.claude/steering/` の同期・`docs/usage.md` の更新はユーザー判断でスコープ外(フェーズ完了時に別途)

---

## File Structure

| ファイル | 責務 |
|---|---|
| `core/src/medo_core/templates.py`(新規) | 要件YAMLの雛形と討議用スライドの章構成。**モデル・registry との対応をテストで縛る** |
| `core/tests/test_templates.py`(新規) | 雛形とモデルの乖離検出 |
| `cli/src/medo_cli/commands/templates.py`(新規) | `requirements template` / `artifacts outline` / `check list` の実装 |
| `cli/src/medo_cli/main.py`(変更) | 上記コマンドの登録 |
| `cli/tests/test_cli.py`(変更) | 各コマンドの出力形式 |
| `core/src/medo_core/context.py`(変更) | `workflow.review.approved` の追加 |
| `core/tests/test_context.py` または `core/tests/test_status.py`(変更) | 承認状態の投影 |
| `skills/src/medo-investigate/SKILL.md`(新規) | ステージ1: 調べる・仕立てる(討議用スライド生成を含む) |
| `skills/src/medo-review/SKILL.md`(新規) | ステージ2: 内部検証 |
| `skills/src/medo-dialogue/SKILL.md`(新規) | ステージ3: ぶつける・反応を得る |
| `skills/src/medo-decide/SKILL.md`(新規) | ステージ4: 振り返る・次へ進む |
| `skills/src/medo-hearing/SKILL.md`(変更) | `medo-investigate` を案内する薄いwrapperにする |
| `skills/src/medo-propose-options/SKILL.md`(変更) | 共通契約3項目へ差し替え・`codex` 対応・表現規約へのポインタ |
| `skills/src/medo-grow-prfaq/SKILL.md`(変更) | 同上 |
| `skills/tests/test_build.py`(変更) | 新Skillのビルド検証。**各Taskで1本ずつ追加する** |

`commands/templates.py` は `commands/_common.py` のヘルパーだけを使い、`main.py` を import しない(依存が双方向になる)。

**新コマンドは既存グループの下に置く**(`medo slides` のようなトップレベルグループを新設しない)。スライドの保存が `medo artifacts save --type slides` である以上、章構成の取得も `medo artifacts outline` が自然で、名前空間が割れない。

---

## Task 1: 要件YAMLの雛形をCLIが返す

**Files:**
- Create: `core/src/medo_core/templates.py`
- Create: `core/tests/test_templates.py`
- Create: `cli/src/medo_cli/commands/templates.py`
- Modify: `cli/src/medo_cli/main.py`
- Modify: `cli/tests/test_cli.py`

**Interfaces:**
- Consumes: `medo_core.requirements.RequirementsDoc` / `RequirementsStore`
- Produces:
  - `medo_core.templates.REQUIREMENTS_TEMPLATE: str`
  - `medo_core.templates.WRITABLE_SECTIONS: tuple[str, ...]`
  - `medo_core.templates.NODE_EXAMPLES: dict[str, type[BaseModel]]` — 雛形が例示するセクション名 → そのノード型
  - CLI `medo requirements template` → 雛形YAMLをstdoutへ、exit 0

**なぜ必要か**: フェーズ2で要件スキーマが19セクション(うち11がノード)に拡張された。Skillが要件YAMLを書くにはスキーマを知る必要があるが、SKILL.mdに書き写すと本文が肥大し(移植性の条件4に反する)、実装との二重管理になる。

**設計上の要点**: **ノードの例はすべてコメントアウトする**。雛形をそのまま保存できる状態にしないと、Skillが「まだ埋まっていないセクション」に空ノードを1件ずつ作ってしまう。空ノードにもIDが採番され、さらに**空の `to_be` が1件あるだけで `diagnostic_phase` が `convergence` に変わり、Discovery段階の診断が飛ぶ**。

- [ ] **Step 1: 失敗するテストを書く**

`core/tests/test_templates.py`:

```python
import yaml

from medo_core.requirements import RequirementsDoc, RequirementsStore
from medo_core.storage import LocalJsonStorage
from medo_core.templates import NODE_EXAMPLES, REQUIREMENTS_TEMPLATE, WRITABLE_SECTIONS


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


def test_every_example_matches_its_node_model(tmp_path):
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
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest core/tests/test_templates.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'medo_core.templates'`

- [ ] **Step 3: `templates.py` を実装**

`core/src/medo_core/templates.py`:

```python
"""SkillがCLIから取得する雛形と registry の射影。

スキーマ・章構成・checkの束縛をSKILL.md本文へ書き写すと、ホストのモデルが
変わったときの遵守率が落ち、かつ実装との二重管理になる
(phase2-skill-portability.md 条件4)。
"""

from medo_core.nodes import (
    AsIs, Attempt, Bottleneck, Challenge, Constraint, Gap, Hypothesis, Kpi,
    OpenQuestion, Stakeholder, ToBe,
)

WRITABLE_SECTIONS = (
    "industry", "background", "goal", "principles", "functional", "non_functional",
    "sources", "knowledge_backend", "challenges", "open_questions",
    "as_is", "to_be", "kpis", "stakeholders", "gaps", "bottlenecks",
    "constraints", "attempts", "hypotheses",
)

NODE_EXAMPLES = {
    "as_is": AsIs, "to_be": ToBe, "gaps": Gap, "bottlenecks": Bottleneck,
    "challenges": Challenge, "constraints": Constraint, "open_questions": OpenQuestion,
    "kpis": Kpi, "stakeholders": Stakeholder, "attempts": Attempt,
    "hypotheses": Hypothesis,
}

REQUIREMENTS_TEMPLATE = """\
# medo 要件ドキュメントの雛形。
#
# ノードの例はすべてコメントアウトしてある。**埋める項目だけコメントを外す**。
# 空のノードを保存するとIDが採番され、空の to_be が1件あるだけで診断段階が
# convergence に変わる。埋まらない項目は open_questions に置くか、何も書かない。
#
# 既存案件を更新するときは `medo requirements get --project <id> --format json`
# の出力を編集する(**既存ノードの id は書き換えない**。書き換えると過去の
# イベント・生成物の参照が別のノードを指す)。
#
# confidence: confirmed(相手が明言) | assumed(文脈からの推定) | open(要検討)
# scope: core(診断対象) | secondary | out
# id: 新規ノードは書かない。保存時に core が採番する。

industry: ''
background: ''
goal: ''

# 経営思想・理念・方針。検索で取れる事実ではなく、対話で引き出して合意する対象。
principles: []
# principles:
#   - text: ''
#     confidence: open

# 現状。visibility は必須。public=外から見える姿 / internal=現場の実態。
as_is: []
# as_is:
#   - text: ''
#     confidence: open
#     visibility: internal
#     scope: core
#     source_stakeholder_ids: []
#     reality_checked: false

# あるべき姿。journey_before / journey_after は業務シナリオを具体で書く。
to_be: []
# to_be:
#   - text: ''
#     confidence: open
#     scope: core
#     journey_before: ''
#     journey_after: ''
#     assumed_risks: []
#     transition_steps: []
#     evidenced_by: []

# 現状と理想の乖離(現象)。真因ではない。
# kind: perception(公開情報と実態の食い違い) | internal_conflict(立場による対立)
#     | goal(あるべき姿との差)
gaps: []
# gaps:
#   - text: ''
#     confidence: open
#     scope: core
#     kind: goal
#     from_as_is: []
#     from_to_be: []

# 真因。**confirmed のみ保存できる**。未検証の見立ては hypotheses(kind: cause)へ。
bottlenecks: []
# bottlenecks:
#   - text: ''
#     confidence: confirmed
#     scope: core
#     gap_ids: []
#     from_hypothesis: ''

# 解くべき課題。
challenges: []
# challenges:
#   - text: ''
#     confidence: open
#     scope: core
#     bottleneck_ids: []
#     cause_hypothesis_ids: []
#     cost_of_inaction: ''

# 動かせない条件(予算・期間・体制・法令・既存システム)。
constraints: []
# constraints:
#   - text: ''
#     confidence: open
#     scope: core

# 未確定事項。レビュー所見から参照されるためIDを持つ。
open_questions: []
# open_questions:
#   - text: ''
#     confidence: open
#     scope: core

# 指標。current_fact_id は `medo facts save` した実測値のIDを指す。
kpis: []
# kpis:
#   - name: ''
#     text: ''
#     confidence: open
#     current_fact_id: ''
#     target_value: null
#     target_text: ''
#     unit: ''
#     to_be_ids: []

# 関係者。誰かは text に書く(name フィールドは無い)。
# influence / interest: high | medium | low
stakeholders: []
# stakeholders:
#   - text: ''
#     role: ''
#     confidence: open
#     pains: []
#     stance: unknown
#     is_decision_maker: false
#     influence: medium
#     interest: medium
#     surfaced_by: stated

# 既往の取り組み。なぜ今まで解決していないかの核心。
# outcome: not_attempted | in_progress | stalled | failed | partial | succeeded
#   stalled / failed には blocker が必須。
# blocker_category: resource | politics_incentive | technical | governance | priority
attempts: []
# attempts:
#   - description: ''
#     outcome: not_attempted
#     blocker: ''
#     blocker_category: []
#     confidence: open
#     challenge_ids: []
#     gap_ids: []

# 未検証の見立て。kind: cause | solution | impact
hypotheses: []
# hypotheses:
#   - statement: ''
#     kind: cause
#     status: unvalidated
#     validation_method: ''
#     challenge_ids: []
#     evidence_refs: []

# 既に見えているシステム要件があれば(薄くてよい)。
functional: []
non_functional: {}

sources: []
knowledge_backend: markdown
"""
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest core/tests/test_templates.py -v`
Expected: PASS(6件)

`test_every_example_saves_through_the_store` が `bottleneck ... は confirmed のみ保存できます` で落ちる場合、雛形の `bottlenecks` の例が `confidence: confirmed` になっているか確認する。

- [ ] **Step 5: CLIの失敗するテストを書く**

`cli/tests/test_cli.py` に追記(`result.stderr` ではなく `result.output` を見るのが既存の慣習):

```python
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
```

- [ ] **Step 6: テストが失敗することを確認**

Run: `uv run pytest cli/tests/test_cli.py -k requirements_template -v`
Expected: FAIL — exit_code が 2(`No such command 'template'`)

- [ ] **Step 7: CLIを実装**

`cli/src/medo_cli/commands/templates.py`:

```python
"""雛形と registry の射影を返すコマンド。案件が無い状態でも呼べる。"""

import typer

from medo_core.templates import REQUIREMENTS_TEMPLATE


def requirements_template() -> None:
    """要件YAMLの雛形を出力する。埋めて `requirements save --file` に渡す。"""
    typer.echo(REQUIREMENTS_TEMPLATE)
```

`typer.Typer()` のサブアプリは作らず関数だけを公開する。サブアプリにすると階層が1段深くなり `medo requirements template template` になる。

`cli/src/medo_cli/main.py` の `requirements_app` 定義より後に登録する:

```python
from medo_cli.commands import templates as template_commands

requirements_app.command("template")(template_commands.requirements_template)
```

- [ ] **Step 8: テストが通ることを確認**

Run: `uv run pytest cli/tests/test_cli.py -k requirements_template -v`
Expected: PASS(2件)

- [ ] **Step 9: 全体を確認してコミット**

```bash
uv run pytest
uv run ruff check .
git add core/src/medo_core/templates.py core/tests/test_templates.py \
        cli/src/medo_cli/commands/templates.py cli/src/medo_cli/main.py cli/tests/test_cli.py
git commit -m "feat(core): 要件YAMLの雛形をCLIから取得できるようにする

Skillが要件を書くにはスキーマを知る必要があるが、SKILL.md本文に
書き写すとモデルが変わったときの遵守率が落ち、実装との二重管理に
なる。判断材料はCLIが返すという移植性条件を満たす。"
```

---

## Task 2: 討議用スライドの章構成をCLIが返す

**Files:**
- Modify: `core/src/medo_core/templates.py`
- Modify: `core/tests/test_templates.py`
- Modify: `cli/src/medo_cli/commands/templates.py`
- Modify: `cli/src/medo_cli/main.py`
- Modify: `cli/tests/test_cli.py`

**Interfaces:**
- Consumes: Task 1 の `templates.py`
- Produces:
  - `medo_core.templates.DISCUSSION_SLIDES_OUTLINE: str`
  - `medo_core.templates.DISCUSSION_CHAPTER_INPUTS: dict[str, tuple[str, ...]]`
  - CLI `medo artifacts outline --type slides --slide-kind discussion` → 章構成をstdoutへ、exit 0。`--slide-kind final` は未実装として exit 1

**なぜ必要か**: 討議用スライドは7章構成で、章2・章3には**破ると提案関係が壊れる**リフレーミング規約がかかる([スライド設計](../specs/phase2-slides-design.md) §2)。これを `medo-investigate` のSKILL.md本文に書くと本文が3倍に膨らみ、条件4に反する。

規約は**顧客提出物である `prfaq` の文章生成にも適用する**(同 §2 末尾)。そのため `medo-grow-prfaq` からも同じコマンドで取得できるようにする。

- [ ] **Step 1: 失敗するテストを書く**

`core/tests/test_templates.py` に追記:

```python
from medo_core.templates import DISCUSSION_CHAPTER_INPUTS, DISCUSSION_SLIDES_OUTLINE


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
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest core/tests/test_templates.py -v`
Expected: FAIL — `ImportError: cannot import name 'DISCUSSION_SLIDES_OUTLINE'`

- [ ] **Step 3: 章構成を実装**

`core/src/medo_core/templates.py` に追記:

```python
DISCUSSION_CHAPTER_INPUTS = {
    "本日の検証テーマ": ("hypotheses", "open_questions"),
    "現状の全体像": ("as_is",),
    "公開情報と現場実態": ("as_is", "gaps"),
    "立場による見え方の違い": ("gaps", "stakeholders"),
    "制約と、これまでの取り組み": ("constraints", "attempts"),
    "叩き台の理想像": ("to_be", "kpis"),
    "確認したいこと": ("open_questions", "hypotheses"),
}

DISCUSSION_SLIDES_OUTLINE = """\
# 討議用スライドの章構成(slide_kind: discussion)
#
# 目的は説得ではなく、認識の確認と過不足の洗い出し。最終提案と同じ構成にすると、
# まだ合意していない段階で結論を押し付ける資料になる。
# 1章=1枚に固定せず、情報密度の高い章は複数枚に展開してよい。
#
# 章0と章6には `medo status --view workflow` の値が要る:
#   workflow.loop.focus_hypothesis / workflow.checks.states

## 章0: 本日の検証テーマ
今回この場で確かめたいこと1点。入力: workflow.loop.focus_hypothesis。
未設定なら scope: core の open_questions の最上位を使う。それも無ければ
「本日確認したい範囲」として現状整理の対象セクションを述べる。**省略しない**。

## 章1: 現状の全体像
何を調べ、何が分かったか。入力: research 生成物 / as_is。

## 章2: 公開情報と現場実態  ★リフレーミング必須
外部から見える姿と実態の対比。入力: as_is(public / internal)/ gaps(kind: perception)。

## 章3: 立場による見え方の違い  ★リフレーミング必須・開示制御あり
認識が分かれている点。入力: gaps(kind: internal_conflict)/ stakeholders。
internal_conflict は提示相手に応じて開示・非開示を制御する。対立当事者が同席する
合同会議では出さず、個別のすり合わせで扱う。**どちらにするかユーザーに問う**。

## 章4: 制約と、これまでの取り組み
動かせない条件と、なぜ今まで解決していないか。入力: constraints / attempts。

## 章5: 叩き台の理想像
仮説としてのあるべき姿を2〜3案の振れ幅で提示。入力: to_be(confidence: assumed /
journey_before / journey_after)/ kpis。
**抽象論を出さない**。「業務が効率化される」ではなく「朝9時の伝票処理が、担当者の
手入力からシステム取込に変わる」と具体で示す。抽象的な理想像には訂正が入らず、
顧客は迎合するか沈黙する。
to_be が1件も無い周回では省略する。

## 章6: 確認したいこと
**見立て + 論点 + 選択肢**の形で提示して反論・選択を促す。入力: open_questions /
confidence: assumed の項目 / focus_hypothesis。
「この点は推測です。教えてください」は事前調査不足の丸投げと受け取られ、専門家と
しての信頼を失う。「公開情報と業界の一般的な構成からA案と推測しました。実際は
B案のパターンもあり得ますが、どちらに近いでしょうか」の形で、**推測の根拠と想定
パターンを示した上で選ばせる**。
その周回の focus_hypothesis を中心に置く。すべての未確定事項を一度に問わない。
`medo check list --confirmer customer` が返す項目のうち、`medo status --view workflow`
の checks.states が unverified のものを投影する。チェックリストの正本はCLI側にあり、
スライドはその投影である。文書に直接書き込まない。
答えが出ないことを失敗として扱わない。「あるべき姿がまだ描けない」は
`medo check add --result undeterminable` として記録し、それ自体を発見として扱う。

---

## リフレーミング規約(章2・章3に必須。prfaq の文章生成にも同じ規約を適用する)

認識GAPや立場の対立をそのまま「言動不一致の暴露」として提示すると、顧客の防衛反応を
招き対話が閉じる。**非難を伴わない表現へ変換する**。

| 変換前 | 変換後 |
|---|---|
| 対外的には〇〇と説明しているが実態は△△ | 外部環境の変化スピードに対し、現場の仕組みの追随には□□のタイムラグがある |
| 公約と実態が乖離している | 目指す姿と、現在の運用上の摩擦点 |
| 〇〇部と△△部の主張が食い違っている | 評価指標が部門間で相反しており、片方の改善が他方の不利益になる構造 |

**責任の所在ではなく、構造として描く**。引用するノードと出典は変えない。

### 誠実さを損なわないための線引き

| 外すもの | 保つもの |
|---|---|
| 誰が悪いか(責任の所在・個人や部門の名指し) | 何が起きているか(構造的弊害の深刻度・頻度・影響範囲) |
| 非難・断罪のトーン | 数値・事実・当事者の痛みの生々しさ |

**「タイムラグ・摩擦」への画一的な言い換えは禁止する**。実態が
blocker_category: politics_incentive(部門間の利害対立)や意図的なサボタージュで
ある場合、環境変化の物語に押し込めると問題の矮小化になり、真因が議題から消える。
この場合は**利害構造そのものを非人格的に描く**。
"""
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest core/tests/test_templates.py -v`
Expected: PASS(13件)

- [ ] **Step 5: CLIの失敗するテストを書く**

`cli/tests/test_cli.py` に追記:

```python
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


def test_artifacts_outline_reports_final_is_not_available_yet(medo_home: Path):
    """未実装を空出力で誤魔化すと、Skillが空の章構成で資料を作る。"""
    result = runner.invoke(
        app, ["artifacts", "outline", "--type", "slides", "--slide-kind", "final"]
    )

    assert result.exit_code == 1 and "error:" in result.output


def test_artifacts_outline_rejects_a_type_without_an_outline(medo_home: Path):
    result = runner.invoke(app, ["artifacts", "outline", "--type", "prfaq"])

    assert result.exit_code == 1 and "error:" in result.output
```

- [ ] **Step 6: テストが失敗することを確認**

Run: `uv run pytest cli/tests/test_cli.py -k artifacts_outline -v`
Expected: FAIL — exit_code が 2(`No such command 'outline'`)

- [ ] **Step 7: CLIを実装**

`cli/src/medo_cli/commands/templates.py` に追記:

```python
from medo_core.templates import DISCUSSION_SLIDES_OUTLINE

from medo_cli.commands._common import fail


def artifacts_outline(
    type: str = typer.Option(..., "--type", help="現在 outline があるのは slides のみ"),
    slide_kind: str = typer.Option(
        "", "--slide-kind", help="discussion(final は優先度6で未実装)"
    ),
) -> None:
    """生成物の章構成と表現の規約を出力する。"""
    if type != "slides":
        fail(f"{type} の章構成はありません")
    if slide_kind == "final":
        fail("slide_kind=final の章構成は未実装です(フェーズ2 優先度6)")
    if slide_kind != "discussion":
        fail(f"未知の slide_kind です: {slide_kind or '(未指定)'}")
    typer.echo(DISCUSSION_SLIDES_OUTLINE)
```

`cli/src/medo_cli/main.py` の `artifacts_app` 定義より後に登録する:

```python
artifacts_app.command("outline")(template_commands.artifacts_outline)
```

- [ ] **Step 8: テストが通ることを確認**

Run: `uv run pytest cli/tests/test_cli.py -k artifacts_outline -v`
Expected: PASS(4件)

- [ ] **Step 9: 全体を確認してコミット**

```bash
uv run pytest
uv run ruff check .
git add core/src/medo_core/templates.py core/tests/test_templates.py \
        cli/src/medo_cli/commands/templates.py cli/src/medo_cli/main.py cli/tests/test_cli.py
git commit -m "feat(core): 討議用スライドの章構成をCLIから取得できるようにする

リフレーミング規約は破ると提案関係が壊れる制約だが、SKILL.md本文へ
書くと本文が肥大しモデル差で遵守率が落ちる。章が使う要件セクションを
コードに持つことで、モデル変更時の乖離をテストで落とせる。"
```

---

## Task 3: checkの束縛と確認者をCLIが返す

**Files:**
- Modify: `cli/src/medo_cli/commands/templates.py`
- Modify: `cli/src/medo_cli/main.py`
- Modify: `cli/tests/test_cli.py`

**Interfaces:**
- Consumes: `medo_core.checks.CHECK_REGISTRY`
- Produces: CLI `medo check list [--confirmer customer|consultant|both] [--format json|digest]`

**なぜ必要か**: **`medo check add` は artifact束縛の項目に `--artifact` が必須で、指定しないと拒否される**(`source_quality` / `as_is_articulation` / `expression_safety`)。どの項目が artifact束縛かは `CHECK_REGISTRY` の中にしかなく、`status --view workflow` の `checks.states` は名前→状態しか返さない。Skillが束縛を知る手段が無いまま `check add` を案内すると、**手順どおり実行して失敗する**。

同じ理由で `confirmer`(顧客に確認する項目か、コンサル側で判断する項目か)も要る。討議用スライドの章6は「確認者が顧客の項目を投影する」と定めているが、その一覧を取る手段が無い。

- [ ] **Step 1: 失敗するテストを書く**

`cli/tests/test_cli.py` に追記:

```python
def test_check_list_reports_which_checks_need_an_artifact(medo_home: Path):
    """artifact束縛のcheckは --artifact なしでは拒否される。Skillは事前に知る必要がある。"""
    result = runner.invoke(app, ["check", "list", "--format", "json"])
    assert result.exit_code == 0

    by_name = {row["name"]: row for row in json.loads(result.output)}

    assert (by_name["as_is_articulation"]["binding"], by_name["as_is_articulation"]["target_type"],
            by_name["reality_gap"]["binding"]) == ("artifact_bound", "as-is-report", "persistent")


def test_check_list_filters_by_confirmer(medo_home: Path):
    """討議用スライドの章6には、確認者が顧客の項目だけを投影する。"""
    result = runner.invoke(app, ["check", "list", "--confirmer", "customer", "--format", "json"])

    assert [row["name"] for row in json.loads(result.output)] == [
        "as_is_articulation", "to_be_articulation", "scope_agreement",
    ]


def test_check_list_digest_is_the_default(medo_home: Path):
    result = runner.invoke(app, ["check", "list"])

    assert result.exit_code == 0 and "as_is_articulation" in result.output


def test_check_list_rejects_an_unknown_confirmer(medo_home: Path):
    result = runner.invoke(app, ["check", "list", "--confirmer", "vendor"])

    assert result.exit_code == 1 and "error:" in result.output
```

`test_check_list_filters_by_confirmer` の期待値は `CHECK_REGISTRY` の**定義順**である。実装では `CHECK_REGISTRY` の反復順をそのまま保つ(Python 3.7以降のdictは挿入順)。

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest cli/tests/test_cli.py -k check_list -v`
Expected: FAIL — exit_code が 2(`No such command 'list'`)

- [ ] **Step 3: CLIを実装**

`cli/src/medo_cli/commands/templates.py` に追記:

```python
import json

from medo_core.checks import CHECK_REGISTRY

CONFIRMERS = ("consultant", "customer", "both")


def check_list(
    confirmer: str = typer.Option("", "--confirmer", help="consultant|customer|both"),
    format: str = typer.Option("digest", "--format", help="json|digest"),
) -> None:
    """checkの束縛・対象生成物type・確認者・段階を出力する。"""
    if confirmer and confirmer not in CONFIRMERS:
        fail(f"未知の confirmer です: {confirmer}")
    if format not in ("json", "digest"):
        fail(f"未知の format です: {format}")

    rows = [
        {
            "name": name,
            "binding": spec.binding,
            "target_type": spec.target_type,
            "slide_kind": spec.slide_kind,
            "confirmer": spec.confirmer,
            "phase": spec.phase,
        }
        for name, spec in CHECK_REGISTRY.items()
        if not confirmer or spec.confirmer == confirmer
    ]
    if format == "json":
        typer.echo(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    for row in rows:
        target = f" target={row['target_type']}" if row["target_type"] else ""
        typer.echo(
            f"{row['name']}  binding={row['binding']}{target}"
            f"  confirmer={row['confirmer']}  phase={row['phase']}"
        )
```

`cli/src/medo_cli/main.py` の `check` グループ登録より後に、そのグループへ足す:

```python
workflow_commands.check_app.command("list")(template_commands.check_list)
```

`check_app` の実体名は `cli/src/medo_cli/commands/workflow.py` を読んで確認する。

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest cli/tests/test_cli.py -k check_list -v`
Expected: PASS(4件)

- [ ] **Step 5: 全体を確認してコミット**

```bash
uv run pytest
uv run ruff check .
git add cli/src/medo_cli/commands/templates.py cli/src/medo_cli/main.py cli/tests/test_cli.py
git commit -m "feat(cli): checkの束縛と確認者を一覧できるようにする

artifact束縛のcheckは対象IDなしでは記録できないが、束縛は registry の
中にしかなく status も名前と状態しか返さない。Skillが知る手段が無い
まま手順を書くと、そのとおり実行して失敗する。"
```

---

## Task 4: レビュー済みかどうかを status が返す

**Files:**
- Modify: `core/src/medo_core/context.py`
- Modify: `core/tests/test_status.py`

**Interfaces:**
- Consumes: `medo_core.context.StatusContext`
- Produces: `workflow.review.approved: bool` — 現在のレビュー対象(`current_target`)に `approved` のレビューが記録されているか

**なぜ必要か**: [Skill構成と移植性](../specs/phase2-skill-portability.md) §3 は「顧客に見せる資料は内部レビューを通してから使う」と定めている。ステージ3のSkillがこれを確認するには「現在の対象がレビュー済みか」を知る必要があるが、`workflow.review` は `current_target` と `open_findings` しか返さない。**レビュー未実施でも `open_findings` は空**なので、空であることを承認の証拠にできない。

**診断は報告であって強制ではない**(不変条件6)。`approved: false` でも保存や提示を拒否しない。Skillがユーザーに確認するための材料として返す。

- [ ] **Step 1: 失敗するテストを書く**

`core/tests/test_status.py` に追記(既存のヘルパー `_project` / `_doc` の使い方は同ファイル先頭を読んで合わせる):

```python
def test_review_is_not_approved_before_anyone_reviews(tmp_path):
    """レビュー未実施でも open_findings は空。空を承認の証拠にできない。"""
    status = project_status(_project(tmp_path), "p1", tmp_path, view="workflow")

    assert status["workflow"]["review"]["approved"] is False


def test_review_is_approved_after_an_approved_review_of_the_current_target(tmp_path):
    storage = _project(tmp_path)
    # as-is-report と討議用スライドを保存し、approved のレビューを記録する。
    # 具体の保存手順は core/tests/test_context.py の同種テストに合わせる。

    status = project_status(storage, "p1", tmp_path, view="workflow")

    assert status["workflow"]["review"]["approved"] is True
```

2つ目のテストは、`core/tests/test_context.py` にある `AsIsReportReviewed` を記録する既存テストの Arrange をそのまま流用して書く。**新しいヘルパーを作らず、既存のものに合わせる**。

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest core/tests/test_status.py -k review_is -v`
Expected: FAIL — `KeyError: 'approved'`

- [ ] **Step 3: `context.py` に承認状態を足す**

`workflow_branch` の `review` を次にする:

```python
        "review": {
            "current_target": ctx.target.as_is_report_id,
            "approved": _is_approved(ctx),
            "open_findings": ctx.open_review_findings,
        },
```

同ファイルに追加する:

```python
def _is_approved(ctx: StatusContext) -> bool:
    """現在のレビュー対象に approved のレビューがあるか。

    open_findings が空でも「まだ誰も見ていない」場合があり、空を承認の
    証拠にできない。
    """
    return any(
        event.kind == "asis_review"
        and event.outcome == "approved"
        and event.target.artifact_id == ctx.target.as_is_report_id
        for event in ctx.events
    )
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest core/tests/test_status.py -k review_is -v`
Expected: PASS(2件)

- [ ] **Step 5: 全体を確認してコミット**

```bash
uv run pytest
uv run ruff check .
git add core/src/medo_core/context.py core/tests/test_status.py
git commit -m "feat(core): レビュー済みかどうかを workflow 枝が返すようにする

顧客に見せる資料は内部レビューを通してから使うという契約を、Skillが
確認する手段が無かった。レビュー未実施でも open_findings は空になる
ため、空を承認の証拠にできない。"
```

---

## Task 5: `medo-investigate`(ステージ1: 調べる・仕立てる)

**Files:**
- Create: `skills/src/medo-investigate/SKILL.md`
- Modify: `skills/tests/test_build.py`

**Interfaces:**
- Consumes: Task 1 の `requirements template`、Task 2 の `artifacts outline`、Task 3 の `check list`
- Produces: Skill名 `medo-investigate`

**なぜ必要か**: ステージ1は唯一の入口である。[Skill構成と移植性](../specs/phase2-skill-portability.md) §7 は「全部を揃えないと動かない設計にしない」と定めており、`medo-investigate` **だけで**使い始められ、かつ**要件記録の時点で切り上げられる**必要がある。

- [ ] **Step 1: 失敗するテストを書く**

`skills/tests/test_build.py` を編集する。**このTaskで追加するのは `medo-investigate` の1本だけ**(未作成のSkill名を先に足すと、以降のTaskがテストの落ちた状態でコミットすることになる):

```python
SKILL_NAMES = [
    "medo-investigate",
    "medo-hearing", "medo-propose-options", "medo-grow-prfaq",
]

STAGE_SKILLS = ["medo-investigate"]


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
```

既存の `test_build_generates_skill_md_per_name` は `SKILL_NAMES` を使うため、そのままでよい。末尾の `medo-hearing` を参照する2行は Task 9 で差し替える。

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest skills/tests/test_build.py -v`
Expected: FAIL — `medo-investigate` が未作成で `FileNotFoundError`

- [ ] **Step 3: `medo-investigate` を書く**

`skills/src/medo-investigate/SKILL.md`:

```markdown
---
name: medo-investigate
description: 業界・ビジネス状況・現場の実態をヒアリングと調査で構造化し、出典付きファクトと要件ドキュメントとして保存する。必要なら現状調査・分析報告書と、顧客にぶつける討議用スライドまで作る。標準周回のステージ1(調べる・仕立てる)。
---

# medo-investigate: 調べる・仕立てる

公開情報と顧客の生の声を集め、現状を整理する。**手順4で終えてもよい**。報告書とスライドは、顧客にぶつける段になってから作る。

## 進め方

1. 現在地を読み、`actions`(次にできること)をユーザーに報告する:

       medo status --project <project-id> --view summary

   案件が未作成なら `actions` は返らず `next_step: hearing` になる。その場合は
   ユーザーと英数字slugのIDを合意してから進む。

2. 業界・市場・国策・業界動向を検索し(自分の検索能力を使う)、判断に効くファクトを保存する:

       medo facts save --project <id> --kind <market|policy|trend|company> \
         --statement "<出典の記述に忠実な一文>" --source <出典URL> \
         --value <数値> --unit <単位> --retrieved <YYYY-MM-DD>

   数値は出典に忠実に転記し、加工しない。ヒアリング由来の個社情報は
   `--kind company --source "ヒアリング(<日付> <相手>)"`。

3. 要件の雛形を取得して埋める:

       medo requirements template > /tmp/req.yaml

   既存案件を更新するときは代わりに `medo requirements get --project <id> --format json`
   の出力を編集する。**既存ノードの id は書き換えない**。
   雛形の例はコメントアウトされている。**埋める項目だけコメントを外す**。
   埋まらない項目は `open_questions` に置くか、何も書かない。勝手に埋めない。

4. 保存する。誤字・言い回しの修正だけのセクションは `--editorial <section>` を付ける:

       medo requirements save --project <id> --file /tmp/req.yaml
       medo status --project <id> --view summary

   **調査の初期はここで終えてよい**。`actions` を報告し、次に何を確かめるかを
   ユーザーと決める。報告書とスライドは顧客にぶつける段で作る。

5. 顧客に共有する段になったら、現状調査・分析報告書を書いて保存する:

       medo artifacts save --project <id> --type as-is-report \
         --requirements-version <n> --generated-by <claude|codex|gemini> \
         --file /tmp/as-is-report.md --cites-facts <fact-id,...>

   内部の調査ノートを別に残す場合は `--type research` で先に保存し、
   `as-is-report` に `--derived-from research-v<n>` を付ける。

6. 討議用スライドを作る。**章構成と表現の規約はCLIから取得する**:

       medo status --project <id> --view workflow
       medo artifacts outline --type slides --slide-kind discussion

   `workflow.loop.focus_hypothesis` が章0、`workflow.checks.states` が章6に要る。
   出力に従って `/tmp/slides.md` を書き、保存する:

       medo artifacts save --project <id> --type slides --slide-kind discussion \
         --derived-from as-is-report-v<n> --requirements-version <n> \
         --generated-by <claude|codex|gemini> --file /tmp/slides.md

7. 終了時に現在地を読み、`actions` を報告する:

       medo status --project <id> --view summary

   対話から得た案件固有ノウハウがあれば追記する:

       medo knowledge save --project <id> --statement "<ノウハウ>" \
         --source "medo-investigate <日付>対話"

   スライドまで作れたら「次は medo-review で内部検証する」と案内して終える。

## 契約(必ず守る)

- 開始時と終了時に `medo status --view summary` を実行し、`actions`(案件が未作成なら `next_step`)をユーザーに報告する。詳しい理由が要るときだけ `--view readiness` を追加で呼ぶ
- CLIが失敗したら推測で補完せず、エラー内容をそのまま報告する
- stale・未確認(`confidence: assumed` / `open`)・仮説の項目を引用するときは、その旨を明記する
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest skills/tests/test_build.py -v`
Expected: PASS(全件)

- [ ] **Step 5: 手順が実CLIと一致することを確認**

```bash
uv run medo requirements template | head -5
uv run medo artifacts outline --type slides --slide-kind discussion | head -5
uv run medo facts save --help
uv run medo artifacts save --help
uv run medo requirements save --help
```

Expected: SKILL.md に書いたオプション名がすべてヘルプに存在する。**フェーズ1で実在しないフラグを書いた事故があるため、この確認を飛ばさない**。

- [ ] **Step 6: コミット**

```bash
uv run pytest
uv run ruff check .
git add skills/src/medo-investigate/SKILL.md skills/tests/test_build.py
git commit -m "feat(skills): ステージ1のSkillを追加

決定論層は完成しているが手順書が無く、ホストLLMが標準周回を
回せない。ステージ1は唯一の入口であり、これ単独で使い始められ、
要件記録の時点で切り上げられる必要がある。"
```

---

## Task 6: `medo-review`(ステージ2: 内部検証)

**Files:**
- Create: `skills/src/medo-review/SKILL.md`
- Modify: `skills/tests/test_build.py`

**Interfaces:**
- Consumes: Task 3 の `check list`、Task 5 が保存した `as-is-report` と討議用 `slides`(CLI経由でのみ受け取る)
- Produces: Skill名 `medo-review`

**なぜ必要か**: 顧客に投影する資料こそリフレーミング規約が課される対象であり、提示前に内部レビューを通す必要がある。レビューは**別のホストで実行してよい**運用にすることで、サブエージェント機構なしに「作ったモデル ≠ レビューするモデル」を実現する([Skill構成と移植性](../specs/phase2-skill-portability.md) §5)。

- [ ] **Step 1: 失敗するテストを書く**

`skills/tests/test_build.py` の2つのリストに `medo-review` を足す:

```python
SKILL_NAMES = [
    "medo-investigate", "medo-review",
    "medo-hearing", "medo-propose-options", "medo-grow-prfaq",
]

STAGE_SKILLS = ["medo-investigate", "medo-review"]
```

さらに追加する:

```python
def test_review_reads_the_current_target_from_the_workflow_branch(tmp_path):
    """current_target は summary にも model にも無い。workflow 枝にしかない。"""
    assert "--view workflow" in _built(tmp_path, "medo-review")


def test_review_looks_up_which_checks_need_an_artifact(tmp_path):
    """artifact束縛のcheckは対象IDなしでは記録できず、手順どおり実行して失敗する。"""
    assert "medo check list" in _built(tmp_path, "medo-review")
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest skills/tests/test_build.py -v`
Expected: FAIL — `medo-review` が未作成で `FileNotFoundError`

- [ ] **Step 3: `medo-review` を書く**

`skills/src/medo-review/SKILL.md`:

```markdown
---
name: medo-review
description: 現状調査・分析報告書と討議用スライドを顧客に見せる前に内部検証し、論理矛盾・GAP・欠落と、顧客に見せてよいかの表現上の懸念を洗い出してレビュー結果を記録する。標準周回のステージ2(内部検証)。
---

# medo-review: 内部検証

顧客に出す前に論点を研ぐ。**このSkillは資料を作ったのとは別のホスト(Claude / Codex / agy)で実行してよい**。状態はすべてCLIにあるため、どのホストからでも同じ対象をレビューできる。

## 進め方

1. 現在地とレビュー対象を読む:

       medo status --project <project-id> --view summary
       medo status --project <project-id> --view workflow
       medo status --project <project-id> --view model

   `workflow.review.current_target` がレビュー対象の `as-is-report` ID
   (**summary にも model にも無い。workflow 枝を読む**)。
   対応する討議用スライドのIDは次で確認する:

       medo artifacts list --project <id>

   `model.links` と `model.coverage` が、繋がっていない要素と未検証の要素を返す。
   **これらは報告であって強制ではない**。埋まっていないこと自体を所見にしてよい。

2. 対象の本文を読む:

       medo artifacts get --project <id> --id <as-is-report-vN>
       medo artifacts get --project <id> --id <slides-vN>

3. 表現の規約を取得してスライドと突き合わせる:

       medo artifacts outline --type slides --slide-kind discussion

   章2・章3のリフレーミング規約に反する箇所、`internal_conflict` の開示制御が
   必要な箇所を所見にする。

4. 確認したチェック項目を記録する。何を確認すべきかは `actions` の `run_check` が、
   各項目の束縛は次が返す:

       medo check list

   `binding=artifact_bound` の項目(`source_quality` / `as_is_articulation` /
   `expression_safety`)は **`--artifact <対象ID>` が必須**で、無いと拒否される:

       medo check add --project <id> --check as_is_articulation \
         --result <completed|finding|undeterminable> --artifact <as-is-report-vN> \
         --refs <該当ノードID,...> --note "<所見>"

   `binding=persistent` / `version_bound` の項目は `--artifact` を付けない:

       medo check add --project <id> --check reality_gap --result completed --note "<所見>"

   判断できなかった項目は `--result undeterminable` で記録し、扱いを
   `--disposition open|deferred|promoted` で示す(既定 `open`)。
   **判断できなかったこと自体が発見**であり、隠さない。

5. レビュー結果を記録する:

       medo review add --project <id> --report <as-is-report-vN> --slides <slides-vN> \
         --outcome <approved|changes_requested> --reviewed-by <claude|codex|gemini|human> \
         --refs <要件側の所見ノードID,...> --slide-finding "<スライド固有の所見>"

   `--slides` は当該レポートから生成された討議用スライドである必要がある
   (CLIが検証する)。

6. 終了時に現在地を読み、`actions` を報告する:

       medo status --project <id> --view summary

   `approved` なら「次は medo-dialogue で顧客にぶつける」、
   `changes_requested` なら「medo-investigate で直して再生成する」と案内して終える。

## 契約(必ず守る)

- 開始時と終了時に `medo status --view summary` を実行し、`actions` をユーザーに報告する。詳しい理由が要るときだけ `--view readiness` を追加で呼ぶ
- CLIが失敗したら推測で補完せず、エラー内容をそのまま報告する
- stale・未確認(`confidence: assumed` / `open`)・仮説の項目を引用するときは、その旨を明記する
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest skills/tests/test_build.py -v`
Expected: PASS(全件)

- [ ] **Step 5: 手順が実CLIと一致することを確認**

```bash
uv run medo check list
uv run medo check add --help
uv run medo review add --help
uv run medo artifacts get --help
uv run medo artifacts list --help
```

Expected: `artifacts get` の引数が `--id` であること、`check list` の出力に `binding=` が含まれることを確認する。異なれば SKILL.md を実際の形に直す。

- [ ] **Step 6: コミット**

```bash
uv run pytest
uv run ruff check .
git add skills/src/medo-review/SKILL.md skills/tests/test_build.py
git commit -m "feat(skills): ステージ2のSkillを追加

顧客に投影する資料こそ表現の規約が課される対象であり、提示前に
検証を通す必要がある。別ホストで実行してよい運用にすることで、
サブエージェント機構なしに作成者とレビュアーを分ける。"
```

---

## Task 7: `medo-dialogue`(ステージ3: ぶつける・反応を得る)

**Files:**
- Create: `skills/src/medo-dialogue/SKILL.md`
- Modify: `skills/tests/test_build.py`

**Interfaces:**
- Consumes: Task 4 の `workflow.review.approved`、Task 6 が記録した `AsIsReportReviewed`(CLI経由)
- Produces: Skill名 `medo-dialogue`

**なぜ必要か**: 往復は頭の中では回らず、顧客の反応がないと暗黙知は出てこない。反応を構造化して記録することが次の周回の入力になる。

**`respond add` は purpose ごとに対象が決まっている**。`to_be_go_ahead` は要件宛てで、`--artifact` を付けると拒否される。手順にそのまま書くと必ず失敗するため、purpose 別に分けて書く。

- [ ] **Step 1: 失敗するテストを書く**

`skills/tests/test_build.py` の2つのリストに `medo-dialogue` を足し、追加する:

```python
def test_dialogue_does_not_attach_an_artifact_to_the_go_ahead(tmp_path):
    """to_be_go_ahead は要件宛て。--artifact を付けると拒否される。"""
    text = _built(tmp_path, "medo-dialogue")
    go_ahead = text[text.index("to_be_go_ahead") :][:400]

    assert "--artifact" not in go_ahead


def test_dialogue_checks_whether_the_target_was_reviewed(tmp_path):
    """open_findings はレビュー未実施でも空。空を承認の証拠にできない。"""
    assert "review.approved" in _built(tmp_path, "medo-dialogue")
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest skills/tests/test_build.py -v`
Expected: FAIL — `medo-dialogue` が未作成で `FileNotFoundError`

- [ ] **Step 3: `medo-dialogue` を書く**

`skills/src/medo-dialogue/SKILL.md`:

```markdown
---
name: medo-dialogue
description: レビュー済みの討議用スライドを顧客に提示する準備を整え、得られた確認・共感・異議をステークホルダーごとの反応として記録する。標準周回のステージ3(ぶつける・反応を得る)。
---

# medo-dialogue: ぶつける・反応を得る

**提示と反応の記録に専念する**。資料の生成は medo-investigate、検証は medo-review が済ませている。

## 進め方

1. 現在地を読み、提示できる状態か確認する:

       medo status --project <project-id> --view summary
       medo status --project <project-id> --view workflow

   - `workflow.review.approved` が `false` なら、まだ内部検証を通していない。
     medo-review を先に回すかをユーザーに確認する(**止めはしない**)
   - `workflow.review.open_findings` が空でなければ未解決の所見が残っている。
     そのまま提示するか先に直すかをユーザーに確認する
   - `workflow.loop.focus_hypothesis` がその周回で検証したい論点

2. 提示する討議用スライドを読む:

       medo artifacts get --project <id> --id <slides-vN>

   章3(立場による見え方の違い)を含む場合、**提示相手に応じた開示制御をユーザーに問う**。
   対立当事者が同席する合同会議では出さず、個別のすり合わせで扱う。

3. 章6の問いを、その周回の `focus_hypothesis` に絞って読み上げられる形に整理して渡す。
   顧客に確認する項目は次で取れる:

       medo check list --confirmer customer

4. 得られた反応を、**ステークホルダーごとに1件ずつ**記録する。
   **purpose によって対象の指定が変わる**:

   現状認識への反応(対象は as-is-report):

       medo respond add --project <id> --stakeholder <sh-N> \
         --artifact <as-is-report-vN> --purpose as_is_alignment \
         --reaction <empathized|acknowledged|agreed|objected|unclear> \
         --note "<相手の言葉に近い形で>"

   理想像を進めてよいかの返答(対象は要件。**`--artifact` を付けない**):

       medo respond add --project <id> --stakeholder <sh-N> \
         --purpose to_be_go_ahead \
         --reaction <empathized|acknowledged|agreed|objected|unclear> \
         --note "<相手の言葉に近い形で>"

   `unclear` は「反応が読み取れなかった」であり失敗ではない。沈黙や曖昧な同意を
   `agreed` に丸めない。
   語られた内容が要件の訂正・追加を含む場合、ここでは記録に留める。要件への反映は
   medo-decide が行う。

5. 顧客が答えたチェック項目を記録する。**artifact束縛の項目は `--artifact` が必須**
   (`medo check list` の `binding` を見る):

       medo check add --project <id> --check as_is_articulation \
         --result <completed|finding|undeterminable> --artifact <as-is-report-vN> \
         --note "<顧客の反応>"

   「あるべき姿がまだ描けない」「判断できない」という反応は
   `--result undeterminable --disposition open` で記録する。**それ自体が発見**である。

6. 終了時に現在地を読み、`actions` を報告する:

       medo status --project <id> --view summary

   「次は medo-decide で反応を要件に反映し、往復継続か次段階かを判断する」と
   案内して終える。

## 契約(必ず守る)

- 開始時と終了時に `medo status --view summary` を実行し、`actions` をユーザーに報告する。詳しい理由が要るときだけ `--view readiness` を追加で呼ぶ
- CLIが失敗したら推測で補完せず、エラー内容をそのまま報告する
- stale・未確認(`confidence: assumed` / `open`)・仮説の項目を引用するときは、その旨を明記する
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest skills/tests/test_build.py -v`
Expected: PASS(全件)

- [ ] **Step 5: 手順が実CLIと一致することを確認**

実データを壊さないコピーに対して、`to_be_go_ahead` に `--artifact` を付けないことを実行で確かめる:

```bash
uv run medo respond add --help
```

Expected: `--purpose` が `as_is_alignment|to_be_go_ahead|phase_signoff`、`--reaction` が `empathized|acknowledged|agreed|objected|unclear` であること。

- [ ] **Step 6: コミット**

```bash
uv run pytest
uv run ruff check .
git add skills/src/medo-dialogue/SKILL.md skills/tests/test_build.py
git commit -m "feat(skills): ステージ3のSkillを追加

往復は頭の中では回らず、顧客の反応がないと暗黙知は出てこない。
反応を構造化して記録することが次の周回の入力になる。"
```

---

## Task 8: `medo-decide`(ステージ4: 振り返る・次へ進む)

**Files:**
- Create: `skills/src/medo-decide/SKILL.md`
- Modify: `skills/tests/test_build.py`

**Interfaces:**
- Consumes: Task 7 が記録した `StakeholderResponded`(CLI経由)
- Produces: Skill名 `medo-decide`。4Skillが揃い、標準周回が1周する

**なぜ必要か**: 反応を要件に反映して次の周回へ渡す工程がないと、往復が1周で止まる。**回ること自体が価値**であり、`round_delta` で進んでいることを可視化する。

- [ ] **Step 1: 失敗するテストを書く**

`skills/tests/test_build.py` の2つのリストに `medo-decide` を足し、追加する:

```python
def test_decide_picks_one_focus_hypothesis_per_round(tmp_path):
    """論点を1つに絞らないと、蓄積した課題すべてに一律で向き合い周回が発散する。"""
    assert "--focus" in _built(tmp_path, "medo-decide")


def test_decide_keeps_node_ids_stable(tmp_path):
    """idを書き換えると過去のイベント・生成物の参照が別のノードを指す。"""
    assert "id は書き換えない" in _built(tmp_path, "medo-decide")
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest skills/tests/test_build.py -v`
Expected: FAIL — `medo-decide` が未作成で `FileNotFoundError`

- [ ] **Step 3: `medo-decide` を書く**

`skills/src/medo-decide/SKILL.md`:

```markdown
---
name: medo-decide
description: 顧客の反応とレビュー所見を要件ドキュメントに反映し、その周回で新たに分かったことを確認して、往復を続けるか次の段階へ進むかを判断する。ToBeチェックポイントへの回答も行う。標準周回のステージ4(振り返る・次へ進む)。
---

# medo-decide: 振り返る・次へ進む

**回ること自体が価値**である。チェックリストが埋まらなくても、周回を重ねること自体が解像度を上げる。

## 進め方

1. 現在地とその周回の成果を読み、ユーザーに報告する:

       medo status --project <project-id> --view summary
       medo status --project <project-id> --view workflow

   `workflow.loop.round_delta` が今回新たに分かったこと。`progress_count` が
   0 でなければ前進している。`divergence_warning` が真なら2周続けて成果ゼロで
   あり、論点の立て方をユーザーと見直す。
   `workflow.responses.effective` が有効な反応の一覧。

2. 反応と所見を要件に反映する。現在の要件を取得して編集する:

       medo requirements get --project <id> --format json > /tmp/req.json

   - `objected` / `unclear` の反応が指す内容を `as_is` / `to_be` などに反映する
   - 確認が取れた項目の `confidence` を上げる(`open` → `assumed` → `confirmed`)
   - **既存ノードの id は書き換えない**。書き換えると過去のイベント・生成物の
     参照が別のノードを指す
   - 真因が確定したら `bottlenecks` に置く。**`confirmed` のみ保存できる**ため、
     未検証のうちは `hypotheses`(`kind: cause`)に置いたままにする
   - 矛盾・判断不能が「解くべき課題」だと分かったら `challenges` に追加し、
     `promoted_from` に昇格元(`kind` と `ref`)を記録する

3. 保存する。誤字・言い回しの修正だけのセクションは `--editorial <section>` を付ける:

       medo requirements save --project <id> --file /tmp/req.json

   保存すると節目(`MilestoneDetected`)が自動で記録されることがある。

4. 節目が未回答なら回答する。`actions` の先頭が `answer_tobe_checkpoint` になる:

       medo checkpoint answer --project <id> --responds-to <ev-N> \
         --answer <generate|defer> --focus <hyp-N>

   `--focus` はその周回で検証したい仮説を1つ選ぶ。**これが無いと蓄積した課題と
   GAPすべてに一律で向き合うことになり、周回が発散する**。

5. 差分と陳腐化した生成物を確認する:

       medo requirements diff --project <id>

6. 終了時に現在地を読み、`actions` を報告する:

       medo status --project <id> --view summary

   - `readiness.state` が `ready` なら「収束条件を満たした。medo-propose-options で
     打ち手候補に進める」と案内する
   - そうでなければ「次の周回を medo-investigate から回す」と案内する
   - 詳しい理由が要るときだけ `medo status --view readiness` を呼び、
     `failed_conditions` を報告する

## 契約(必ず守る)

- 開始時と終了時に `medo status --view summary` を実行し、`actions` をユーザーに報告する。詳しい理由が要るときだけ `--view readiness` を追加で呼ぶ
- CLIが失敗したら推測で補完せず、エラー内容をそのまま報告する
- stale・未確認(`confidence: assumed` / `open`)・仮説の項目を引用するときは、その旨を明記する
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest skills/tests/test_build.py -v`
Expected: PASS(全件)

- [ ] **Step 5: 手順が実CLIと一致することを確認**

```bash
uv run medo checkpoint answer --help
uv run medo requirements diff --help
```

Expected: `--answer` の値域が `generate|defer` の2値、`--focus` が任意オプションとして存在する。

- [ ] **Step 6: コミット**

```bash
uv run pytest
uv run ruff check .
git add skills/src/medo-decide/SKILL.md skills/tests/test_build.py
git commit -m "feat(skills): ステージ4のSkillを追加

反応を要件へ戻す工程がないと往復が1周で止まる。周回ごとの成果を
可視化して、埋まっていない項目を数える道具にしないため。"
```

---

## Task 9: 既存Skillの移行と、まっさらな環境からの通し確認

**Files:**
- Modify: `skills/src/medo-hearing/SKILL.md`
- Modify: `skills/src/medo-propose-options/SKILL.md`
- Modify: `skills/src/medo-grow-prfaq/SKILL.md`
- Modify: `skills/tests/test_build.py`

**Interfaces:**
- Consumes: Task 5〜8 の4Skill
- Produces: 計7本(移行期間中)。`medo-hearing` は wrapper

**なぜ必要か**: `medo-hearing` は旧スキーマのYAMLを本文に持っており、フェーズ2の要件を保存できない案内をしている。設計は「移行期間中は薄いwrapperとして残し、統合完了後に削除する」と定めている。既存2本は `status` 呼び出しがフェーズ1の形で、契約も6項目あり**3項目に絞る規定**に反する。`generated_by` が `claude|gemini` のままで Codex 実行時に自己記録できない。**リフレーミング規約は `prfaq` の文章生成にも適用する**([スライド設計](../specs/phase2-slides-design.md) §2 末尾)が、`medo-grow-prfaq` にその案内が無い。

- [ ] **Step 1: 失敗するテストを書く**

`skills/tests/test_build.py` に追加し、既存の `test_build_generates_skill_md_per_name` 末尾の `medo-hearing` を参照する2行を削除する:

```python
def test_hearing_is_a_pointer_to_investigate(tmp_path):
    """旧スキーマのYAMLを案内し続けると、フェーズ2の要件を保存できない。"""
    text = _built(tmp_path, "medo-hearing")

    assert "medo-investigate" in text and "medo requirements save" not in text


def test_every_skill_reports_actions_from_status(tmp_path):
    """次に何をすべきかはCLIが返す。Skillが自前で判断すると本文が肥大する。"""
    missing = [
        name for name in SKILL_NAMES
        if name != "medo-hearing" and "--view summary" not in _built(tmp_path, name)
    ]

    assert missing == []


def test_every_skill_records_codex_as_a_possible_author(tmp_path):
    """3ホストで実行できる設計なのに、Codexが自分を記録できないと来歴が追えない。"""
    missing = [
        name for name in SKILL_NAMES
        if "--generated-by" in _built(tmp_path, name)
        and "codex" not in _built(tmp_path, name)
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
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest skills/tests/test_build.py -v`
Expected: FAIL — `test_hearing_is_a_pointer_to_investigate` / `test_every_skill_reports_actions_from_status` / `test_every_skill_records_codex_as_a_possible_author` / `test_grow_prfaq_applies_the_reframing_rule` / `test_no_skill_carries_more_than_three_contract_items` の5件

- [ ] **Step 3: `medo-hearing` を wrapper にする**

`skills/src/medo-hearing/SKILL.md` を全文置き換える:

```markdown
---
name: medo-hearing
description: 【medo-investigate に統合済み】課題ヒアリングの入口。medo-investigate を案内する移行用のポインタ。
---

# medo-hearing:(medo-investigate に統合済み)

ヒアリングは標準周回のステージ1「調べる・仕立てる」の一部になった。

**`medo-investigate` を使う**。ヒアリングで課題と方針を構造化し、出典付きファクトを保存し、必要なら現状調査・分析報告書と討議用スライドまで作る手順がそこにある。

このSkillは移行期間中のポインタであり、統合完了後に削除する。
```

- [ ] **Step 4: `medo-propose-options` を更新**

手順1を差し替える:

```markdown
1. 現在地を読み、`actions`(次にできること)をユーザーに報告する:

       medo status --project <project-id> --view summary

   `next_step` が `hearing` なら「まず medo-investigate で現状を構造化する」よう
   案内して終了する。続けて最新要件を取得する:

       medo requirements get --project <project-id> --format json
```

手順6の `--generated-by <claude|gemini>` を `--generated-by <claude|codex|gemini>` にする。

手順8を差し替える:

```markdown
8. 保存後 `medo status --project <project-id> --view summary` を実行し、`actions` を
   報告する。「候補セットを比較・Q&Aし、合意した打ち手を medo-grow-prfaq で完全版に
   育てる」ことを案内して終える。
```

`## 契約(必ず守る)` 以下を共通契約3項目に差し替える。**削る項目の内容は失われない**
— ファクト・ナレッジの出典必須と鮮度注記はCLIが返す `stale` フラグと契約3で、
フェルミ計算をLLMでやらないことは手順3の記述で担保される:

```markdown
## 契約(必ず守る)

- 開始時と終了時に `medo status --view summary` を実行し、`actions` をユーザーに報告する。詳しい理由が要るときだけ `--view readiness` を追加で呼ぶ
- CLIが失敗したら推測で補完せず、エラー内容をそのまま報告する
- stale・未確認(`confidence: assumed` / `open`)・仮説の項目を引用するときは、その旨を明記する
```

手順3の末尾に、契約から移した1行を足す:

```markdown
   **フェルミ推定の計算を自分で行わない**。必ず `medo fermi calc` の結果を使う。
```

- [ ] **Step 5: `medo-grow-prfaq` を更新**

同様に、`medo status --project <id>` の呼び出しをすべて `--view summary` 付きに変え、報告対象を `next_step` から `actions` に変える。`--generated-by` の値域に `codex` を足す。`medo-hearing` への言及があれば `medo-investigate` に置き換える。`## 契約` 以下を上と同じ3項目に差し替える。

さらに、PRFAQ本文を書く手順の直前に次を足す:

```markdown
   顧客提出物であるため、**表現の規約を取得して適用する**:

       medo artifacts outline --type slides --slide-kind discussion

   出力末尾のリフレーミング規約は、スライドだけでなくPRFAQの文章にも適用する。
```

- [ ] **Step 6: テストが通ることを確認**

Run: `uv run pytest skills/tests/test_build.py -v`
Expected: PASS(全件)

- [ ] **Step 7: 配布してホストから見えることを確認**

```bash
python skills/build.py
ls skills/dist/
```

Expected: 7ディレクトリ(`medo-investigate` / `medo-review` / `medo-dialogue` / `medo-decide` / `medo-hearing` / `medo-propose-options` / `medo-grow-prfaq`)

```bash
mkdir -p ~/.claude/skills ~/.codex/skills .agents/skills
cp -r skills/dist/* ~/.claude/skills/
cp -r skills/dist/* ~/.codex/skills/
cp -r skills/dist/* .agents/skills/
```

- [ ] **Step 8: まっさらな環境から標準周回を1周させる**

**実データに触れない**。空のディレクトリを `MEDO_HOME` にして、各SKILL.mdに書いたコマンドをそのまま実行する:

```bash
export MEDO_BACKEND=local MEDO_HOME=/tmp/medo-skills-smoke
rm -rf "$MEDO_HOME"

# ステージ1
medo status --project smoke --view summary                  # next_step: hearing
medo requirements template > /tmp/req.yaml
```

`/tmp/req.yaml` のコメントを外して次を埋める(**この最小データで一周できる**):

- `as_is` を1件(`visibility: internal` / `confidence: assumed`)
- `to_be` を1件(`confidence: assumed`)
- `stakeholders` を1件(`is_decision_maker: true`)
- `hypotheses` を1件(`kind: cause`)

```bash
medo requirements save --project smoke --file /tmp/req.yaml   # saved: v1
medo status --project smoke --view summary                    # actions が返る

printf '# 現状\n' > /tmp/as-is-report.md
printf '# 討議用\n' > /tmp/slides.md
medo artifacts save --project smoke --type as-is-report --requirements-version 1 \
  --generated-by claude --file /tmp/as-is-report.md
medo artifacts outline --type slides --slide-kind discussion | head -5
medo artifacts save --project smoke --type slides --slide-kind discussion \
  --derived-from as-is-report-v1 --requirements-version 1 \
  --generated-by claude --file /tmp/slides.md

# ステージ2
medo status --project smoke --view workflow                   # review.current_target
medo check list
medo check add --project smoke --check as_is_articulation --result completed \
  --artifact as-is-report-v1
medo check add --project smoke --check reality_gap --result completed
medo review add --project smoke --report as-is-report-v1 --slides slides-v1 \
  --outcome approved --reviewed-by human

# ステージ3
medo status --project smoke --view workflow                   # review.approved: true
medo check list --confirmer customer
medo respond add --project smoke --stakeholder sh-1 --artifact as-is-report-v1 \
  --purpose as_is_alignment --reaction empathized
medo respond add --project smoke --stakeholder sh-1 --purpose to_be_go_ahead \
  --reaction agreed

# ステージ4
medo status --project smoke --view workflow                   # loop.round_delta
medo requirements get --project smoke --format json > /tmp/req2.json
# as_is を1件足して保存 → 節目が記録される
medo requirements save --project smoke --file /tmp/req2.json
medo status --project smoke --view summary                    # actions[0]
medo checkpoint answer --project smoke --responds-to <ev-N> --answer generate --focus hyp-1
medo status --project smoke --view full
```

確認項目:

1. すべてのコマンドが exit 0 で通る(`--artifact` の要否・`--purpose` の対象がSKILL.mdの記述どおり)
2. 雛形をそのまま保存した直後の `diagnostic_phase` が `discovery` である
3. `check add --check as_is_articulation` は `--artifact` 無しでは失敗し、有りで成功する
4. `respond add --purpose to_be_go_ahead` は `--artifact` を付けると失敗する
5. `workflow.review.approved` が、レビュー前は `false`、`approved` 記録後は `true`
6. `workflow.loop.round_delta.progress_count` が 0 でない
7. `medo artifacts outline --type slides --slide-kind final` が exit 1 + `error:`

**1つでも失敗したら、失敗として記録し推測で補完しない**。SKILL.md 側の記述を実CLIに合わせて直す。

- [ ] **Step 9: 結果を記録して全体を確認し、コミット**

`docs/setup.md` に §6 として、上の通し確認で実行したコマンド列と確認項目の結果表を追記する。失敗した項目は失敗として書く。

```bash
uv run pytest
uv run ruff check .
git add skills/src/ skills/tests/test_build.py docs/setup.md
git commit -m "feat(skills): 既存Skillを標準周回の形に合わせる

medo-hearing は旧スキーマのYAMLを本文に持ち、フェーズ2の要件を
保存できない案内をしていた。既存2本は契約が6項目あり3項目に絞る
規定に反し、Codex実行時に自分を来歴として記録できなかった。"
```

---

## 完了の定義

- [ ] `medo requirements template` の出力をそのまま保存でき、**ノードが1件も作られず** `diagnostic_phase` が `discovery` のまま
- [ ] `medo artifacts outline --type slides --slide-kind discussion` が7章とリフレーミング規約を返す
- [ ] `medo check list` が各checkの束縛・対象type・確認者・段階を返す
- [ ] `medo status --view workflow` の `review.approved` が承認状態を返す
- [ ] 4ステージのSkillが揃い、いずれも `medo status --view summary` から単独で開始できる
- [ ] 各ステージSkillの本文が80行以内、契約が3項目以内(条件4・§4)
- [ ] `skills/build.py` が7Skillをビルドし、frontmatter検証を通る
- [ ] **まっさらな `MEDO_HOME` から標準周回を1周でき**、各SKILL.mdのコマンドが実CLIと一致する
- [ ] すべてのTaskで `uv run pytest` / `uv run ruff check .` が通った状態でコミットされている

## 次にやること(本計画のスコープ外)

- 優先度6: 最終提案スライド(`slide_kind="final"`)+ `phase_signoff` ゲート。`medo artifacts outline --type slides --slide-kind final` が exit 1 を返す箇所が着手点
- 設計の未決事項5「進行記録の状態をSkillが会話ログから正確に判定・更新できるか(未検証)」は、本計画のSkillを実案件で使い、`MEDO_TRACE` のトレースをホスト間でdiffして検証する

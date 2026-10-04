"""SkillがCLIから取得する雛形と registry の射影。

スキーマ・章構成・checkの束縛をSKILL.md本文へ書き写すと、ホストのモデルが
変わったときの遵守率が落ち、かつ実装との二重管理になる
(phase2-skill-portability.md 条件4)。
"""

from medo_core.nodes import (
    AsIs, Attempt, Bottleneck, Challenge, Constraint, Gap, Hypothesis, Kpi,
    OpenQuestion, Stakeholder, ToBe,
)
from medo_core.requirements import ConfidenceItem

WRITABLE_SECTIONS = (
    "industry", "background", "goal", "principles", "functional", "non_functional",
    "sources", "knowledge_backend", "challenges", "open_questions",
    "as_is", "to_be", "kpis", "stakeholders", "gaps", "bottlenecks",
    "constraints", "attempts", "hypotheses",
)

# 雛形がコメントで例示しているセクションと、その型。
# ここに載らないセクションは例の乖離検査から漏れるため、テストで一致を縛る。
NODE_EXAMPLES = {
    "principles": ConfidenceItem,
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
# kind によって参照の要件が変わる(満たさないと保存が拒否される):
#   perception       from_as_is に public と internal の AsIs を両方含める
#   internal_conflict from_as_is に internal な AsIs を2件以上。
#                     かつ source_stakeholder_ids が異なる(視点が違う)こと
#   from_to_be を持てるのは goal だけ。bottleneck が参照できるのも goal だけ。
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

DISCUSSION_CHAPTER_INPUTS = {
    "本日の検証テーマ": ("hypotheses", "open_questions"),
    "現状の全体像": ("as_is",),
    "公開情報と現場実態": ("as_is", "gaps"),
    "立場による見え方の違い": ("gaps", "stakeholders"),
    "制約と、これまでの取り組み": ("constraints", "attempts"),
    "叩き台の理想像": ("to_be", "kpis"),
    "確認したいこと": ("open_questions", "hypotheses"),
}

REFRAMING_RULE = """\
## リフレーミング規約(prfaq の文章生成にも同じ規約を適用する)

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
""" + REFRAMING_RULE

FINAL_CHAPTER_INPUTS: dict[str, tuple[str, ...]] = {
    "SCQAエグゼクティブサマリー": ("as_is", "challenges", "prfaq"),
    "As-Is vs To-Be 対比": ("as_is", "to_be", "kpis"),
    "GAPと真因": ("gaps", "bottlenecks", "attempts"),
    "打ち手比較と選定理由": ("prfaq", "rejected_options", "principles", "kpis"),
    "推奨ソリューション詳細": ("prfaq", "fermi", "constraints", "non_functional"),
    "ロードマップ": ("hypotheses",),
    "ネクストアクション(Ask)": ("open_questions", "hypotheses"),
}

FINAL_SLIDES_OUTLINE = """\
# 最終提案スライドの章構成(slide_kind: final)
#
# 合意形成の最後に、採択案と選定理由、実現の道筋、次工程の承認依頼を示す。
# 親は prfaq ちょうど1件。1章=1枚に固定せず、情報密度の高い章は複数枚に展開してよい。

## 章1: SCQAエグゼクティブサマリー
Situation-Complication-Question-Answerで提案の全体像を示す。
入力: as_is / challenges / prfaq の採択案。

## 章2: As-Is vs To-Be 対比
現状と理想、およびKPIの現状値から目標値への変化を対比する。
入力: as_is / to_be / kpis。

## 章3: GAPと真因  ★リフレーミング必須・開示制御あり
状態の乖離と、その裏にある真因、なぜ今まで解決に至っていないかを示す。
入力: gaps / bottlenecks / attempts。
提示相手に応じて開示・非開示を制御する。決裁者と関係部門が同席する合同会議では、
リフレーミング済みでも対立構造をそのまま投影せず、**出すかどうかをユーザーに問う**。

## 章4: 打ち手比較と選定理由
Impact × Feasibilityの比較と、どの評価軸で選び、なぜ他案を落としたかを示す。
入力: prfaq に取り込まれた打ち手比較 / rejected_options / principles / kpis。
比較の観点と評価は prfaq 本文から引き、選定理由を principles と kpis に紐づける。

## 章5: 推奨ソリューション詳細
選定案の具体像(How・Workflow Before/After)、効果の桁感、動かせない条件を示す。
入力: prfaq の技術的背景・workflow改善見込み / 保存済み fermi / constraints /
non_functional。**効果の数値は保存済み fermi からのみ引き、スライド生成で作らない**。
予算・体制の制約は constraints / non_functional から引く。複数枚に展開してよい。

## 章6: ロードマップ
段階と、各段階がどの仮説の検証に依存するかを示す。入力: hypotheses。

## 章7: ネクストアクション(Ask)
本日合意いただきたい事項(PoC実施・体制・スコープ・次工程)を示す。
入力: open_questions / hypotheses(status: unvalidated)。
**このAskは、次工程へ進むための phase_signoff の承認依頼として明記する**。

複雑な図解はMermaidまたは対比テーブルに割り切る(Marpの表現力の範囲内に収める)。

---
""" + REFRAMING_RULE

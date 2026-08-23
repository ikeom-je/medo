# Medo フェーズ2 設計ドキュメント

ステータス: レビュー中(3エージェント相互検証を2ラウンド実施済み。実装計画化の前にユーザー承認が必要)

正本: 本ファイル。全体設計は `medo-design.md` を参照し、本ファイルはフェーズ2の差分を定義する。

---

## 1. 目的とスコープ

フェーズ1は「What/Whyの合意形成」の縦切りを通した。フェーズ2は、その合意形成を**利用者が漏れなく重複なく進められるよう導く**支援に踏み込む。

利用者が求める論理連鎖:

```
事実調査(出典付き) → 現状(as-is)の共有
                          ↓
                    あるべき姿(to-be)・成功指標(KPI)の言語化
                          ↓
                    GAP(状態の乖離) → ボトルネック(真因)
                          ↓
                    課題(解くべき問い)+ 仮説(検証すべき前提)
                          ↓        ※制約条件の中で解く
                    優先度・効果の比較
                          ↓
                    共感できるドキュメント → スライド
```

**medoの位置づけ**: 利用者を導く支援ツールであり、判断を代行しない。フレームワークをパターンとして整理し、MECE(漏れなく重複なく)なヒアリングを支える。

---

## 2. 設計判断

### 判断1: フレームワークに基づく固定スキーマを持つ

汎用ノード+種別タグではなく、フレームワークに基づく**named field**として持つ。

**理由**: 支援ツールの役割は利用者を導くこと。項目が定義されていなければ「何が漏れているか」を機械的に指摘できず、MECEを担保できない。汎用ノードは自由度が高い代わりに、漏れの検出を利用者の記憶に依存させる。

### 判断2: 順序は固定しない

実案件は典型パターンに従わない。理想像から語り始めることも、特定の制約から入ることも、症状だけが見えている状態から始まることもある。

- **CLI(決定論)**: 構造の充足状況(空のセクション・assumed/openのみの項目・繋がっていないリンク)を返す
- **Skill(生成的)**: それを見て「次に何をどう問うか」を決める

利用者の話の流れが順序を決め、CLIは「今どこが埋まっていないか」だけを機械的に返す。

### 判断3: 顧客に直接問う項目と、Skillが下書きする項目を分ける

**相互レビュー(agy)の指摘を採用した最重要の判断**。スキーマが細分化された状態で「空欄を埋める」ことを機械的に追求すると、顧客が答えられない項目を質問し続ける**穴埋め尋問**になり対話が破綻する。

顧客はGAPと真因の区別、仮説の検証手順といったオントロジーに沿って話してくれない。

| 分類 | 項目 | ヒアリングでの扱い |
|---|---|---|
| **顧客に直接問う(初期必須ミニマム)** | `as_is` / `challenges`(顧客の生の声) / `constraints` / `stakeholders` | 顧客が答えられる。ここから始める |
| **合意を取りにいく** | `to_be` / `kpis` / `principles` | ブレストで一緒に言語化する |
| **Skillが下書きして確認する** | `gaps` / `bottlenecks` / `hypotheses` | 顧客に直接答えを求めない。対話内容からSkillが `confidence: assumed` で下書きし、「こういう真因と捉えて合っていますか」と**ぶつけて確認する** |

この運用契約をSkill本文に義務付ける。空欄は「顧客がまだ答えていない」だけでなく「Skillがまだ下書きしていない」場合もあり、後者はSkillの責務。

### 判断4: 要素間のリンクは任意にする

「すべての課題はGAPに紐づく」といった強制はしない。痛みは明確だが理想像が未言語化、という状態は実案件で普通に起きる。

**繋がっていないこと自体を情報として扱う**。エラーではなく現在地。

### 判断5: 解像度は confidence が制御する

「知らない顧客情報は仮説なので高解像度にしても判断できない」という懸念は、スキーマを粗くすることでは解決しない。既存の `confidence`(confirmed/assumed/open)が担う。

| confidence | 期待する解像度 |
|---|---|
| `confirmed`(利用者が明言 / 合意済み) | 高。判断に使える |
| `assumed` / `open` | 低くてよい。空欄のままでよい |

**空欄はペナルティではなく「まだ聞けていない/まだ下書きしていない」という情報**。

### 判断6: GAP(現象)とボトルネック(真因)を分離する

現象の差分をそのまま課題と呼ぶと対症療法しか出ない(agy指摘)。

```
to_be − as_is = gap(現象)
                  ↓ なぜ生じているか
              bottleneck(真因)
                  ↓ 何を解くべきか
              challenge(問い)
```

### 判断7: 未検証の真因は hypotheses に一元管理する

相互レビュー(agy)の指摘により、`bottlenecks` と `hypotheses(kind="cause")` の責務重複を解消する。

- **`bottlenecks`**: 検証・合意済みの真因のみ(`confidence: confirmed`)
- **`hypotheses(kind="cause")`**: 未検証・要検証の真因

仮説が検証されたら(`status: validated`)、`bottlenecks` に昇格させ、`from_hypothesis` に元の仮説IDを記録する。二重管理を避けつつ、昇格の経緯が追跡できる。

---

## 3. スキーマ設計

既存フィールドは維持し、追加はすべて既定値ありの additive change とする。

### 3.1 Node と ID の規約

```python
class Node(BaseModel):
    id: str = ""                    # 空なら保存時にcoreが採番
    text: str
    confidence: Confidence = "open"
    evidence_refs: list[str] = []   # fact-id / knowledge-id(出典による裏づけ)
```

**ID採番の契約**(Codex指摘により明文化):

- **IDはプロジェクト内でグローバル一意**。セクション別プレフィックスを付ける(`as-1` / `tb-1` / `gap-1` / `bn-1` / `ch-1` / `cs-1` / `kpi-1` / `sh-1` / `hyp-1`)
- **採番主体は core**。`id` が空のノードにのみ採番する(`KnowledgeStore.save` の既存方式と同じ)
- **既存IDの検証**: 保存時、指定されたIDが直前バージョンに存在するか検証し、**存在しないIDはエラーで拒否する**。ホストLLMがノードを書き写す際の採番ミス(勝手なリナンバリング)を機械的に検出するため
- **リンクは型付きにする**(汎用の `links: list[str]` にしない):

```python
class Gap(Node):
    from_as_is: list[str] = []       # as-is ノードID
    from_to_be: list[str] = []       # to-be ノードID

class Bottleneck(Node):
    gap_ids: list[str] = []
    from_hypothesis: str = ""        # 昇格元の仮説ID(判断7)

class Challenge(Node):
    bottleneck_ids: list[str] = []
```

型付きリンクにより、接続方向と許容する接続先が実装・検証可能になる。

### 3.2 RequirementsDoc の拡張

```python
class RequirementsDoc(BaseModel):
    # --- 既存(そのまま維持) ---
    project: str
    version: int
    industry: str
    background: str                  # 自由文の背景(as_is の導入として残す)
    goal: str                        # 一文のゴール(kpis が定量面を担う)
    principles: list[ConfidenceItem]
    functional: list[FunctionalRequirement]
    non_functional: dict[str, str]
    open_questions: list[str]
    sources: list[str]
    knowledge_backend: Literal["markdown", "sqlite"]

    # --- 型を変更(移行が必要) ---
    challenges: list[Challenge] = []  # ConfidenceItem から Challenge へ

    # --- 追加 ---
    as_is: list[Node] = []
    to_be: list[Node] = []
    kpis: list[Kpi] = []              # 成功指標(agy指摘により追加)
    stakeholders: list[Stakeholder] = []  # (agy指摘により追加)
    gaps: list[Gap] = []
    bottlenecks: list[Bottleneck] = []
    constraints: list[Node] = []      # 予算・期間・体制・法令・既存システム
    hypotheses: list[Hypothesis] = []
```

**`challenges` の移行方針**: `Challenge` は `ConfidenceItem` の上位互換(`text`/`confidence` を保持し `id` を追加)。既存JSONは `id` が無い状態で読めるため、**読み込み時に空IDとして扱い、次回保存時に core が採番する**。移行対象の実データは1プロジェクト(medo-ops、課題5件)のみで、破壊的変更は発生しない。

### 3.3 KPI とステークホルダー

相互レビュー(agy)の指摘により追加。フェルミ推定は効果の桁感を計算するが、**「どの指標をいくら改善するのか」を結ぶノードが無かった**。

```python
class Kpi(Node):
    name: str                      # 指標名
    current_value: float | None = None
    target_value: float | None = None
    unit: str = ""
    to_be_ids: list[str] = []      # どのあるべき姿に対応するか

class Stakeholder(Node):
    role: str = ""                 # 役割・立場
    pains: list[str] = []          # この立場固有の痛み
```

`stakeholders.pains` は Section 6 の共感要素②(読み手の痛みとBefore/After)の入力になる。

### 3.4 仮説(Hypothesis)

`confidence` は「今どれだけ確からしいか」、`Hypothesis` は「何を検証すれば確定するか」を持つ。両者は補完関係。

```python
class FermiRef(BaseModel):
    artifact_id: str               # 例: "fermi-v2"
    variable_name: str             # モデル内の assume 変数名

class Hypothesis(BaseModel):
    id: str = ""
    kind: Literal["cause", "solution", "impact"]
    statement: str
    validation_method: str = ""    # 何をすれば検証できるか
    status: Literal["unvalidated", "validating", "validated", "rejected"] = "unvalidated"
    evidence_refs: list[str] = []  # 検証済みの場合の fact-id / knowledge-id
    challenge_ids: list[str] = []
    fermi_ref: FermiRef | None = None   # kind="impact" の場合(感度分析の接続点)
```

**`fermi_ref` は Codex 指摘により、汎用の文字列リンクから型付き参照へ変更**。フェルミ変数は現状 `artifact.content` のJSON内にしか存在せず、文字列リンクでは特定できないため。

---

## 4. 充足状況の可視化(MECEの担保)

`medo status` を拡張し、**漏れ**を決定論的に返す。

```json
{
  "structure": {
    "as_is":        {"count": 3, "confirmed": 2, "empty": false},
    "to_be":        {"count": 0, "confirmed": 0, "empty": true},
    "kpis":         {"count": 0, "confirmed": 0, "empty": true},
    "stakeholders": {"count": 2, "confirmed": 2, "empty": false},
    "gaps":         {"count": 0, "confirmed": 0, "empty": true},
    "bottlenecks":  {"count": 0, "confirmed": 0, "empty": true},
    "constraints":  {"count": 1, "confirmed": 1, "empty": false},
    "challenges":   {"count": 5, "confirmed": 4, "empty": false}
  },
  "unlinked": {
    "challenges_without_bottleneck": ["ch-2", "ch-5"],
    "gaps_without_bottleneck": [],
    "to_be_without_kpi": ["tb-1"],
    "hypotheses_unvalidated": ["hyp-1", "hyp-3"]
  }
}
```

**重複(MECEのE)の検知はフェーズ2後半**とし、`knowledge-digest` と同じLLM注入方式(fake generate でテスト可能)で**提案専用機能**として実装する。決定論では意味的重複を判定できないため、検出は提案に留め、統合の判断は利用者が行う。

---

## 5. 陳腐化の粒度

### 5.1 決定: セクション単位 + カバレッジ判定 + 2段階の重大度

実データ(medo-ops の v1→v2: 課題1件追加・open_question1件解決)で4パターンを比較した結果:

| 粒度 | 判定結果 | 評価 |
|---|---|---|
| 文書全体(フェーズ1現状) | 3件すべてstale | fermi-v1 は要件に依存しないのに誤検出 |
| **セクション単位** | 2件stale | 誤検出を解消。**採用** |
| ノード単位(依存のみ) | **0件stale** | 「課題の追加」を検出できず取りこぼす |
| ノード単位+カバレッジ | 2件stale | 正確だが安定IDの全面移行が必要 |

**ノード単位の依存追跡だけでは不十分**である点が重要な発見。追加は既存ノードを変更しないため依存グラフでは何も壊れないが、実際には「打ち手が全課題をカバーしていない」状態になる。

### 5.2 変更の種類による2段階判定(agy指摘により追加)

軽微な文言修正で下流の全生成物が連鎖的にstale化すると、実務で再生成ループに陥る。**変更の種類で重大度を分ける**。判定は決定論で行える。

| 変更の種類 | 重大度 | 意味 |
|---|---|---|
| ノードの**追加・削除**、`confidence` の変更、リンクの変更、KPI目標値の変更 | **stale**(要再生成) | 論理構造が変わった |
| ノードの `text` のみの変更 | **outdated**(差分確認推奨) | 言い回しの修正の可能性が高い |

`medo status` は両方を返し、`next_step` は `stale` のみを再生成対象とする。

### 5.3 生成物の型ごとの依存セクション

**全ArtifactTypeを網羅する**(Codex指摘。旧案は `mock` / `comparison` が未定義だった)。生成物側の宣言は不要で、型ごとの固定ルールとして core が持つ。

| 生成物type | 依存セクション |
|---|---|
| `fermi` | なし(facts と assume のみに依存) |
| `mini-prfaq` | `goal` / `challenges` / `principles` / `constraints` / `to_be` / `kpis` |
| `prfaq` | 上記 + `bottlenecks` / `hypotheses` |
| `comparison` | `challenges` / `principles` / `constraints` / `kpis` |
| `slides` | 親artifact(`derived_from`)に委譲。要件への直接依存は持たない |
| `architecture` | `functional` / `non_functional` / `constraints` |
| `mock` | `functional` / `constraints` |

**比較の基準**: 直前バージョンではなく、**`artifact.requirements_version` の文書と最新版**を比較する(`RequirementsStore.get(project, version)` で任意版を取得できるため実装可能)。

### 5.4 カバレッジ判定

`Artifact` に **`covered_challenge_ids: list[str]`** を追加する。生成時点の要件に存在した課題IDのうち、その生成物が扱ったものを記録する。

最新要件の課題ID集合との差分に未対応のものがあれば `stale` とする。

**本文の文字列一致やLLM判定でカバレッジを推定しない**(設計原則「数値・事実の通り道にLLMを挟まない」に反するため)。Skillが保存時に明示的に宣言する。

### 5.5 生成物の依存グラフと stale 伝播

現状 `grown_from` は `prfaq` にのみ必須で、スライドがどのPRFAQ由来かを記録できない。Skill契約だけでは論理分岐を防げないため、スキーマで支える。

**2つの来歴概念を明確に分ける**(Codex指摘):

| フィールド | 意味 | 対象 |
|---|---|---|
| `grown_from` | **候補選択の来歴**(どの候補セットのどの打ち手を選んだか) | `prfaq`(既存・変更なし) |
| `derived_from` | **内容依存の親**(同じ論理の別表現) | `slides`(必須)・将来の派生生成物 |

**実装契約**:

- `ArtifactStore.save` で親が同一プロジェクトに実在し、期待する型であることを検証する(Pydantic単体ではStoreを参照できないため、検証箇所はStore)
- `status` は**全Artifactを `id -> Artifact` で保持して親を再帰評価**してから、表示用に型ごと最新版へ射影する(現行の `latest_by_type` は非最新版を捨てるため、親が旧版のPRFAQだと解決できない)
- 親の欠落・循環参照は例外にせず、**理由付きで stale** とする
- CLIに `--derived-from` を追加し、`slides` で許す親type(通常は `prfaq`)を契約として定める

---

## 6. 「共感できるドキュメント」の定義

相互レビューで Codex と agy が**独立に**「論理の一貫性は必要条件だが十分条件ではない」と指摘した(確度が高い)。以下の3要素として再定義する。

| 要素 | 内容 | 検証方法 |
|---|---|---|
| ①論理の一貫性 | as-is → to-be/KPI → gap → 真因 → 課題 → 打ち手 が繋がっている | **自動**(構造の充足とリンクで判定可能) |
| ②読み手の痛みとBefore/After | `stakeholders.pains` に紐づく具体的な痛み、変化後の体験 | 人間評価(スキーマが入力を保証) |
| ③トレードオフの誠実な開示 | 不確実性・リスク・**採らなかった選択肢とその理由** | 人間評価(`hypotheses` の未検証項目 + `rejected_options`) |

### 見送った案の理由を保持する(agy指摘により追加)

現状 `prfaq` は採択案のみを育成し、**却下案の見送り理由が失われる**。意思決定者の納得感はここで大きく変わる。

```python
class RejectedOption(BaseModel):
    name: str
    reason: str          # なぜ見送ったか
    accepted_risk: str = ""   # 見送りによって受け入れたリスク

# Artifact に追加
rejected_options: list[RejectedOption] = []   # prfaq で使う
```

これはmedo自身の表現の分担(コードコメント=Why not)と同じ思想である。スライドの比較マトリクスとQ&Aパートに反映する。

---

## 7. スライド生成の設計

**PRFAQの長文をそのままMarpに分割すると「文字だらけの箇条書き」になり、最も共感されない形式になる**(agy指摘)。`make-slides` は要約ではなく、**定型スライドパターンの構造化テンプレート**として設計する。

相互レビュー(agy)により、当初の5構成から**7構成へ改訂**。旧案は「打ち手を比較した後、どの案をどう具体化するか」の説明がないままロードマップへ飛び、かつ**意思決定依頼(Ask)の締めが無かった**。

| # | スライド | 内容 | 主な入力 |
|---|---|---|---|
| 1 | SCQAエグゼクティブサマリー | Situation-Complication-Question-Answer | `as_is` / `challenges` / 採択案 |
| 2 | As-Is vs To-Be 対比 | 現状と理想の対比、KPIの現状値→目標値 | `as_is` / `to_be` / `kpis` |
| 3 | GAPと真因 | 状態の乖離と、その裏にある真因 | `gaps` / `bottlenecks` |
| 4 | 打ち手比較と選定理由 | Impact × Feasibility マトリクス + **なぜ他案を落としたか** | `mini-prfaq` / `rejected_options` |
| 5 | 推奨ソリューション詳細 | 選定案の具体像(How・Workflow Before/After) | `prfaq` の技術的背景・workflow改善見込み |
| 6 | ロードマップ | 段階と、各段階がどの仮説の検証に依存するか | `hypotheses` / `decision-roadmap` |
| 7 | ネクストアクション(Ask) | **本日合意いただきたい事項**(PoC実施・体制・スコープ・次工程) | `open_questions` / `hypotheses(unvalidated)` |

複雑な図解はMermaidまたは対比テーブルに割り切る(Marpの表現力の範囲内に収める)。

---

## 8. 優先度・効果比較

単一の数値スコアはLLMの恣意的な採点になりやすく、過剰な数式化は軽さを失う(Codex/agy が独立に指摘)。

- **impact**: フェルミ推定の結果を参照(`fermi` artifact ID)。LLMが数値を作らない。`kpis` の目標値と結びつける
- **feasibility**: 技術ナレッジの確度 + `constraints` との突合
- **保存形式**: 「基準・根拠・確度」を持つ比較表として保存し、数値効果はフェルミ生成物への参照に留める

**感度分析**: `Hypothesis.fermi_ref`(3.4)により、「どの仮定がブレると効果の桁が変わるか」を決定論的に算出できる。これが `decision-roadmap` の検証優先度になる。

---

## 9. フェーズ2の優先順位

| 優先度 | 項目 | 備考 |
|---|---|---|
| **1** | 論理構造スキーマ + ID規約 + 移行 + 充足状況の可視化 | **ID採番・リンク契約・`covered_challenge_ids` を含める**。これが無いと2を開始できない(Codex指摘) |
| **2** | 陳腐化のセクション単位化 + カバレッジ判定 + 2段階重大度 | 1と密結合。飛ばすと全生成物が常時stale化して破綻 |
| **3** | 出典検証の強化(URLフェッチ + 数値突合) | **他と技術的に独立しており並行可能**(Codex指摘)。Task10で穴を実証済み |
| **4** | 生成物の依存グラフ + stale伝播 | `make-slides` の前提 |
| **5** | `make-slides`(7構成の構造化テンプレート) | 利用者の主要求 |
| **6a** | ナレッジ来歴スキーマ(`supersedes`・不変保存・旧引用の解決) | **6bの前提**。統合でIDが変わると過去の引用が全滅する |
| **6b** | `knowledge-digest`(LLMによる統合提案) | 統合後も旧entryを残し、過去Artifactの引用が検証可能であること |
| **7** | `decision-roadmap`(再定義) | 3.4の `fermi_ref` が前提。感度分析と連動 |
| 後続 | `build-mock` / `propose-architecture` / pricing(再定義) / 簡易Webアプリ | フェーズ2完了定義の改訂が必要(後述) |

### 相互レビューで訂正された当初案の誤り

- **pricing計算機の削除は誤り**: 「クラウド非依存」は「料金を扱わない」ことを意味しない。不正だったのはテスト方針(単一の公式Calculatorを正解に置けない)であり機能の要否ではない。**再定義して後送り**
- **簡易Webアプリの除外根拠が誤り**: 正本 `medo-design.md` はフェーズ2に明記しており、差別化軸の「単一のWebアプリに閉じる」は「Webアプリを作らない」という意味ではない。**優先度を下げるが除外しない**

### フェーズ2完了定義の改訂(要承認)

現行は「課題→What/Why合意→スライド+モックまで半日」だが、`build-mock` を後続に送るため改訂が必要:

> **改訂案**: 課題→What/Why合意(MECEな構造の充足を確認)→共感できるドキュメント+提案スライド(7構成)まで半日。knowledgeが案件を跨いで洗練される。

---

## 10. 未決事項

1. 重複検知(MECEのE)を `knowledge-digest` と実装共有するか、別機能にするか
2. `Kpi.current_value` を `facts` の値と自動照合するか(出典による裏づけの強制範囲)
3. 差別化の訴求(証跡追跡可能性をMoatとして押し出す)を正本のどこに書くか。**競合ツールの具体的な弱点は未検証のため、出典なしにドキュメントへ書かない**
4. `stakeholders` を要件ドキュメントに持つか、案件固有ナレッジ側に置くか(個人情報の扱いに関わる)

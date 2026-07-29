# Medo(目処) 設計ドキュメント

ステータス: 承認済み(スコープ再定義: What/Why主軸+PRFAQ、クラウド非依存ナレッジ層)

---

## 1. PRFAQ

### プレスリリース

**Medo(目処)— ビジネスの打ち手に「目処」をつける上流工程Agent。発想は自由に、事実は縛る**

業界・ビジネス状況・経営思想のヒアリングから始め、出典付きの市場・国策・業界動向データとフェルミ推定に裏づけられた打ち手候補(既存の解決/破壊的業務改革/新規市場開拓)をミニPRFAQとして並べ、What/Whyの合意を最速でつくる。合意した打ち手は、出典付き・鮮度保証付きの技術ナレッジ(案件を跨いで育つ)に基づく技術的背景・workflow改善見込み・効果を備えた完全版PRFAQに育て、「絵に描いた餅」にならない目処として持ち帰れる。実装手段としてGCPを選ぶ案件が多い想定だが、Medo自体はクラウド非依存で、AIのUIからバックエンド・インフラまで一貫構築できる実装先(GCP等)をHowの根拠として引用する形をとる。

課題も要件も最初から確定している必要はない。打ち手の比較やQ&Aで気づいた過不足は、どの段階からでも課題・方針・要件・ファクトに戻って更新し、下流の生成物を作り直せる。提案が引用する事実(市場数値・国策・業界動向・クラウド/技術サービスの新旧・GA/Preview状態・料金)は常に出典・取得日付きのデータに紐づくため、検討をやり直しても提案が揺れない。

Claude Codeやagy(Antigravity/Gemini)といった普段のAIツールからSkill+CLIとしてそのまま使える(フェーズ2で簡易Webアプリからの自然言語対話にも対応する)。ヒアリング・課題・方針・要件の成果は案件を跨いで蓄積され、業界ナリッジ・システムマップ資産としてチーム展開の土台になる。

### 顧客と課題

**顧客**: 利用者本人(自分および顧客のビジネス課題を整理し、打ち手と実装アーキテクチャ(主にGCPを想定)を検討・提案する立場)。将来は所属チーム。

**課題**:

1. What/Whyの合意がないままHow(システム要件・アーキ検討)に突入し、後戻りと手戻りが起きる
2. 市場・国策・業界動向を踏まえた打ち手の比較検討が毎回手作業で、提案の説得力が個人の経験と勘に依存する
3. アイデア段階の曖昧な入力から課題・要件を引き出す作業が毎回手作業で、成果が案件ごとに使い捨てになる
4. AI/ML系サービスの更新が速すぎて、LLMの学習知識では「今なら解決できるようになったこと」を見落とす
5. 新機能のPreview/GA・安定性・事例有無という「判断に効くメタ情報」が単発プロンプトでは取れない
6. 提案がプロンプト次第・実行ごとに揺れて、比較検討や意思決定の土台にならない
7. 顧客に見せられる形(PRFAQ・スライド・動くモック)にするまでが遠く、提案・意思決定が遅い

### FAQ(抜粋)

**Q. なぜPRFAQ形式なのか?**
打ち手を「顧客に届いた未来」の形で記述することで、価値仮説(What/Why)と実現手段(How)と効果を1つのドキュメントで検証できるため。打ち手ごとにミニPRFAQを作れば同じ土俵で比較・Q&Aでき、合意後は同じドキュメントを完全版PRFAQ(技術的背景・workflow改善見込み・ロードマップ付き)に育てられる。要件と同じく「生きた成果物」として扱う。

**Q. 方針や理念はどう扱うのか?**
個社の経営思想・理念・方針は検索で取れる「事実」ではなく、ヒアリングとブレストで引き出し・合意する対象。要件ドキュメントの `principles` に confidence 付きで記録し、打ち手の評価軸(理念との整合)として使う。

**Q. 将来の市場予測はどう「事実は縛る」のか?**
将来予測は「出典付きファクト(国策・業界動向・統計)× 明示された仮定 × コードによる計算」で構成する。ファクトは常に出典必須であり、成長率などに出典があれば policy/trend ファクトとして保存して参照し、出典がなければフェルミモデル側の**明示的仮定(assume)**として記録する — 仮定をファクトと混同させない。フェルミ推定の計算はLLMではなくコード(fermi計算機)が行い、予測の根拠(どのファクト・どの仮定・どの式)は生成物から全て追跡できる。

**Q. コンサルティングファームやリサーチツールとの違いは?**
目的は網羅的な市場調査レポートではなく「意思決定の目処」。案件に必要な範囲のファクトを出典付きで素早く集め、フェルミ推定で桁感を合わせ、ミニPRFAQで比較可能にする。技術的実現性(How)まで同じ場で、出典付き・鮮度保証付きの技術ナレッジ(案件を跨いで蓄積・洗練される)に基づいて目処を付けられる点がリサーチ専業と異なる。

**Q. なぜmulti-agentにしないのか?**
課題はエージェントの自律性不足ではなく、根拠データの鮮度と出力の再現性の不足だから。自律的なエージェント間対話は非決定性を増やし、課題と正面から矛盾する。「手順=Skill、事実と計算=CLI、かさばる検索=ホストLLM+出典検証」という分担で解く。

**Q. 既存のマルチクラウド設計比較Agent事例との違いは?**
それらは「その場でKnowledge MCPを検索して一発生成」であり、(1) 実行ごとに結果が揺れる、(2) Preview/GA・料金の決定論的な扱いがない、(3) 課題・要件が固定入力で育てられない、(4) 成果物が蓄積されない、(5) そもそもWhat/Whyを扱わない。MedoはWhat/Whyの合意形成を主戦場とし、鮮度付き技術ナレッジ・決定論計算・生きた要件ハブ・案件横断の蓄積で支える。

**Q. コーディング支援系のOSS Agentツールとの違いは?**
コーディング支援ではなく、上流工程の提案と意思決定の高速化が目的。モック生成も「作るため」ではなく「合意形成のため」。

**Q. なぜMCPサーバーを最初に作らないのか?**
主要ホスト(Claude Code / agy / codex)はシェルが使えるため、Skill+CLIの方がコンテキスト効率が良い。MCPは同じコアの薄いアダプタとして、シェルなしホストが必要になった時点で追加する。

**Q. ハルシネーションをどう防ぐのか?**
「発想は自由、事実は縛る」。打ち手の発想・PRFAQの文章は創造的な生成物だが、引用する市場数値・国策・業界動向・技術/サービス情報(launch_stage・料金等)は必ずCLIが検証・保存した出典付きファクト・技術ナレッジを使う。保存後の数値の通り道にLLMを挟まない(フェルミ推定もコードが計算する)。LLMが数値に触れるのは出典からの初回転記のみで、転記は出典に忠実・無加工とし、出典・取得日の必須保存で常に人間が検証できる(フェーズ2でCLIの出典照合検証を追加)。ツール失敗時は推測で補完せず失敗を報告する。

**Q. 成功の姿は?**
課題を話してから半日以内に、市場・国策・業界動向データとフェルミ推定に裏づけられた打ち手のミニPRFAQ比較でWhat/Whyに合意し、合意案の完全版PRFAQ(技術的背景・workflow改善見込み・効果・ロードマップ)まで持ち帰れる。

### 利用スコープ(初期)

- 利用者: 本人のみ(認証・マルチテナントなし)
- 技術ナレッジ範囲: 事前の自動カタログ化はしない。案件で必要になった技術・サービス情報(実装手段としてGCPを想定することが多いが非依存)をホストLLMが検索→出典検証して`knowledge/`に保存し、案件を跨いで再利用・育成する
- 市場ファクト範囲: 案件ごとに必要な範囲をその都度収集(事前カタログ化しない)
- ホスト: Claude Code / agy + 簡易Webアプリ(フェーズ2)

---

## 2. 全体アーキテクチャ

```
[ホスト]   Claude Code / agy (Skill+CLI)        簡易Webアプリ(フェーズ2, Gemini)
              │                                      │
[Skill層]  hearing / propose-options / grow-prfaq
           (フェーズ2: make-slides / build-mock / propose-architecture /
            decision-roadmap) … 手順書(生成的)。CLI呼び出し手順を含む
              │ シェル実行                            │ 関数呼び出し
[CLI/コア] medo CLI ── core(ドメインロジック):
              requirements(課題・方針・要件のバージョン管理・差分) /
              facts(市場・国策・業界動向・個社ファクト。案件スコープ・出典必須・鮮度判定) /
              fermi(仮定×式の決定論計算。LLM不使用) /
              knowledge(技術ナレッジ[案件横断]+案件固有ナレッジ[単一案件]照会・鮮度判定) /
              artifacts(生成物の保存・紐づけ) /
              pricing(フェーズ2)
              │
[知識層]   Firestore(本番) or ローカルJSON(開発) + GCS(フェーズ2)
           knowledge/ は案件データと分離した専用ストア(既定: MEDO_HOME配下の別gitリポジトリ。
           git履歴がレビュー記録になる。GitHub公開のmedoツールリポジトリには含めない)。
           案件固有ナレッジは同リポジトリ内 knowledge/projects/{id}/ に同居(バックエンドは
           案件ごとにmarkdown|sqliteを選択、フェーズ2でObsidian/Notion外部連携を追加)
              ↑
[洗練フロー] フェーズ1: ホストLLMが検索→CLIが出典検証して保存(facts同様)+ git履歴による参照・レビュー
           フェーズ2: knowledge-digest(収集データの分析・統合による洗練。重複検知・要約統合)
           (市場ファクトは自動収集しない: 案件毎にホストLLMが検索し、CLIが出典検証して保存)
```

### 役割の三分担

| 役割 | 担当 | 決定論性 |
|---|---|---|
| 手順(ヒアリング・打ち手提案・PRFAQ育成の進め方) | Skill(ホストLLMが実行) | 生成的 |
| 事実と計算(ファクト保存検証・フェルミ計算・技術ナレッジ・料金・要件保存) | medo CLI + core | 決定論 |
| かさばる検索(市場・国策・業界動向・技術/サービス情報) | ホストLLMの検索能力 +(フェーズ2)knowledge-digest | 生成的だが出典必須 |

- LLM選定: ホスト側はClaude(Claude Code)/Gemini(agy)。フェーズ2 knowledge-digestの構造化はGemini Flash等。
- **数値の通り道にLLMを挟まない**: 保存済みファクト・ナレッジ値の参照、フェルミ計算、料金計算は常にコードが行う。LLMが数値に触れるのは**出典からの初回転記のみ**(市場ファクト・技術ナレッジの抽出)であり、転記は出典に忠実に行い加工しない(単位換算・集計が必要な場合はfermiで行う)。この転記精度がホストLLM依存であるトレードオフは認識した上で、出典・取得日の必須保存により人間が常に検証できる状態を保ち、フェーズ2でCLIによる出典照合検証(URLフェッチ+数値突合)を追加して縛りを強化する。

### データフロー: ハブ&スポーク

要件ドキュメント(課題・方針・要件)がハブ。各生成物はその時点の要件バージョンに紐づく。

1. `hearing` Skill: 業界・ビジネス状況・課題・経営思想/方針を対話とブレストで構造化 → `medo requirements save`(v1。この時点ではビジネス文脈とopen_questionsが中心で、システム要件は薄くてよい)
2. `propose-options` Skill: ホストLLMが市場・国策・業界動向を検索 → `medo facts save`(出典検証付き保存。数値は出典に忠実に転記)→ `medo fermi calc`(効果・市場規模の桁感をコードが計算)→ 打ち手候補2〜3案(既存の解決/破壊的業務改革/新規市場開拓 × スコープ/立ち位置/根本治療の切り口)を生成し、**各案の「Howの目処」は `medo knowledge search` の技術ナレッジ根拠に縛って**記述(cited_knowledgeに記録)→ 各案のミニPRFAQを**1つの候補セットドキュメント**にまとめて保存 → `medo artifacts save --type mini-prfaq`(候補セット=1生成物。バージョンは候補セットの改訂を表す)
3. **比較・Q&A・合意**: ミニPRFAQ候補セットで意思決定。Q&Aで気づいた過不足は要件・ファクトに反映(v2)→ 陳腐化した生成物を検出 → 再生成。合意はツールの外で行われる人間の意思決定であり、次ステップのSkillが「どの打ち手に合意したか」を確認する
4. `grow-prfaq` Skill: 開始時に合意した打ち手をユーザーに確認し、完全版PRFAQに育成。技術的背景・workflow改善見込みは `medo knowledge search` の技術ナレッジ根拠に縛る → `medo artifacts save --type prfaq`(`grown_from` に元のミニPRFAQ候補セットIDと選択した打ち手名を記録し、育成履歴を追跡可能にする)
5. フェーズ2: `make-slides`(スライド仕上げ)・`build-mock`・`propose-architecture`(アーキ詳細)・pricing
6. 成果はFirestoreに蓄積され、次案件で類似案件参照として効く(将来)

### 現在地の可視化(medo status)

`medo status --project <id>` が保存状態から**決定論的に**現在地レポートを返す(LLMを挟まない):

- 要件: 最新バージョン、confidence別件数、open_questions件数
- ファクト: 件数・staleの有無
- 生成物: **typeごとの最新バージョンのみ**をtype昇順で返す(陳腐化staleフラグ付き)
- **陳腐化判定**: 依存する `requirements_version` が最新要件より古い場合に加え、**引用根拠にstaleまたは欠落がある場合**(`cited_facts` のファクト=180日超過、`cited_knowledge` のナレッジエントリ=kind別閾値超過。既定は`tech`=30日・他=180日)も陳腐化として扱う(「事実は縛る」を生成物のライフサイクルまで貫く)
- `next_step`(優先順): 要件なし→`hearing` / typeごとの最新生成物に陳腐化あり→`regenerate-stale-artifacts` / mini-prfaqなし→`propose-options` / prfaqなし→`grow-prfaq`(合意を経て実行。合意の確認はgrow-prfaq Skill冒頭の責務) / それ以外→`up-to-date`(フェーズ2で make-slides 等に拡張)

各Skillは開始時(プロジェクトID既知の場合のみ)・終了時に `medo status` を実行し、現在地と次ステップをユーザーに報告する(共通契約)。プロセス全体像は `docs/usage.md`(人間用)に置く。

### Claude vs Gemini の生成物比較

`grow-prfaq` や `make-slides` は同一Skill・同一要件・同一ファクト根拠で、Claude Code(Claude)とagy(Gemini)の双方から実行できる。生成物メタデータに `generated_by: claude|gemini` を記録し、両者の出力を並べて比較・選択できる。Skill本文は共通markdownとして1箇所で管理する。

---

## 3. リポジトリ構成(モノレポ)

uv workspaceによるPythonモノレポ。

```
medo/
├── core/            # ホスト非依存ドメインロジック
│   ├── requirements # 課題・方針・要件(スキーマ・バージョン管理・差分)
│   ├── facts        # 市場・国策・業界動向・個社ファクト(案件スコープ・出典必須・鮮度判定)
│   ├── fermi        # フェルミ推定の決定論計算(安全な式評価。LLM不使用)
│   ├── knowledge    # 技術/サービスナレッジ(案件横断スコープ・型・クエリ・鮮度判定。factsと同型スキーマを共有)
│   ├── artifacts    # 生成物(保存・要件バージョン紐づけ)
│   ├── status       # 現在地とnext_stepの決定論導出
│   └── pricing       # (フェーズ2)
├── cli/             # medo CLI(requirements / facts / fermi / knowledge / artifacts / status)
├── skills/          # Skill本文(共通md)+ ビルドアダプタ
├── webapp/          # (フェーズ2)
└── docs/
```

将来追加(バックログ): `mcp-server/`、`a2a-server/`(Gemini Enterprise接続)。

---

## 4. データモデル

### 要件ドキュメント(ハブ) — `projects/{id}/requirements/v{n}`

```yaml
project: "yoyaku"
version: 3            # 更新のたびにインクリメント、旧版保持
industry: "飲食"       # 蓄積・類似案件検索のキー
background: "インバウンド客の増加と人手不足が同時進行。電話予約の外国語対応が限界…"  # 業界・ビジネス状況の要約
principles:            # 経営思想・理念・方針(ヒアリング・ブレストで引き出し合意する。検索対象ではない)
  - text: "地域の食文化を海外客に開くことを成長軸にする"
    confidence: confirmed | assumed | open
challenges:            # 課題(What/Whyの起点)
  - text: "外国語の電話予約に対応できず機会損失が発生"
    confidence: confirmed | assumed | open
goal: "..."            # 打ち手の合意とともに確定していく一文
functional: [...]      # システム要件(打ち手合意後に育つ。confidence付き)
non_functional: {performance: ..., availability: ..., security: ..., budget_cap: ...}
open_questions: [...]  # 未確定事項 = 次のヒアリング質問リスト = 意思決定の不確定パラメタ
sources: [...]         # ヒアリングメモ・参考URL
```

`confidence` と `open_questions` が「課題も要件も最初から確定しない」の実装。`principles` は打ち手の評価軸(理念との整合)として `propose-options` が参照する。

**後方互換**: `background`(既定 `""`)・`principles` / `challenges`(既定 `[]`)は追加フィールドであり、既存の保存済みドキュメント(Task 1〜6時点のスキーマ)はそのままバリデーションを通る(additive change)。

### 市場ファクト — `projects/{id}/facts/{fact_id}`

```yaml
kind: market | policy | trend | company
  # market: 市場統計(規模・単価・人口動態)
  # policy: 国策・規制・補助金(将来予測の根拠)
  # trend:  業界動向(レポート・ニュース)
  # company: 個社情報(ヒアリング・顧客資料由来)
statement: "訪日外国人旅行者数 3,687万人(2024年)"
value: 36870000        # 数値がある場合(フェルミ推定から参照される)
unit: "人"
source: "https://www.jnto.go.jp/..."   # 必須(下記のkind別ルール)
retrieved: "2026-07-01"
note: "..."
```

- **ファクトは常に「出典のある事実」**: 仮定はファクトにしない(仮定はフェルミモデルの `assume` 変数としてのみ存在する)。この境界により「出典付きファクト」と「明示的仮定」が混ざらない
- **出典のkind別ルール**(CLIがバリデーション): `market` / `policy` / `trend` は `source` にURL必須(URL形式を検証)。`company` は `source` に由来表記(例: 「ヒアリング(2026-07-01 顧客X)」「顧客提供資料: 2025年度売上報告」)必須。いずれも空は拒否
- **鮮度契約**: `retrieved` から180日超で `stale: true` を全CLIレスポンスに付与(市場データは技術ナレッジ(kind: tech、30日)より劣化が遅い)。Skillはstaleファクト引用時に注記義務
- `kind: company` はヒアリング・顧客資料由来であり、Web検索の対象ではない

### フェルミ推定 — 決定論計算(`medo fermi calc`)

```yaml
name: "多言語予約対応の市場機会(年間)"
variables:
  visitors: {fact: "fact-001"}             # 市場ファクト参照(valueを使う)
  dining_rate: {assume: 0.8, note: "外食利用率の仮定"}  # 明示的仮定
  unit_price: {fact: "fact-002"}
formula: "visitors * dining_rate * unit_price"
```

- 計算は**コードが実行**する(astベースの安全な演算のみ: 四則演算+累乗。CAGR等の複利計算に累乗が必要。LLM・`eval`不使用)
- **生成物(`type: fermi`)はモデル(variables・formula)と計算結果の両方を保存**し、根拠(参照ファクトID・仮定・式・計算値)を後から全て追跡できる
- **再計算**: `medo fermi calc --from-artifact <id>` が保存済みモデルからファクトを最新値で再解決して再計算する(新バージョンとして保存)。ファクトのstale・更新で fermi 生成物が陳腐化した場合、CLI単独で再生成できる
- 将来予測は policy/trend ファクトを成長率等の根拠に使い、同じ仕組みで計算する

### 技術ナレッジ — `knowledge/{kind}/{entry_id}`(案件横断スコープ)

```yaml
kind: tech | market | policy | trend | company   # factと同じ語彙 + "tech"(技術/サービス能力に関するナレッジ)
statement: "Vertex AI context caching は 2026年時点でGA"
value: null             # 数値化できる場合はfactと同様value/unitを使う(例: 料金の目安)
source: "https://cloud.google.com/vertex-ai/docs/..."   # 必須
retrieved: "2026-07-01"
note: "..."
```

- factと同一スキーマ・同一バリデーション(出典必須・URL検証)を共有する薄い`KnowledgeStore`として実装し、保存先ルートのみ案件横断(`knowledge/`)にする
- **鮮度契約**: kind別の閾値(`tech`=30日、他=180日。factと揃える)を超えたら`stale: true`
- **配置**: 既定で`MEDO_HOME`配下の別gitリポジトリ(medoツールリポジトリ本体には含めない)。git履歴がナレッジの成長・レビュー記録になる
- **フェーズ1のスコープ**: 保存・参照・stale判定・git履歴による目視レビューまで。「収集データを分析して統合・重複解消するフロー」はフェーズ2の`knowledge-digest`で扱う(バックログではなくフェーズ2の主要機能に格上げ)

### 案件固有ナレッジ — `knowledge/projects/{project_id}/{entry_id}.md`(単一案件スコープ)

技術ナレッジ(案件横断)とは別に、案件を掘り下げるほど蓄積される「その案件固有のノウハウ・気づき」を保持する層。medoは汎用支援ツールであり、個社の暗黙知を汎用ナレッジに混在させないための分離。

```yaml
project: "yoyaku"
statement: "顧客の予約システムは現在Excel管理。現場担当者はPC操作に不慣れ"
source: "hearing Skill 2026-07-27対話"   # URL出典は強制しない(対話由来のメモのため)
retrieved: "2026-07-27"
note: null
```

- 新規スキーマ `ProjectKnowledgeEntry`(`project` / `statement` / `source` / `retrieved` / `note`)。`kind`は持たない。既存`KnowledgeEntry`(出典URL必須)とはバリデーションを分ける
- **配置**: 既存の技術ナレッジと同じ`knowledge/`gitリポジトリ内に`projects/{project_id}/`サブディレクトリとして同居させる(リポジトリを分けない)。git履歴が案件ノウハウの成長記録になる
- **バックエンド選択**: `KnowledgeBackend` Protocol(`append` / `list` / `search`)を挟み、案件の`requirements`ドキュメントの`knowledge_backend: markdown | sqlite`(既定`markdown`)で1案件につき1つ選ぶ
  - `MarkdownBackend`(既定): frontmatter付きmd、1エントリ=1ファイル
  - `SqliteBackend`: `MEDO_HOME/projects/{id}/knowledge.sqlite`(バイナリのためgit管理外)、同一スキーマを1テーブルで保持
  - フェーズ2: `ExternalBackend`(Obsidian vault参照 / Notion API連携。認証情報は`.env`の`NOTION_API_KEY`等で分離)
- **蓄積フロー(フェーズ1: 追記のみ)**: 各Skill(hearing/propose-options/grow-prfaq)は終了時に、対話から得た案件固有ノウハウをホストLLMが抽出し `medo knowledge save --project <id> --statement "..." --source "<Skill名> <日付>対話"` で追記する。既存エントリとの重複統合・要約はしない(フェーズ2の`knowledge-digest`が案件横断・案件固有の両方を対象にする際に拡張)
- **CLI**: 既存`medo knowledge`に`--project <id>`を追加。指定時は案件固有ナレッジ(ProjectKnowledgeEntry・backend選択に従う)、未指定時は従来どおり案件横断の技術ナレッジ(kind必須)

### 生成物 — `projects/{id}/artifacts/{type}-v{n}`

type: `mini-prfaq` / `prfaq` / `fermi` / `comparison` / `architecture` / `slides` / `mock`。必ず以下を持つ:

- `requirements_version`(依存する要件バージョン → 陳腐化検出)
- `cited_facts[]`(市場ファクト根拠)+ `cited_knowledge[]`(技術ナレッジ根拠)→ 引用ファクト・ナレッジエントリのstale・欠落も陳腐化判定に含める
- `generated_by: claude | gemini | None` — 生成的な生成物(mini-prfaq / prfaq / slides 等)には必須。`fermi` はコードが決定論的に生成するため `None`

**`mini-prfaq` = 打ち手候補セット(1ドキュメント)**: 2〜3案の各ミニPRFAQを1つの生成物にまとめ、`options[]`(打ち手名・approach_typeのメタデータ)を持つ。バージョンは候補セットの改訂を表す(候補ごとに別Artifactにしない — statusの「typeごと最新のみ」表示・陳腐化検出・再生成が候補セット単位で一貫して機能するため)。

**`prfaq`(完全版)**: `grown_from: {artifact: "mini-prfaq-v<n>", option: "<打ち手名>"}` を必須で持ち、どの候補セットのどの打ち手から育成されたかを追跡できる。

ミニPRFAQ(各打ち手)の構成: 打ち手の宣言(顧客に届いた未来のプレスリリース1段落)/ 価値仮説(What/Why。principlesとの整合を明記)/ 効果の桁感(フェルミ推定参照)/ Howの目処(技術ナレッジ根拠の要点)/ 主要リスク・open_questions。完全版PRFAQはこれに技術的背景・workflow改善見込み・ロードマップ・FAQを加えて育成する。

---

## 5. Skill一覧(生成的な手順書)

| Skill | 内容 | フェーズ |
|---|---|---|
| `hearing` | 業界・ビジネス状況・課題・経営思想/方針の構造化。方針・理念はヒアリングとブレストで引き出して合意する。open_questionsを育て `medo requirements save` で保存 | 1 |
| `propose-options` | 市場・国策・業界動向ファクトの収集(ホストLLM検索→CLI保存)→フェルミ推定→打ち手候補(既存解決/業務改革/新市場 × スコープ/立ち位置/根本治療)をミニPRFAQ候補セット化。「Howの目処」は `medo knowledge search` の根拠に縛り、理念との整合を評価軸に含める | 1 |
| `grow-prfaq` | 合意した打ち手を完全版PRFAQへ育成。技術的背景・workflow改善見込みは `medo knowledge search` の根拠に縛る | 1 |
| `make-slides` | 提案スライド(Marp md)の対話的生成。Claude/Gemini比較可能 | 2 |
| `build-mock` | 合意形成用の動くMVPモック | 2 |
| `propose-architecture` | 詳細アーキ設計(完全版PRFAQの技術的背景を深掘り) | 2 |
| `decision-roadmap` | open_questionsを不確定パラメタとした修正コントロール | 2 |
| `compare-aws` | 同一要件でのAWS比較 | バックログ |

共通契約: CLIが失敗したら推測で補完せず失敗を報告する / stale項目(ファクト・技術ナレッジとも)は注記必須 / 出典のないファクトを提案に引用しない / フェルミ推定の計算をLLMで行わない / 開始時(プロジェクトID既知の場合のみ)・終了時に `medo status` を実行して現在地を報告する / 終了時、対話から得た案件固有ノウハウがあれば `medo knowledge save --project <id>` で追記する(フェーズ1: 追記のみ、統合・重複解消はしない)。

---

## 6. 技術ナレッジの鮮度維持(自動ETLではなくホストLLM検索+出典検証)

- **収集方法**: 自動ETL(BigQuery/Billing Catalog API等の常設パイプライン)は採用しない。案件で必要になった技術・サービス情報をホストLLMがその都度検索し、`medo knowledge save` で出典検証して保存する(市場ファクトと同じ扱い)
- **理由**: medoはクラウド非依存を志向するため、特定クラウドのAPIに常設依存するETLは持たない。実装手段としてGCPを検討する案件では、ホストLLMがGCP公式ドキュメント・リリースノート等を検索して保存すればよく、事前の全量カタログ化は不要
- **フェーズ2「knowledge-digest」**: 蓄積された`knowledge/`エントリを分析し、重複検知・要約統合・定期的な鮮度見直しレポートを提供する洗練フロー(product.md フェーズ計画を参照)
- **市場ファクトも同様に自動収集対象外**: 案件ごとに必要な範囲が変わるため事前カタログ化しない

---

## 7. フェーズ計画

各フェーズが単独で実用価値を持つ。

| フェーズ | 内容 | 完了の定義 |
|---|---|---|
| 1 | **What/Why縦切りMVP**: core(要件拡張・facts・fermi・knowledge)/ `medo` CLI / Skill 3本(`hearing`, `propose-options`, `grow-prfaq`)をClaude Codeとagyの両方に配布 | 実案件1件で 課題ヒアリング→市場ファクト+フェルミ推定→打ち手ミニPRFAQ比較→合意案の完全版PRFAQ(技術ナレッジ根拠付き) が両ホストで通る |
| 2 | **提案完成形+ナレッジ洗練**: `make-slides` / `build-mock` / `propose-architecture` / pricing計算機 / `decision-roadmap` / **knowledge-digest(蓄積ナレッジの分析・重複統合・鮮度見直し)** / 簡易Webアプリ | 課題→What/Why合意→スライド+モックまで半日で出せる。knowledgeが案件を跨いで洗練される |
| 3 | **運用自動化**: 蓄積の類似案件検索 / (必要になれば)特定クラウドAPIとの連携ETLをプラグインとして追加 | ナレッジが人手の負担少なく鮮度維持される |
| バックログ | `compare-aws` / MCPアダプタ / A2Aサーバー(Gemini Enterprise)/ チーム展開 | — |

---

## 8. エラー処理

- **ファクト/技術ナレッジ**: `source` 欠落はバリデーション拒否(market/policy/trend/techはURL形式も検証)。staleならCLIレスポンスにフラグ付与、Skillは注記義務
- **フェルミ計算**: 未定義変数・許可外の演算(四則演算・累乗以外)・参照先ファクトの不在または`value`欠落は非ゼロ終了+構造化エラー。推測で補完しない
- **CLI失敗**: 非ゼロ終了+構造化エラーメッセージ。Skill側の共通契約で「推測で補完せず失敗を報告」を強制
- **生成物の陳腐化**: 要件バージョンの差分と引用根拠(ファクト・技術ナレッジ)のstale・欠落による機械的検出(`requirements diff` / `status`)。自動再生成はしない(ユーザーが再生成を選ぶ)

## 9. テスト

1. **fermi計算機**: 手計算との突合ゴールデンテスト(ファクト参照・仮定混在・エラーパス)
2. **facts/knowledge**: バリデーション(出典欠落拒否・kind別のURL/由来表記ルール)・kind別stale判定(factsは180日、knowledgeのtechは30日)
3. **Skill**: 実案件1件をevalケース化し、同一要件→ミニPRFAQ群の安定性(引用ファクト・ナレッジIDの一致、打ち手構成の一貫性)を確認
4. **core**: 要件バージョニング・diff・鮮度判定・statusのユニットテスト
5. **pricing計算機**(フェーズ2): 公式Pricing Calculatorとの突合

## 10. ランニングコスト見積(自分専用時)

- 既定構成(ローカルJSON + ホストLLM検索): 追加コストなし
- Firestoreを本番ストレージに選ぶ場合: 無料枠内〜数百円/月
- フェーズ2 knowledge-digest(Gemini Flash等): 使用量次第、想定数百円/月
- ホスト側LLM(Claude Code/agy)・市場ファクト/技術ナレッジ検索: 既存契約内

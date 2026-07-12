# Medo(目処) 設計ドキュメント

ステータス: 承認済み(スコープ再定義: What/Why主軸+PRFAQ)

---

## 1. PRFAQ

### プレスリリース

**Medo(目処)— ビジネスの打ち手に「目処」をつける上流工程Agent。発想は自由に、事実は縛る**

業界・ビジネス状況・経営思想のヒアリングから始め、出典付きの市場・国策・業界動向データとフェルミ推定に裏づけられた打ち手候補(既存の解決/破壊的業務改革/新規市場開拓)をミニPRFAQとして並べ、What/Whyの合意を最速でつくる。合意した打ち手は、鮮度保証付きのGoogle Cloudナリッジに基づく技術的背景・workflow改善見込み・効果を備えた完全版PRFAQに育て、「絵に描いた餅」にならない目処として持ち帰れる。

課題も要件も最初から確定している必要はない。打ち手の比較やQ&Aで気づいた過不足は、どの段階からでも課題・方針・要件・ファクトに戻って更新し、下流の生成物を作り直せる。提案が引用する事実(市場数値・国策・業界動向・GCPサービスの新旧・GA/Preview状態・料金)は常に出典・取得日付きのデータに紐づくため、検討をやり直しても提案が揺れない。

Claude Codeやagy(Antigravity/Gemini)といった普段のAIツールからSkill+CLIとしてそのまま使える(フェーズ2で簡易Webアプリからの自然言語対話にも対応する)。ヒアリング・課題・方針・要件の成果は案件を跨いで蓄積され、業界ナリッジ・システムマップ資産としてチーム展開の土台になる。

### 顧客と課題

**顧客**: 利用者本人本人(自分および顧客のビジネス課題を整理し、打ち手とGCPアーキテクチャを検討・提案する立場)。将来は所属チーム。

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
目的は網羅的な市場調査レポートではなく「意思決定の目処」。案件に必要な範囲のファクトを出典付きで素早く集め、フェルミ推定で桁感を合わせ、ミニPRFAQで比較可能にする。技術的実現性(How)まで同じ場で、鮮度保証付きのGCPナリッジに基づいて目処を付けられる点がリサーチ専業と異なる。

**Q. なぜmulti-agentにしないのか?**
課題はエージェントの自律性不足ではなく、根拠データの鮮度と出力の再現性の不足だから。自律的なエージェント間対話は非決定性を増やし、課題と正面から矛盾する。「手順=Skill、事実と計算=CLI、かさばる検索=ホストLLM+出典検証」という分担で解く。

**Q. 既存のマルチクラウド設計比較Agent事例との違いは?**
それらは「その場でKnowledge MCPを検索して一発生成」であり、(1) 実行ごとに結果が揺れる、(2) Preview/GA・料金の決定論的な扱いがない、(3) 課題・要件が固定入力で育てられない、(4) 成果物が蓄積されない、(5) そもそもWhat/Whyを扱わない。MedoはWhat/Whyの合意形成を主戦場とし、鮮度カタログ・決定論計算・生きた要件ハブ・蓄積で支える。

**Q. コーディング支援系のOSS Agentツールとの違いは?**
コーディング支援ではなく、上流工程の提案と意思決定の高速化が目的。モック生成も「作るため」ではなく「合意形成のため」。

**Q. なぜMCPサーバーを最初に作らないのか?**
主要ホスト(Claude Code / agy / codex)はシェルが使えるため、Skill+CLIの方がコンテキスト効率が良い。MCPは同じコアの薄いアダプタとして、シェルなしホストが必要になった時点で追加する。

**Q. ハルシネーションをどう防ぐのか?**
「発想は自由、事実は縛る」。打ち手の発想・PRFAQの文章は創造的な生成物だが、引用する市場数値・国策・業界動向・サービス情報・launch_stage・料金は必ずCLIが検証・保存した出典付きファクトとカタログ値を使う。保存後の数値の通り道にLLMを挟まない(フェルミ推定もコードが計算する)。LLMが数値に触れるのは出典からの初回転記のみで、転記は出典に忠実・無加工とし、出典・取得日の必須保存で常に人間が検証できる(フェーズ2でCLIの出典照合検証を追加)。ツール失敗時は推測で補完せず失敗を報告する。

**Q. 成功の姿は?**
課題を話してから半日以内に、市場・国策・業界動向データとフェルミ推定に裏づけられた打ち手のミニPRFAQ比較でWhat/Whyに合意し、合意案の完全版PRFAQ(技術的背景・workflow改善見込み・効果・ロードマップ)まで持ち帰れる。

### 利用スコープ(初期)

- 利用者: 本人のみ(認証・マルチテナントなし)
- GCPカタログ範囲: AI/ML中心(Vertex AI・Gemini API等)を重点的に鮮度管理し、定番サービスは普通の粒度でカバー
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
              facts(市場・国策・業界動向・個社ファクト。出典必須・鮮度判定) /
              fermi(仮定×式の決定論計算。LLM不使用) /
              catalog(GCPナリッジ照会・鮮度判定) /
              artifacts(生成物の保存・紐づけ) /
              pricing・knowledge-digest(フェーズ2)
              │
[知識層]   Firestore(本番) or ローカルJSON(開発) + GCS(フェーズ2)
              ↑
[ETL]      GCPカタログのみ: リリースノートBQ公開データセット + Billing Catalog API
           → Gemini Flashで構造化 → 検証通過分のみコミット
           (市場ファクトはETLしない: 案件毎にホストLLMが検索し、CLIが出典検証して保存)
```

### 役割の三分担

| 役割 | 担当 | 決定論性 |
|---|---|---|
| 手順(ヒアリング・打ち手提案・PRFAQ育成の進め方) | Skill(ホストLLMが実行) | 生成的 |
| 事実と計算(ファクト保存検証・フェルミ計算・カタログ・料金・要件保存) | medo CLI + core | 決定論 |
| かさばる検索(市場・国策・業界動向) | ホストLLMの検索能力 +(フェーズ2)内蔵digest | 生成的だが出典必須 |

- LLM選定: ホスト側はClaude(Claude Code)/Gemini(agy)。内蔵(ETL構造化・digest)はGemini Flash。
- **数値の通り道にLLMを挟まない**: 保存済みファクト・カタログ値の参照、フェルミ計算、料金計算は常にコードが行う。LLMが数値に触れるのは**出典からの初回転記のみ**(市場ファクトの抽出、ETLの構造化)であり、転記は出典に忠実に行い加工しない(単位換算・集計が必要な場合はfermiで行う)。この転記精度がホストLLM依存であるトレードオフは認識した上で、出典・取得日の必須保存により人間が常に検証できる状態を保ち、フェーズ2でCLIによる出典照合検証(URLフェッチ+数値突合)を追加して縛りを強化する。

### データフロー: ハブ&スポーク

要件ドキュメント(課題・方針・要件)がハブ。各生成物はその時点の要件バージョンに紐づく。

1. `hearing` Skill: 業界・ビジネス状況・課題・経営思想/方針を対話とブレストで構造化 → `medo requirements save`(v1。この時点ではビジネス文脈とopen_questionsが中心で、システム要件は薄くてよい)
2. `propose-options` Skill: ホストLLMが市場・国策・業界動向を検索 → `medo facts save`(出典検証付き保存。数値は出典に忠実に転記)→ `medo fermi calc`(効果・市場規模の桁感をコードが計算)→ 打ち手候補2〜3案(既存の解決/破壊的業務改革/新規市場開拓 × スコープ/立ち位置/根本治療の切り口)を生成し、**各案の「Howの目処」は `medo catalog search` のGCPナリッジ根拠に縛って**記述(cited_catalog_entriesに記録)→ 各案のミニPRFAQを**1つの候補セットドキュメント**にまとめて保存 → `medo artifacts save --type mini-prfaq`(候補セット=1生成物。バージョンは候補セットの改訂を表す)
3. **比較・Q&A・合意**: ミニPRFAQ候補セットで意思決定。Q&Aで気づいた過不足は要件・ファクトに反映(v2)→ 陳腐化した生成物を検出 → 再生成。合意はツールの外で行われる人間の意思決定であり、次ステップのSkillが「どの打ち手に合意したか」を確認する
4. `grow-prfaq` Skill: 開始時に合意した打ち手をユーザーに確認し、完全版PRFAQに育成。技術的背景・workflow改善見込みは `medo catalog search` のGCPナリッジ根拠に縛る → `medo artifacts save --type prfaq`(`grown_from` に元のミニPRFAQ候補セットIDと選択した打ち手名を記録し、育成履歴を追跡可能にする)
5. フェーズ2: `make-slides`(スライド仕上げ)・`build-mock`・`propose-architecture`(アーキ詳細)・pricing
6. 成果はFirestoreに蓄積され、次案件で類似案件参照として効く(将来)

### 現在地の可視化(medo status)

`medo status --project <id>` が保存状態から**決定論的に**現在地レポートを返す(LLMを挟まない):

- 要件: 最新バージョン、confidence別件数、open_questions件数
- ファクト: 件数・staleの有無
- 生成物: **typeごとの最新バージョンのみ**をtype昇順で返す(陳腐化staleフラグ付き)
- **陳腐化判定**: 依存する `requirements_version` が最新要件より古い場合に加え、**引用根拠にstaleまたは欠落がある場合**(`cited_facts` のファクト=180日超過、`cited_catalog_entries` のカタログエントリ=30日超過)も陳腐化として扱う(「事実は縛る」を生成物のライフサイクルまで貫く)
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
│   ├── facts        # 市場・国策・業界動向・個社ファクト(出典必須・鮮度判定)
│   ├── fermi        # フェルミ推定の決定論計算(安全な式評価。LLM不使用)
│   ├── catalog      # GCPカタログ(型・クエリ・鮮度判定)
│   ├── artifacts    # 生成物(保存・要件バージョン紐づけ)
│   ├── status       # 現在地とnext_stepの決定論導出
│   └── pricing / knowledge  # (フェーズ2)
├── cli/             # medo CLI(requirements / facts / fermi / catalog / artifacts / status / etl)
├── skills/          # Skill本文(共通md)+ ビルドアダプタ
├── etl/             # GCPカタログ更新パイプライン
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
- **鮮度契約**: `retrieved` から180日超で `stale: true` を全CLIレスポンスに付与(市場データはGCPカタログ(30日)より劣化が遅い)。Skillはstaleファクト引用時に注記義務
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

### カタログエントリ — `catalog/{service}__{feature}`(既存のまま)

launch_stage・出典URL・`last_verified`必須、30日stale判定、料金はSKU参照のみ(金額焼き込みなし)。

### 生成物 — `projects/{id}/artifacts/{type}-v{n}`

type: `mini-prfaq` / `prfaq` / `fermi` / `comparison` / `architecture` / `slides` / `mock`。必ず以下を持つ:

- `requirements_version`(依存する要件バージョン → 陳腐化検出)
- `cited_facts[]`(市場ファクト根拠)+ `cited_catalog_entries[]`(GCPナリッジ根拠)→ 引用ファクト・カタログエントリのstale・欠落も陳腐化判定に含める
- `generated_by: claude | gemini | None` — 生成的な生成物(mini-prfaq / prfaq / slides 等)には必須。`fermi` はコードが決定論的に生成するため `None`

**`mini-prfaq` = 打ち手候補セット(1ドキュメント)**: 2〜3案の各ミニPRFAQを1つの生成物にまとめ、`options[]`(打ち手名・approach_typeのメタデータ)を持つ。バージョンは候補セットの改訂を表す(候補ごとに別Artifactにしない — statusの「typeごと最新のみ」表示・陳腐化検出・再生成が候補セット単位で一貫して機能するため)。

**`prfaq`(完全版)**: `grown_from: {artifact: "mini-prfaq-v<n>", option: "<打ち手名>"}` を必須で持ち、どの候補セットのどの打ち手から育成されたかを追跡できる。

ミニPRFAQ(各打ち手)の構成: 打ち手の宣言(顧客に届いた未来のプレスリリース1段落)/ 価値仮説(What/Why。principlesとの整合を明記)/ 効果の桁感(フェルミ推定参照)/ Howの目処(カタログ根拠の要点)/ 主要リスク・open_questions。完全版PRFAQはこれに技術的背景・workflow改善見込み・ロードマップ・FAQを加えて育成する。

---

## 5. Skill一覧(生成的な手順書)

| Skill | 内容 | フェーズ |
|---|---|---|
| `hearing` | 業界・ビジネス状況・課題・経営思想/方針の構造化。方針・理念はヒアリングとブレストで引き出して合意する。open_questionsを育て `medo requirements save` で保存 | 1 |
| `propose-options` | 市場・国策・業界動向ファクトの収集(ホストLLM検索→CLI保存)→フェルミ推定→打ち手候補(既存解決/業務改革/新市場 × スコープ/立ち位置/根本治療)をミニPRFAQ候補セット化。「Howの目処」は `medo catalog search` の根拠に縛り、理念との整合を評価軸に含める | 1 |
| `grow-prfaq` | 合意した打ち手を完全版PRFAQへ育成。技術的背景・workflow改善見込みは `medo catalog search` の根拠に縛る | 1 |
| `make-slides` | 提案スライド(Marp md)の対話的生成。Claude/Gemini比較可能 | 2 |
| `build-mock` | 合意形成用の動くMVPモック | 2 |
| `propose-architecture` | 詳細アーキ設計(完全版PRFAQの技術的背景を深掘り) | 2 |
| `decision-roadmap` | open_questionsを不確定パラメタとした修正コントロール | 2 |
| `compare-aws` | 同一要件でのAWS比較 | バックログ |

共通契約: CLIが失敗したら推測で補完せず失敗を報告する / stale項目(ファクト・カタログとも)は注記必須 / 出典のないファクトを提案に引用しない / フェルミ推定の計算をLLMで行わない / 開始時(プロジェクトID既知の場合のみ)・終了時に `medo status` を実行して現在地を報告する。

---

## 6. ETL(GCPカタログ鮮度維持)

- **ソース**: (1) リリースノート: BigQuery公開データセット `bigquery-public-data.google_cloud_release_notes`、(2) 料金: Cloud Billing Catalog API、(3) 公式ドキュメント、(4) 補助: Google Developer Knowledge MCP等(検索素材)
- **処理**: フェーズ1は手動実行 → フェーズ3でCloud Scheduler + Cloud Run Job。取得 → Gemini Flashで構造化 → スキーマバリデーション → 通過分のみコミット
- **市場ファクトはETL対象外**: 案件ごとに必要な範囲が変わるため事前カタログ化しない。ホストLLMの検索→CLIの出典検証付き保存で扱う

---

## 7. フェーズ計画

各フェーズが単独で実用価値を持つ。

| フェーズ | 内容 | 完了の定義 |
|---|---|---|
| 1 | **What/Why縦切りMVP**: core(要件拡張・facts・fermi・カタログ)/ 最小ETL(手動)/ `medo` CLI / Skill 3本(`hearing`, `propose-options`, `grow-prfaq`)をClaude Codeとagyの両方に配布 | 実案件1件で 課題ヒアリング→市場ファクト+フェルミ推定→打ち手ミニPRFAQ比較→合意案の完全版PRFAQ(GCPカタログ根拠付き) が両ホストで通る |
| 2 | **提案完成形**: `make-slides` / `build-mock` / `propose-architecture` / pricing計算機 / `decision-roadmap` / knowledge-digest / 簡易Webアプリ | 課題→What/Why合意→スライド+モックまで半日で出せる |
| 3 | **運用自動化**: ETLのScheduler自動化+Monitoringアラート / 蓄積の類似案件検索 | カタログが人手なしで鮮度維持される |
| バックログ | `compare-aws` / MCPアダプタ / A2Aサーバー(Gemini Enterprise)/ チーム展開 | — |

---

## 8. エラー処理

- **ファクト**: `source` 欠落はバリデーション拒否(market/policy/trendはURL形式も検証)。staleファクトはCLIレスポンスにフラグ付与、Skillは注記義務
- **フェルミ計算**: 未定義変数・許可外の演算(四則演算・累乗以外)・参照先ファクトの不在または`value`欠落は非ゼロ終了+構造化エラー。推測で補完しない
- **ETL失敗**: 前回カタログを維持し、壊れた更新で上書きしない
- **CLI失敗**: 非ゼロ終了+構造化エラーメッセージ。Skill側の共通契約で「推測で補完せず失敗を報告」を強制
- **生成物の陳腐化**: 要件バージョンの差分と引用根拠(ファクト・カタログエントリ)のstale・欠落による機械的検出(`requirements diff` / `status`)。自動再生成はしない(ユーザーが再生成を選ぶ)

## 9. テスト

1. **fermi計算機**: 手計算との突合ゴールデンテスト(ファクト参照・仮定混在・エラーパス)
2. **facts**: バリデーション(出典欠落拒否・kind別のURL/由来表記ルール)・180日stale判定
3. **カタログ**: スキーマバリデーション+出典URL生存チェック
4. **ETL**: サンプル固定によるスナップショットテスト
5. **Skill**: 実案件1件をevalケース化し、同一要件→ミニPRFAQ群の安定性(引用ファクト・カタログIDの一致、打ち手構成の一貫性)を確認
6. **core**: 要件バージョニング・diff・鮮度判定・statusのユニットテスト
7. **pricing計算機**(フェーズ2): 公式Pricing Calculatorとの突合

## 10. ランニングコスト見積(自分専用時)

- Firestore/GCS/Cloud Run: 無料枠内〜数百円/月
- Gemini Flash(ETL構造化・digest): 使用量次第、想定数百円/月
- ホスト側LLM(Claude Code/agy)・市場ファクト検索: 既存契約内

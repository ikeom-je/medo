# Medo(目処) 設計ドキュメント

日付: 2026-07-05
ステータス: レビュー待ち

---

## 1. PRFAQ

### プレスリリース

**Medo(目処)— アイデアから「目処が立つ」までを最速にする、Google Cloud上流工程Agent**

サービスやアプリのアイデア・ヒアリング内容を対話で構造化された要件に育てながら、鮮度保証付きのGoogle Cloudナリッジに基づいて、複数のアーキテクチャ案・コスト試算・動くMVPモック・提案スライドを高速に生成する。要件は最初から確定している必要はない。アーキ案やコストを見て過不足に気づいたら、どの段階からでも要件に戻って更新し、下流の生成物を作り直せる。提案が引用する事実(サービスの新旧・GA/Preview状態・料金)は常に出典・取得日付きのカタログデータに紐づくため、検討をやり直しても提案が揺れない。

Claude Codeやagy(Antigravity/Gemini)といった普段のAIツールからSkill+CLIとしてそのまま使え、簡易Webアプリからも自然言語で対話できる。ヒアリングと要件の成果は案件を跨いで蓄積され、業界ナリッジ・システムマップ資産としてチーム展開の土台になる。

### 顧客と課題

**顧客**: ikeoさん本人(自分および顧客のサービス/アプリのGCPアーキテクチャを検討・提案する立場)。将来は所属チーム。

**課題**:

1. アイデア段階の曖昧な入力から要件を引き出す作業が毎回手作業で、成果が案件ごとに使い捨てになる
2. AI/ML系サービスの更新が速すぎて、LLMの学習知識では「今なら解決できるようになったこと」を見落とす
3. 新機能のPreview/GA・安定性・事例有無という「判断に効くメタ情報」が単発プロンプトでは取れない
4. 提案がプロンプト次第・実行ごとに揺れて、比較検討や意思決定の土台にならない
5. 顧客に見せられる形(動くモック・スライド)にするまでが遠く、提案・意思決定が遅い

### FAQ(抜粋)

**Q. なぜmulti-agentにしないのか?**
課題はエージェントの自律性不足ではなく、根拠データの鮮度と出力の再現性の不足だから。自律的なエージェント間対話は非決定性を増やし、課題と正面から矛盾する。「手順=Skill、事実と計算=CLI、かさばる検索の圧縮=内蔵Gemini」という分担で解く。

**Q. 既存のマルチクラウド設計比較Agent事例(Skills+Subagentsで同一要件からAWS/GCP案を一括生成する構成)との違いは?**
それらの構成は「その場でKnowledge MCPを検索して一発生成」であり、(1) 実行ごとに結果が揺れる、(2) Preview/GA・料金の決定論的な扱いがない、(3) 要件が固定入力で育てられない、(4) 成果物が蓄積されない。Medoはこの4点(鮮度カタログ・決定論計算・生きた要件ハブ・蓄積)を核に設計する。なおそれらの事例が使うAWS Knowledge MCP / Google Developer Knowledge MCPは再発明せず、素材(検索ソース)として利用する。

**Q. コーディング支援系のOSS Agentツールとの違いは?**
コーディング支援ではなく、上流工程の提案と意思決定の高速化が目的。モック生成も「作るため」ではなく「合意形成のため」。

**Q. なぜMCPサーバーを最初に作らないのか?**
主要ホスト(Claude Code / agy / codex)はシェルが使えるため、Skill+CLIの方がコンテキスト効率が良い(ツールスキーマの常時ロードが不要、出力サイズを`--limit`等で制御可能)。MCPは同じコアの薄いアダプタとして、シェルなしホスト(ChatGPT、Gemini Enterprise等)が必要になった時点で追加する。

**Q. ハルシネーションをどう防ぐのか?**
「発想は自由、事実は縛る」。アーキ案・スライドの文章は創造的な生成物だが、引用するサービス情報・launch_stage・料金は必ずCLIツールが返すカタログ値・SKU計算値を使う。数値・ステータスの通り道にLLMを挟まない。ツール失敗時は推測で補完せず失敗を報告する。

**Q. 成功の姿は?**
アイデアを話してから半日以内に「動くモック+根拠付きアーキ比較スライド」を顧客に見せられる。

### 利用スコープ(初期)

- 利用者: 本人のみ(認証・マルチテナントなし)
- カタログ範囲: AI/ML中心(Vertex AI・Gemini API等)を重点的に鮮度管理し、アプリ構築定番サービス(Cloud Run/Functions/データ基盤等)は普通の粒度でカバー
- ホスト: Claude Code / agy + 簡易Webアプリ

---

## 2. 全体アーキテクチャ

```
[ホスト]   Claude Code / agy (Skill+CLI)        簡易Webアプリ (Gemini Flash/Pro)
              │                                      │
[Skill層]  hearing / propose-architecture / make-slides / build-mock /
           compare-aws / decision-roadmap  … 手順書(生成的)。CLI呼び出し手順を含む
              │ シェル実行                            │ 関数呼び出し
[CLI/コア] medo CLI ── core(ドメインロジック):
              catalog(照会・鮮度判定) / requirements(バージョン管理・差分) /
              pricing(SKU×利用量の決定論計算) / artifacts(生成物の保存・紐づけ) /
              knowledge-digest(内蔵Gemini Flashによる検索結果圧縮。出典必須)
              │
[知識層]   Firestore(カタログ・要件・生成物メタ) + GCS(スライド・モック実体)
              ↑
[ETL]      Cloud Scheduler → Cloud Run Job:
           リリースノートBQ公開データセット + Billing Catalog API + 公式ドキュメント
           → Gemini Flashで構造化(出典URL・launch_stage・last_verified付き)
```

### 役割の三分担

| 役割 | 担当 | 決定論性 |
|---|---|---|
| 手順(ヒアリング・提案の進め方) | Skill(ホストLLMが実行) | 生成的 |
| 事実と計算(カタログ・料金・要件保存) | medo CLI + core | 決定論 |
| かさばる検索の圧縮 | 内蔵Gemini Flash(knowledge-digest) | 生成的だが出典必須 |

- LLM選定: ホスト側はClaude(Claude Code)/Gemini(agy)。内蔵(圧縮・ETL構造化)はGemini Flashで低コスト化。Webアプリの頭脳はGemini Flash/Pro。
- 数値・ステータス(料金、launch_stage、last_verified)の通り道にLLMを挟まない。

### データフロー: ハブ&スポーク

要件ドキュメントがハブ。各生成物はその時点の要件バージョンに紐づく。

1. ホストで `hearing` Skill実行 → 対話でアイデアから要件抽出 → `medo requirements save` で構造化保存(v1)
2. `propose-architecture` Skillが要件v1 + `medo catalog search` の根拠で複数案生成(ねらい・理由・難易度付き)→ 引用カタログエントリIDを付けて `medo artifacts save`
3. `medo pricing estimate` が案ごとの決定論コスト算出、`make-slides` SkillがMarp mdを対話的に生成
4. アーキ案を見て要件の過不足に気づいたら要件を更新(v2)→ `medo requirements diff` が「どの生成物がv1依存で古いか」を返し、再生成を促す
5. ヒアリング・要件はFirestoreに蓄積され、次案件で類似案件参照として効く(将来)

### Claude vs Gemini のスライド比較

`make-slides` は同一Skill・同一要件・同一カタログ根拠で、Claude Code(Claude)とagy(Gemini)の双方から実行できる。生成物メタデータに `generated_by: claude|gemini` を記録し、両者の出力を並べて比較・選択できる。Skill本文は共通のmarkdownとして1箇所で管理し、Claude Skill形式とagy/Gemini形式へは薄いアダプタ(配置とフロントマターの変換)で配布する。

---

## 3. リポジトリ構成(モノレポ)

uv workspaceによるPythonモノレポ。コアを複数の薄いアダプタが共有し、SkillとCLIとスキーマを同一コミットで進化させる。

```
medo/
├── core/            # ホスト非依存ドメインロジック(Pythonパッケージ)
│   ├── catalog/     #   カタログの型・クエリ・鮮度判定
│   ├── requirements/#   要件ドキュメント(スキーマ・バージョン管理・差分検出)
│   ├── pricing/     #   決定論的コスト計算機(SKU×利用量)
│   ├── artifacts/   #   生成物の保存・要件バージョン紐づけ・Marpレンダリング
│   └── knowledge/   #   knowledge-digest(Gemini Flash圧縮、出典必須)
├── cli/             # medo CLI(catalog / requirements / pricing / artifacts / knowledge)
├── skills/          # Skill本文(共通md)+ Claude形式・agy形式へのビルドアダプタ
├── etl/             # Cloud Run Job: カタログ更新パイプライン
├── webapp/          # 簡易Webアプリ(対話クライアント兼、将来のMCP/A2A動作確認クライアント)
└── docs/
```

将来追加(バックログ): `mcp-server/`(coreの薄いMCPアダプタ。ツール5〜8個、ダイジェスト+ID+個別getのページング設計)、`a2a-server/`(Gemini Enterprise接続)。

---

## 4. データモデル

### 要件ドキュメント(ハブ) — Firestore `projects/{id}/requirements/v{n}`

```yaml
project: "顧客X 予約システム"
version: 3            # 更新のたびにインクリメント、旧版保持
industry: "飲食"       # 蓄積・類似案件検索のキー
goal: "..."            # やりたいことの一文
functional:            # 機能要件
  - text: "..."
    confidence: confirmed | assumed | open
non_functional: {performance: ..., availability: ..., security: ..., budget_cap: ...}
open_questions: [...]  # 未確定事項 = 次のヒアリング質問リスト = 意思決定の不確定パラメタ
sources: [...]         # ヒアリングメモ・参考URL
```

`confidence` と `open_questions` が「要件は最初から確定しない」の実装。生成物は `assumed` 要件に依存した箇所へ印を付け、`decision-roadmap`(最終推奨のロードマップ)は `open_questions` を不確定パラメタとして感度を示す。

### カタログエントリ — Firestore `catalog/{service}/features/{feature}`

```yaml
service: "vertex-ai"
feature: "context-caching"
launch_stage: GA | Preview | Deprecated
since: "2025-11-01"        # リリースノート由来
summary: "..."             # Gemini Flashによる構造化(出典必須)
pricing_refs: [sku-ids]    # Billing Catalog APIのSKU参照。金額は焼き込まない
caveats: ["リージョン制限", ...]
sources: [url, ...]
last_verified: "2026-07-01"
```

**鮮度契約**: `last_verified` が30日超なら全CLIレスポンスに `stale: true` が付き、Skillは提案文中への注記を必須とする。料金はSKU参照のみ保持し、金額はpricing計算機が都度Billing Catalog値から算出する(カタログへの金額焼き込み=陳腐化を防止)。

### 生成物 — Firestore `projects/{id}/artifacts/{type}-v{n}` + GCS(実体)

アーキ案md・スライドmd/PDF・モック・比較レポート。必ず以下を持つ:

- `requirements_version`(依存する要件バージョン → `medo requirements diff` で陳腐化検出)
- `cited_catalog_entries[]`(根拠。「なぜこの提案か」を後から追跡可能)
- `generated_by: claude | gemini`(スライド等の生成モデル比較用)

---

## 5. Skill一覧(生成的な手順書)

| Skill | 内容 | フェーズ |
|---|---|---|
| `hearing` | アイデア・ヒアリングメモ→要件抽出の対話手順。open_questionsを育て `medo requirements save` で保存 | 1 |
| `propose-architecture` | 複数アーキ案の生成(ねらい・理由・難易度)。根拠は `medo catalog search` に縛る | 1 |
| `make-slides` | 提案スライド(Marp md)の対話的生成。Claude/Gemini比較可能 | 2 |
| `build-mock` | Webフロントのみで動くMVPモックの高速生成(合意形成用) | 2 |
| `compare-aws` | 同一要件でAWS版アーキ案・コストを生成し比較レポート化 | 2 |
| `decision-roadmap` | 最終推奨のロードマップ化。open_questionsを不確定パラメタとして修正コントロール | 2 |

各Skillには「CLIが失敗したら推測で補完せず失敗を報告する」「stale項目は注記必須」の共通契約を記載する。

---

## 6. ETL(カタログ鮮度維持)

- **ソース**: (1) リリースノート: BigQuery公開データセット `bigquery-public-data.google_cloud_release_notes`、(2) 料金: Cloud Billing Catalog API、(3) 公式ドキュメント(launch_stage・caveats)、(4) 補助: Google Developer Knowledge MCP / AWS Knowledge MCP(検索素材として)
- **処理**: Cloud Scheduler(週次、フェーズ1は手動実行)→ Cloud Run Job → 取得 → Gemini Flashで構造化 → スキーマバリデーション → 通過分のみFirestoreへコミット → 差分レポート出力
- **範囲**: AI/ML系サービスを重点、定番サービスは普通の粒度。対象サービスリストは設定ファイルで管理

---

## 7. フェーズ計画

各フェーズが単独で実用価値を持つ。

| フェーズ | 内容 | 完了の定義 |
|---|---|---|
| 1 | **縦切りMVP**: core(スキーマ・カタログ・要件ストア)/ 最小ETL(AI/ML系リリースノート+主要SKU、手動実行)/ `medo` CLI / Skill 2本(`hearing`, `propose-architecture`)をClaude Codeとagyの両方に配布 | 実案件1件でヒアリング→要件保存→根拠付きアーキ案生成が両ホストで通る |
| 2 | **提案完成形**: pricing計算機 / `make-slides`(Claude/Gemini比較)/ `build-mock` / `compare-aws` / `decision-roadmap` / knowledge-digest / 簡易Webアプリ(チャット+要件表示+生成物プレビュー) | アイデア→モック+根拠付き比較スライドまで半日で出せる |
| 3 | **運用自動化**: ETLのScheduler自動化+Monitoringアラート / 蓄積の類似案件検索 | カタログが人手なしで鮮度維持される |
| バックログ | MCPアダプタ(シェルなしホスト向け)/ A2Aサーバー(Gemini Enterprise)/ チーム展開(認証・共有) | — |

---

## 8. エラー処理

- **ETL失敗**: 前回カタログを維持し、壊れた更新で上書きしない(バリデーション通過分のみコミット)。フェーズ3でMonitoringアラート
- **CLI失敗**: 非ゼロ終了+構造化エラーメッセージ。Skill側の共通契約で「推測で補完せず失敗を報告」を強制
- **鮮度切れ**: `stale: true` の伝播とSkillでの注記必須化(前述)
- **生成物の陳腐化**: `requirements diff` による機械的検出。自動再生成はしない(ユーザーが再生成を選ぶ)

## 9. テスト

1. **pricing計算機**: 公式Pricing Calculatorとの突合ゴールデンテスト(代表構成数パターン)
2. **カタログ**: スキーマバリデーション+出典URL生存チェック
3. **ETL**: リリースノートのサンプル固定によるスナップショットテスト(Gemini構造化の出力スキーマ検証含む)
4. **Skill**: 実案件1件をevalケース化し、同一要件→提案の安定性(引用の一致・構成の一貫性)を確認
5. **core**: 要件バージョニング・diff・鮮度判定のユニットテスト

## 10. ランニングコスト見積(自分専用時)

- Firestore/GCS/Cloud Run(Job+Webアプリ): 無料枠内〜数百円/月
- Gemini Flash(ETL構造化・digest・Webアプリ対話): 使用量次第、想定数百円/月
- ホスト側LLM(Claude Code/agy): 既存契約内

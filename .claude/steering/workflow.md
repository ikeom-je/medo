# ワークフロールール

Medo の開発ワークフロー。スペック駆動(superpowersフロー)+TDDで進める。

---

## 1. ドキュメントの二層整理

| 層 | 場所 | 内容 |
|---|---|---|
| **人間用** | `docs/` | 設計ドキュメント(PRFAQ含む)・実装計画・セットアップ手順。正本(canonical) |
| **Agent用** | `.claude/` | steering(常時参照する要約・規約)と specs(フェーズ単位のAgent向け要約+正本へのポインタ) |

- 正本は常に `docs/` 側。`.claude/` 側は要約とポインタに留め、二重管理のドリフトを防ぐ
- 設計が変わったら: `docs/superpowers/specs/` を更新 → `.claude/steering/` と `.claude/specs/` の要約を同期
- **例外**: 開発Agentの担当表(Section 3)は開発運用の設定であり、本ファイル(workflow.md)を正本とする(docs/側に対応する正本を持たない唯一の項目)

## 2. 着手前チェック(全エージェント共通)

1. `.claude/steering/product.md`(設計原則・差別化軸)を確認
2. タスクに応じて `tech.md` / `structure.md` / `testing.md` / `git.md` を確認
3. 実行中のフェーズの spec と実装計画を確認: `.claude/specs/<phase>/` → 正本 `docs/superpowers/{specs,plans}/`
4. 実装計画のチェックボックス(`- [ ]`)で現在地を把握する

## 3. 実行主体の使い分け(Claude / Codex / agy)

Medo の開発では実行主体を作業領域ごとに分担する。**Claudeが統制者(オーケストレーター)** であり、他は実行担当。

### 担当表(single source of truth)

**本表が担当分担の唯一の定義箇所**。他のドキュメント(CLAUDE.md・git.md・正本設計等)は本表を参照する。モデルの強さ・得意領域の変化に応じて、**担当は本表の更新だけで変更できる**(steering変更として相互レビュー→`docs(steering):`コミットを経る)。

**担当変更の合議プロセス**: モデルの世代交代・コストパフォーマンスの変化時(またはユーザーの求めに応じて)、3モデルの合議で変更案を作る — (1) Codexとagyそれぞれに全作業領域について「どのモデルが最適か」の自己評価・相互評価(得意領域・コスパ。自分に有利に倒さない)を取る (2) Claudeが自身の評価と突き合わせて一致点・相違点を集約し、相違は理由付きで裁定 (3) 提案としてユーザーに提示し、**人間の承認を得てから**本表を更新する。

| 作業領域 | 担当 | 例・備考 |
|---|---|---|
| 計画・設計・判断 | **Claude** | スペック・実装計画の作成、設計承認、要件との整合性判断、Skill/CLIの契約変更判断、相互レビュー(Codex/agy作diff)とレビュー裁定、テスト/リントの最終検証、コミット・ブランチ・マージ操作 |
| 実装・テストコード作成 | **Codex** | 実装計画のTaskに沿ったコード実装、テストコードの作成、コードの大量生成(スキャフォールド・網羅的テスト生成・マイグレーション)、相互レビュー(Claude作の生成物) |
| デバッグ・障害解析 | **起因で分担** | 初期切り分け=Claude → コード・テスト失敗起因=Codex / 実環境・外部起因(GCPログ・既知Issue検索)=agy / **最終的な原因認定=Claude** |
| 調査・情報抽出 | **agy(antigravity)** | Web検索(市場・国策・業界動向・技術情報)、依存ライブラリ・CVE(脆弱性)調査、エラーログの一次トリアージ(GCPガード適用)、マルチモーダル資料(PDF・スライド・画像)からの情報抽出、長いドキュメント/コード全体の読み込みが要る調査・ダイジェスト作成、テキスト・資料の大量処理(一括要約等)、相互レビュー(Claude作の生成物) |
| ドキュメント執筆 | **種別で分担** | 設計正本・steering=Claude / 実装近傍のドラフト(README・CLI使用例等)=Codex / 調査レポート・ユーザー向け資料のドラフト=agy。**最終文面の裁定は常にClaude**。相互レビュー上の「作成者」は、Claudeが実質的に文面を編集した場合はClaude作(→Codex+agyレビュー)、ドラフトの採否のみの場合はドラフト作成モデル作(→Claudeレビュー)として扱う |
| スライド・図表などの資料生成 | **agy(antigravity)** | Gemini系が得意な傾向のある資料生成(Google Slides・図表等)。Skillの「Geminiホスト」としての実行・eval(`generated_by`比較)を含む |

**変更できない不変条件**(担当表の編集では変えられない):
1. 最終判断・検証・マージ・コミットの統制は常にClaude(オーケストレーター)— このため担当表の「計画・設計・判断」行はClaude以外に変更できない
2. 相互レビューの「作ったモデル≠レビューするモデル」原則。レビューの組み合わせを変えたい場合は担当表ではなく正本 `docs/superpowers/specs/cross-review-design.md` の改訂(設計サイクル)として扱う
3. プロダクト設計原則(`.claude/steering/product.md`。数値・事実の通り道にLLMを挟まない等)

なお、本Section下部の運用注記(Codexサンドボックスのネットワーク遮断・agyのモデル方針・GCPガード等)は**現在の担当構成に固有の制約**であり、担当表を変更した場合は合わせて見直す。

- **レビューは従来通り3者が担う**(組み合わせは相互レビュープロトコルのマトリクスに従う: Claude作→Codex+agy両方、Codex/agy作→Claude)
- 判断の最終権限と結果検証は常にClaudeが持つ。Codex/agyの出力を無検証で正としない。**Codexサンドボックスはネットワーク遮断のため、依存解決とテスト実行の最終確認(`uv run pytest` / `uv run ruff check .`)は必ずClaudeが自環境で行う**
- **agyのモデル方針**: 基本は Gemini 3.5 Flash。深い設計レビュー・複雑な調査ではClaudeの判断で Gemini Pro に引き上げてよい(引き上げた場合はコミット本文の `review:` 行に使用モデルを明記し、PRへは既存ルール通り転記)。Gemini quotaが切れた場合はagy経由の Claude Sonnet 系(現状4.6。Sonnet 5がagyで利用可能になり次第そちら)に切り替えて**調査を継続する**。ただし別モデル原則により: **Claude系代替モデルはClaude作生成物のレビュアーとして数えず**(Codex単独レビュー+記録)、**Claude系代替モデルで作成したagy生成物の相互レビューはCodexが担う**。**Geminiホストとしての Skill 実行・eval・`generated_by: gemini` 比較はGeminiモデル稼働時のみ**とし、quota切れ中はClaude単独実行で開発を進行してよい(Gemini側のeval・比較はフェーズ完了までに復旧後追実施)。agy自体が利用不可の場合、調査はClaudeが自身の検索ツールで代替し、**レビューは実施可能なレビュアー(Codex単独)で行う**。いずれもコミット本文・PR本文にその旨を記録する
- **GCP環境調査のガード**: agyのCloud Logging等の調査は読み取り専用・対象プロジェクト明示で行う。ログに含まれ得る機密・PIIは伏字・プレースホルダーにマスクした上で技術情報(エラーメッセージ・スタックトレース)のみを転記するか、ログURI参照のみを成果物・Issue・PRに記録する
- 振り分けの基準に迷ったら: 作業を「意思決定・検証・裁定 / 手順が決まっているコード作成 / デバッグ / 外部情報の収集・大量読み込み / ドキュメント執筆 / 資料生成」のどの作業領域かで捉え、担当表の該当行に従う。どの行にも該当しなければ担当表に新しい行を足す判断をユーザーに確認する
- 詳細な委譲手順は `antigravity` プラグインの steering/skill を参照(本ファイルは役割分担の方針のみを定める)

### 相互レビュープロトコル(要約)

中間生成物(スペック・実装計画・実装diff)は最小単位で相互レビューする。
**正本: `docs/superpowers/specs/cross-review-design.md`**(詳細な手段・裁定ルールはそちらを参照)。

- 原則: **作ったモデル ≠ レビューするモデル**。Claude作の生成物(スペック・計画・diff)は Codex + agy の両方が、agy/Codex作のdiffは Claude がレビューする。Claudeが最終裁定者で、指摘も無検証で採用しない
- **上限2ラウンド**(指摘往復のみに適用)。早期終了は重大指摘ゼロ+コードは pytest/ruff パス。テスト・リントパスは裁定でも免除されない絶対条件
- **記録**: コミット本文に `review: <レビュアー(+区切り)> <n>R / 重大<n>件解消 / 未解決<n>` を1行残す。PRを経由する変更(git.mdセクション1)は同じ記録をPR本文にも転記する

## 4. 機能開発ワークフロー(スペック駆動)

```
アイデア/要望
  → superpowers:brainstorming(設計の対話・承認)
  → 設計ドキュメント作成: docs/superpowers/specs/<topic>-design.md
  → superpowers:writing-plans(実装計画: docs/superpowers/plans/<topic>.md)
  → 実行: superpowers:subagent-driven-development または executing-plans
  → 検証(testing.md)→ コミット(git.md)
```

- ファイル名に日付プレフィックスは付けない(git履歴が作成日・変更履歴を持つため冗長)。本文内にも日付ヘッダーは書かない

- 設計承認前に実装を始めない
- 実装計画のTask単位で「失敗テスト→実装→パス→コミット」を回す(計画にステップとコードが明記されている)
- 計画から外れる判断が必要になったら、勝手に進めず計画・specを更新してから実装する
- 実装計画のTask単位はGitHub Issueに対応させ、Issue→worktree→PR→dev/mainマージで進める(詳細: git.mdセクション1、正本: `docs/superpowers/specs/issue-driven-workflow-design.md`)

## 5. 設計判断で迷ったら

1. `product.md` の設計原則(発想は自由・事実は縛る/三分担/要件は確定しない/鮮度契約/推測で補完しない)に照らす
2. 差別化軸の「やらない」リストに該当しないか確認する
3. それでも決まらないものはユーザーに確認する(特に: スコープ拡大、外部公開、課金が発生する変更)

## 6. 変更時の同期トリガー

| 変更 | 同時に更新するもの |
|---|---|
| CLIのコマンド体系・出力形式 | `skills/src/*.md`(SkillはCLIとの契約で動く)+ Skill evalケース再実行 |
| ドメインスキーマ(要件・カタログ・生成物) | `structure.md` のストレージパス表、関連するSkill本文 |
| services.yaml(対象サービス) | ETLの手動実行でカタログ再構築 |
| 設計そのもの | `docs/superpowers/specs/` → steering/specs要約の同期(Section 1) |
| フェーズ完了 | `product.md` のフェーズ計画表、`.claude/specs/` に次フェーズを追加 |

## 7. 日常運用(フェーズ1)

```bash
# カタログ更新(手動・週次目安)
MEDO_BACKEND=local uv run medo etl run --since <前回実行日> --services vertex-ai,cloud-run

# Skill更新後の再配布
python skills/build.py && cp -r skills/dist/claude/* ~/.claude/skills/
```

フェーズ3でETLはCloud Scheduler+Cloud Run Jobに自動化し、Monitoringアラートを追加する(それまで監視ワークフローは持たない)。

## 8. 実案件での利用フロー(ドッグフーディング)

1. ホスト(Claude Code / agy)で `medo-hearing` → 業界・ビジネス状況・課題・経営思想/方針を構造化して要件保存(v1)
2. `medo-propose-options` → 市場・国策・業界動向ファクト収集+フェルミ推定+カタログ根拠 → 打ち手候補のミニPRFAQ候補セットを生成・保存
3. 候補セットで比較・Q&A・合意 → `medo-grow-prfaq` → 合意案を完全版PRFAQ(How+効果+ロードマップ)に育成
4. 過不足に気づいたら要件・ファクトを更新(v2) → `medo requirements diff` / `medo status` で陳腐化した生成物を確認 → 再生成
5. 使いにくさ・不足を感じたら、その場で直さずIssueメモとして `docs/feedback.md` に追記し、次の設計サイクルで扱う

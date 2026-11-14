# フェーズ1 タスク一覧(Agent用)

> 正本: `docs/superpowers/plans/medo-phase1.md`(各Taskの手順・コード・コマンドはすべて計画に記載)。
> 進捗は計画側のチェックボックス(`- [ ]`)を正とする。本ファイルは全体像の把握用。

| # | Task | 依存 | 状態 |
|---|---|---|---|
| 1 | uv workspace モノレポ土台(core/cli) | — | 完了 |
| 2 | Storage(Protocol + LocalJSON + Firestore) | 1 | 完了 |
| 3 | 要件ドキュメント(RequirementsDoc + Store) | 2 | 完了 |
| 4 | カタログ(CatalogEntry + Store) → 技術ナレッジ(KnowledgeEntry/Store)に置き換え済み(Issue #26-#29) | 2 | 完了 |
| 5 | 生成物(Artifact + Store) | 2 | 完了 |
| 6 | medo CLI(requirements/knowledge/artifacts) | 3,4,5 | 完了 |
| 6b | 要件スキーマ拡張(背景・理念・課題)※契約変更 | 6 | 完了 |
| 6c | 市場ファクト(Fact + Store + CLI)※契約変更 | 6 | 完了 |
| 6d | 生成物スキーマ拡張(mini-prfaq/prfaq/fermi)※契約変更 | 6 | 完了 |
| 6e | フェルミ推定(決定論計算 + CLI)※契約変更 | 6c,6d | 完了 |
| 6f | medo status + docs/usage.md | 6b,6c,6d,6e | 完了 |
| 7 | ETL: リリースノート取得+Gemini構造化 | 4 | 不採用(クラウド非依存方針と矛盾。Issue #18/PR #19) |
| 8 | ETL: SKUスナップショット+パイプライン+CLI統合 | 6,7 | 不採用(同上。Issue #31) |
| 9 | Skill 3本(hearing/propose-options/grow-prfaq)+ビルド | 6b〜6f | 完了 |
| 10 | 統合スモーク(実環境・ユーザー共同、docs/setup.md作成) | 9 | 完了 |

- 各TaskはTDD(失敗テスト→実装→パス→コミット)。コミットメッセージは計画に明記
- ※契約変更Taskは人間レビューを経てマージ(git.md重要度判定)
- Task完了時に本表の状態を更新する(未着手/進行中/完了/不採用)
- Task 10 は実案件の意思決定が絡むためユーザーと共同で実施(既定のローカルJSONバックエンドではクラウド認証は不要。Firestoreを選ぶ場合のみ関係する)

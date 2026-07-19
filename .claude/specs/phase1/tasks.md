# フェーズ1 タスク一覧(Agent用)

> 正本: `docs/superpowers/plans/medo-phase1.md`(各Taskの手順・コード・コマンドはすべて計画に記載)。
> 進捗は計画側のチェックボックス(`- [ ]`)を正とする。本ファイルは全体像の把握用。

| # | Task | 依存 | 状態 |
|---|---|---|---|
| 1 | uv workspace モノレポ土台(core/cli/etl) | — | 完了 |
| 2 | Storage(Protocol + LocalJSON + Firestore) | 1 | 完了 |
| 3 | 要件ドキュメント(RequirementsDoc + Store) | 2 | 完了 |
| 4 | カタログ(CatalogEntry + Store) | 2 | 完了 |
| 5 | 生成物(Artifact + Store) | 2 | 完了 |
| 6 | medo CLI(requirements/catalog/artifacts) | 3,4,5 | 完了 |
| 6b | 要件スキーマ拡張(背景・理念・課題)※契約変更 | 6 | 完了 |
| 6c | 市場ファクト(Fact + Store + CLI)※契約変更 | 6 | 完了 |
| 6d | 生成物スキーマ拡張(mini-prfaq/prfaq/fermi)※契約変更 | 6 | 未着手 |
| 6e | フェルミ推定(決定論計算 + CLI)※契約変更 | 6c,6d | 未着手 |
| 6f | medo status + docs/usage.md | 6b,6c,6d,6e | 未着手 |
| 7 | ETL: リリースノート取得+Gemini構造化 | 4 | 未着手 |
| 8 | ETL: SKUスナップショット+パイプライン+CLI統合 | 6,7 | 未着手 |
| 9 | Skill 3本(hearing/propose-options/grow-prfaq)+ビルド | 6b〜6f | 未着手 |
| 10 | 統合スモーク(実環境・ユーザー共同、docs/setup.md作成) | 8,9 | 未着手 |

- 各TaskはTDD(失敗テスト→実装→パス→コミット)。コミットメッセージは計画に明記
- ※契約変更Taskは人間レビューを経てマージ(git.md重要度判定)
- Task完了時に本表の状態を更新する(未着手/進行中/完了)
- Task 10 はGCP認証・課金・実案件の意思決定が絡むためユーザーと共同で実施

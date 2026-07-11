# フェーズ1 タスク一覧(Agent用)

> 正本: `docs/superpowers/plans/medo-phase1.md`(各Taskの手順・コード・コマンドはすべて計画に記載)。
> 進捗は計画側のチェックボックス(`- [ ]`)を正とする。本ファイルは全体像の把握用。

| # | Task | 依存 | 状態 |
|---|---|---|---|
| 1 | uv workspace モノレポ土台(core/cli/etl) | — | 完了 |
| 2 | Storage(Protocol + LocalJSON + Firestore) | 1 | 完了 |
| 3 | 要件ドキュメント(RequirementsDoc + Store) | 2 | 未着手 |
| 4 | カタログ(CatalogEntry + Store) | 2 | 未着手 |
| 5 | 生成物(Artifact + Store) | 2 | 未着手 |
| 6 | medo CLI(requirements/catalog/artifacts) | 3,4,5 | 未着手 |
| 6b | medo status(現在地の可視化)+ docs/usage.md | 3,5,6 | 未着手 |
| 7 | ETL: リリースノート取得+Gemini構造化 | 4 | 未着手 |
| 8 | ETL: SKUスナップショット+パイプライン+CLI統合 | 6,7 | 未着手 |
| 9 | Skill 2本+ビルドスクリプト | 6,6b | 未着手 |
| 10 | 統合スモーク(実環境・ユーザー共同、docs/setup.md作成) | 8,9 | 未着手 |

- 各TaskはTDD(失敗テスト→実装→パス→コミット)。コミットメッセージは計画に明記
- Task完了時に本表の状態を更新する(未着手/進行中/完了)
- Task 10 はGCP認証・課金が絡むためユーザーと共同で実施

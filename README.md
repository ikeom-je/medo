# Medo(目処)

> アイデアから「目処が立つ」までを最速にする、Google Cloud上流工程Agent。
> 発想は自由に、事実は縛る。

サービスやアプリのアイデア・ヒアリング内容を対話で要件に育てながら、鮮度保証付きのGoogle Cloudナリッジに基づいて、複数のアーキテクチャ案・コスト試算・MVPモック・提案スライドを高速に生成する **Agentケイパビリティ(Agent + Skill + CLI)** です。

## 何を解決するか

- LLMの学習知識では追いつけない **AI/ML系サービスの更新速度**(「今なら解決できること」の見落とし)
- Preview/GA・安定性という **判断に効くメタ情報** が単発プロンプトで取れない
- 提案が実行ごとに揺れて **比較検討・意思決定の土台にならない**
- 要件整理の成果が案件ごとに **使い捨て** になる

## アプローチ: 役割の三分担

| 役割 | 担当 | 決定論性 |
|---|---|---|
| 手順(ヒアリング・提案の進め方) | Skill(ホストLLMが実行) | 生成的 |
| 事実と計算(カタログ・料金・要件保存) | `medo` CLI + core | 決定論 |
| かさばる検索の圧縮 | 内蔵Gemini Flash | 生成的だが出典必須 |

要件ドキュメントはバージョン付きの「生きた成果物」で、生成物(アーキ案・スライド等)はその時点の要件バージョンと引用カタログエントリに必ず紐づきます。要件が育ったら、陳腐化した生成物を機械的に検出して作り直せます。

## ステータス

**設計完了・フェーズ1(縦切りMVP)実装前。** コードはまだありません。

| フェーズ | 内容 |
|---|---|
| 1(次) | core + 最小ETL + `medo` CLI + Skill 2本(hearing / propose-architecture)を Claude Code / agy 両対応で |
| 2 | pricing計算機・スライド生成(Claude/Gemini比較)・MVPモック・AWS比較・簡易Webアプリ |
| 3 | ETL自動化(Cloud Scheduler)・類似案件検索 |
| バックログ | MCPアダプタ・A2A(Gemini Enterprise)・チーム展開 |

## ドキュメント

| 対象 | 場所 |
|---|---|
| 設計ドキュメント(PRFAQ含む) | [docs/superpowers/specs/medo-design.md](docs/superpowers/specs/medo-design.md) |
| フェーズ1実装計画 | [docs/superpowers/plans/2026-07-05-medo-phase1.md](docs/superpowers/plans/2026-07-05-medo-phase1.md) |
| Agent向けエントリポイント | [CLAUDE.md](CLAUDE.md)(Claude Code) / [AGENTS.md](AGENTS.md)(agy等) |
| Agent向け規約(steering) | `.claude/steering/` |

## 開発(フェーズ1実装後)

```bash
uv sync --all-packages       # 依存解決
uv run pytest                # テスト
uv run medo --help           # CLI
python skills/build.py       # Skill配布物のビルド
```

技術スタック: Python 3.12+ / uv workspace / pydantic / typer / Firestore / BigQuery公開データセット / Cloud Billing Catalog API / Gemini Flash(構造化専任)

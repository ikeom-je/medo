# Medo(目処)

> ビジネスの打ち手に「目処」をつける上流工程Agent。
> 発想は自由に、事実は縛る。

業界・ビジネス状況・経営思想のヒアリングから始め、出典付きの市場・国策・業界動向データとフェルミ推定に裏づけられた打ち手候補(既存の解決/破壊的業務改革/新規市場開拓)をミニPRFAQとして比較提示し、What/Whyの合意を最速でつくる **クラウド非依存の上流工程Agentケイパビリティ(Agent + Skill + CLI)** です。合意した打ち手は、鮮度保証付き技術ナリッジに基づく技術的背景・効果を備えた完全版PRFAQに育てます。

## 何を解決するか

- What/Whyの合意がないまま **How(システム要件・アーキ検討)に突入** して起きる後戻り
- 市場・国策・業界動向を踏まえた打ち手比較が毎回手作業で、**提案の説得力が経験と勘に依存** する
- LLMの学習知識では追いつけない **AI/ML系サービスの更新速度**(「今なら解決できること」の見落とし)
- 提案が実行ごとに揺れて **比較検討・意思決定の土台にならない**
- 課題・要件整理の成果が案件ごとに **使い捨て** になる

## アプローチ: 役割の三分担

| 役割 | 担当 | 決定論性 |
|---|---|---|
| 手順(ヒアリング・打ち手提案・PRFAQ育成の進め方) | Skill(ホストLLMが実行) | 生成的 |
| 事実と計算(ファクト検証・フェルミ計算・技術ナレッジ・要件保存) | `medo` CLI + core | 決定論 |
| かさばる検索(市場・国策・業界動向・技術/サービス情報) | ホストLLMの検索+出典必須の保存 | 生成的だが出典必須 |

要件ドキュメント(背景・理念・課題・要件)はバージョン付きの「生きた成果物」で、生成物(ミニPRFAQ候補セット・完全版PRFAQ等)はその時点の要件バージョン・引用ファクト・引用ナレッジエントリに必ず紐づきます。要件や事実の鮮度が変わったら、陳腐化した生成物を機械的に検出して作り直せます。フェルミ推定の計算はLLMではなくコードが行います。

## 使い所: `medo` CLIは独立Agentではない

`medo` はSkill(手順書)の一部として、**ホストLLM(Claude Code / Codex / agy)がシェルから呼び出す決定論ツール**です。`gh` や `git` のように単体では会話も判断もしません。実行主体は常にホスト側のAgentで、`medo` はその手順の中で事実の保存・検証・計算だけを担います。

```
[ホスト] Claude Code(Claude) / Codex / agy(Gemini)   ← 会話・判断をするのはここだけ
    │ シェル実行
[Skill]  hearing / propose-options / grow-prfaq  ← 手順書(生成的)
    │ 手順の中で呼ぶ
[CLI]    medo requirements / facts / fermi / knowledge / artifacts / status
```

自律的なmulti-agent構成は意図的に採らない設計方針(差別化軸を参照)。会話Agentは1体(ホストLLM)のみで、CLIは決定論的な道具箱として振る舞います。

## ステータス

**フェーズ1(What/Why縦切りMVP)ほぼ完了。** core(要件・ファクト・フェルミ・技術ナレッジ・生成物・status)・CLI・Skill 3本を実装済み。残りは実案件での統合スモークのみ。

| フェーズ | 内容 |
|---|---|
| 1 | core(要件・ファクト・フェルミ・技術ナレッジ)+ `medo` CLI + Skill 3本(hearing / propose-options / grow-prfaq)を Claude Code / Codex / agy 対応で |
| 2 | スライド生成(Claude/Gemini比較)・MVPモック・アーキ詳細・pricing計算機・knowledge-digest・簡易Webアプリ |
| 3 | 運用自動化: 類似案件検索 /(必要になれば)特定クラウドAPI連携ETLをプラグインとして追加 |
| バックログ | AWS比較・MCPアダプタ・A2A(Gemini Enterprise)・チーム展開 |

## ドキュメント

| 対象 | 場所 |
|---|---|
| 設計ドキュメント(PRFAQ含む) | [docs/superpowers/specs/medo-design.md](docs/superpowers/specs/medo-design.md) |
| フェーズ1実装計画 | [docs/superpowers/plans/medo-phase1.md](docs/superpowers/plans/medo-phase1.md) |
| Agent向けエントリポイント | [CLAUDE.md](CLAUDE.md)(Claude Code) / [AGENTS.md](AGENTS.md)(agy等) |
| Agent向け規約(steering) | `.claude/steering/` |

## 開発

```bash
uv sync --all-packages       # 依存解決
uv run pytest                # テスト
uv run medo --help           # CLI
python skills/build.py       # Skill配布物のビルド(Claude Code/Codex/agy共通形式)
```

技術スタック: Python 3.12+ / uv workspace / pydantic / typer / Firestore(本番ストレージに選ぶ場合のみ、任意)

## ライセンス

[MIT License](LICENSE)

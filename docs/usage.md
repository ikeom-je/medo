# Medo 使い方ガイド(フェーズ1)

Medoは「ビジネスの打ち手に目処をつける」上流工程を支援する。作業は次のステージを進む:

    課題 ──(medo-hearing)──▶ 要件v1(背景・理念・課題)
      ──(medo-propose-options)──▶ 市場ファクト+フェルミ推定+技術ナレッジ根拠
                                   → 打ち手候補のミニPRFAQ候補セット
      ──(比較・Q&A・合意)──▶ (medo-grow-prfaq)──▶ 完全版PRFAQ(How+効果+ロードマップ)
                  ▲                                    │
                  └── 過不足に気づいたら要件・ファクトを更新 ◀──┘
                      → medo status / requirements diff が陳腐化を検出 → 再生成

## 今どこにいるかを知る

    medo status --project <id>

が現在地を返す。`next_step` の意味:

| next_step | 状態 | 次にやること |
|---|---|---|
| `hearing` | 要件が未作成 | ホストで medo-hearing Skill を実行 |
| `propose-options` | 要件はあるが打ち手候補がない | medo-propose-options Skill を実行 |
| `grow-prfaq` | 候補セットはあるが完全版PRFAQがない | 合意した打ち手を medo-grow-prfaq で育成 |
| `regenerate-stale-artifacts` | 要件更新・引用ファクト/ナレッジの鮮度切れで生成物が陳腐化 | `medo requirements diff` で確認→再生成 |
| `up-to-date` | 最新要件・鮮度に生成物が追従 | フェーズ1のゴール到達(フェーズ2でスライド等に続く) |

## ステージとコマンドの対応

| ステージ | Skill | 主なCLI |
|---|---|---|
| 課題・方針の構造化 | medo-hearing | `medo requirements save/get` |
| 打ち手候補の提案 | medo-propose-options | `medo facts save/list`、`medo fermi calc`、`medo knowledge search`、`medo artifacts save --type mini-prfaq` |
| PRFAQ育成 | medo-grow-prfaq | `medo artifacts get`、`medo knowledge search`、`medo artifacts save --type prfaq` |
| 見直し | (どこからでも) | `medo requirements diff`、`medo status`、`medo fermi calc --from-artifact` |

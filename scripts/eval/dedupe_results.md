# knowledge-digest Part B 評価記録

評価セットはtune / validate各10組、各分類2組ずつの合成fixture。記述・数値・URLは現実にありうる資料を模したテスト入力であり、検証済みファクトとして引用するものではない。試行間で評価セットは変更していない。

実行コマンド:

```bash
PATH="$PWD/.venv/bin:$PATH" python3 scripts/eval/run_dedupe_eval.py
```

システムのPython 3.11ではworkspaceの依存を読み込めないため、既存.venvのPython 3.12を使った。APIキーは環境変数から読む。Jevに渡したのはa / bのエントリだけで、label / keep / splitは渡していない。

評価は候補生成を通った組にだけJevを呼び、振り分けと案どうしの検査まで行う。聞き直しは評価では行わず、requeryをheldとして数える。受け入れ条件は事前に固定した誤統合0・conflictingの取りこぼし0・proposal率0.8以上。誤統合には残す側だけでなく理由の誤りも含めた。

評価セットSHA-256: `b31b1b53e531bcf58b96f0fe14b6a7ed91e5a505ca95e23e583a467edd8657e9`

## 試行1

文字2-gramの閾値はcore既定の0.35。Jevのinstructions / criteriaは計画どおり。終了コード1。

出力(そのまま):

```
threshold=0.5 wrong=0 missed_conflicts=0 proposal_rate=0.75
reject
tech-21/tech-22 label=duplicate judgment={'relation': 'duplicate', 'relation_confidence': 0.67, 'same_scope': 0.93, 'newer': 'same', 'newer_confidence': 1.0, 'keep': 'b', 'keep_confidence': 0.99} routing={'bucket': 'proposal', 'old': 'tech-21', 'by': 'tech-22', 'reason': 'duplicate'}
tech-23/tech-24 label=duplicate judgment=None routing={'bucket': 'held', 'old': '', 'by': '', 'reason': ''}
market-25/market-26 label=updates judgment={'relation': 'updates', 'relation_confidence': 0.99, 'same_scope': 0.81, 'newer': 'b', 'newer_confidence': 1.0, 'keep': 'a', 'keep_confidence': 0.51} routing={'bucket': 'proposal', 'old': 'market-25', 'by': 'market-26', 'reason': 'updates'}
trend-27/trend-28 label=updates judgment={'relation': 'updates', 'relation_confidence': 0.99, 'same_scope': 0.81, 'newer': 'a', 'newer_confidence': 1.0, 'keep': 'a', 'keep_confidence': 0.76} routing={'bucket': 'proposal', 'old': 'trend-28', 'by': 'trend-27', 'reason': 'updates'}
market-29/market-30 label=conflicting judgment={'relation': 'conflicting', 'relation_confidence': 0.61, 'same_scope': 0.53, 'newer': 'same', 'newer_confidence': 1.0, 'keep': 'a', 'keep_confidence': 0.82} routing={'bucket': 'conflict', 'old': '', 'by': '', 'reason': ''}
trend-31/trend-32 label=conflicting judgment={'relation': 'conflicting', 'relation_confidence': 0.59, 'same_scope': 0.67, 'newer': 'same', 'newer_confidence': 0.99, 'keep': 'a', 'keep_confidence': 0.78} routing={'bucket': 'conflict', 'old': '', 'by': '', 'reason': ''}
tech-33/tech-34 label=complementary judgment={'relation': 'complementary', 'relation_confidence': 0.99, 'same_scope': 0.19, 'newer': 'same', 'newer_confidence': 0.99, 'keep': 'b', 'keep_confidence': 0.46} routing={'bucket': 'excluded', 'old': '', 'by': '', 'reason': ''}
tech-35/tech-36 label=complementary judgment={'relation': 'complementary', 'relation_confidence': 0.97, 'same_scope': 0.35, 'newer': 'same', 'newer_confidence': 0.99, 'keep': 'b', 'keep_confidence': 0.36} routing={'bucket': 'excluded', 'old': '', 'by': '', 'reason': ''}
trend-37/trend-38 label=unrelated judgment={'relation': 'unrelated', 'relation_confidence': 0.98, 'same_scope': 0.02, 'newer': 'same', 'newer_confidence': 0.99, 'keep': 'a', 'keep_confidence': 0.51} routing={'bucket': 'excluded', 'old': '', 'by': '', 'reason': ''}
practice-39/practice-40 label=unrelated judgment=None routing={'bucket': 'held', 'old': '', 'by': '', 'reason': ''}
```

Redisの定性重複が候補に入らず、proposal率が0.75となった。Jevに到達しないため、質問文の調整では改善できない。spec §3の「候補生成の文字重複閾値は評価で決める」に従い、選び方をspec §8と計画Task 7に追記した。tuneのduplicate / updates / conflictingを全件拾える最も高い閾値を0.35から0.05刻みで選び、0.20になった。coreは変更せず、CLIから既存の引数に渡す。

## 試行2

文字2-gramの閾値をtuneのみで選んだ0.20にした。Jevのinstructions / criteriaと評価セットは試行1と同じ。終了コード0。

出力(そのまま):

```
overlap_threshold=0.2 threshold=0.5 wrong=0 missed_conflicts=0 proposal_rate=1.00
accept
```

Jevのinstructions / criteriaの調整回数は0回。判定Tは計画どおりtuneのみで0.50〜0.95を0.05刻みで走査し、誤統合0になる最小値0.50を選んだ。validateの統合対象4組は4組とも正しい側・理由でproposalsとなり、conflictingは2組ともconflictsに入った。CLIの`--threshold`既定値を0.50とし、設計書§3.2を同期した。coreの純関数の既定値はPart Aのままにし、CLIと評価から閾値を明示する。

## タスク終端の検証

| Task | pytest | ruff |
|---|---|---|
| 5 | 632 passed in 23.80s | All checks passed! |
| 6 | 650 passed in 25.10s | All checks passed! |
| 7(最終) | 660 passed in 25.07s | All checks passed! |

Codex単体プロファイルで自己レビュー済み。既存Jev関数の送信共通化、最後の判定を使う出力、候補生成を含めた評価、ラベルの非送信、CLIと評価の閾値の一致を確認した。

## Claudeの再実行と閾値ごとの比較(2026-10-04)

評価を再実行し、同じ結果(threshold=0.5、accept)を得た。閾値ごとに比べると次のとおり。

| T | tune: 誤統合 / proposal率 | validate: 誤統合 / proposal率 |
|---|---|---|
| 0.5 | 0 / 0.75 | 0 / 1.00 |
| 0.6 | 0 / 0.75 | 0 / 1.00 |
| 0.7 | 0 / 0.75 | 0 / 1.00 |
| 0.8 | 0 / 0.75 | 0 / 0.50 |

**この評価セット(tune 10組)では T を 0.5〜0.8 のあいだで識別できない**。0.5 は「誤統合0件の最も低い値」という規則の帰結であり、0.5 が安全だという根拠ではない。validate を見て T を選び直すと過適合になるため、規則どおり 0.5 を採る。統合案は人の承認を経て確定するので、T が低いことの影響は人に見せる候補が増えることに留まる。実データが増えたら tune に組を足して決め直す。

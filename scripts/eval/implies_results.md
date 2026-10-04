# decision-roadmap Part B 評価記録

評価セットは tune / validate 各12組、determines / narrows / none 各4組の合成fixture。案件の前提と依存関係を分類するテスト入力であり、検証済みファクトとして引用するものではない。評価セットは全試行で固定した。

受け入れ条件は事前に固定した validate の `none` に辺を張る率 ≤ 0.1、`determines` を辺として採用する再現率 ≥ 0.8。閾値は tune のみを使い、0.50〜0.95 を0.05刻みで走査し、誤った辺の率が1割以下となる最小値を選ぶ。validate の結果から閾値を選び直していない。

実行コマンド:

```bash
PATH="$PWD/.venv/bin:$PATH" python3 scripts/eval/run_implies_eval.py
```

システムの Python では workspace の依存を読み込めないため、既存 .venv の Python を使った。APIキーは環境変数から読む。各組の a / b / context だけを Jev に渡し、label / split は渡していない。組ごとの context を保持するため、計画サンプルの一括呼び出しを組単位の呼び出し(最大4並列、返却順は入力順)にした。

全組の判定、出力、評価セットと Jev ソースの SHA-256 は `implies_runs.jsonl` に追記保存した。

評価セット SHA-256: `1536be7a5da22ac8b474c8abe21562f33d78294e57029105bc868ef7786bc67d`

## 試行1

計画どおりの instructions / criteria。終了コード1。週次の発注周期という前提が唯一の未確認条件である組が narrows(確信度0.2)となり、determines の再現率が0.75で reject。

Jev ソース SHA-256: `827100e0ece0f3a876c65ed5ff40a359c2b140d6bbcaf649ceb3ba79197c9fc2`

出力(そのまま):

```text
tune_thresholds_equivalent=0.50,0.55,0.60,0.65 (この範囲では閾値を識別できない)
threshold=0.5 false_edge_rate=0.00 determines_recall=0.75
reject
validate[1] label=determines judgment={"choice": "narrows", "confidence": 0.2}
```

## 試行2

instructions / criteria の調整1回目。context の確認済み条件を明示して利用させ、「必要条件が分かるだけ」と「他の条件は確認済みでAだけが残る」を区別し、独立した同じ課題の仮説を none とした。終了コード0。validate の none 4組への誤った辺は0組、determines 4組の採用は4組で accept。

Jev ソース SHA-256: `a09e0ac8c720bb4a30e446ea9ef5cfc4db7dd5f863fc1bb45cfa1f9fb1ae4625`

出力(そのまま):

```text
tune_thresholds_equivalent=0.50,0.55,0.60,0.65 (この範囲では閾値を識別できない)
threshold=0.5 false_edge_rate=0.00 determines_recall=1.00
accept
```

## 質問文の調整

試行1の implies 質問:

> `pairs[n].a` の仮説が確定すると、`pairs[n].b` の仮説も決まるか。数値の計算や一致ではなく、仮説の意味の依存関係を分類する。

criteria:

- determines: Aが確定するとBも決まる
- narrows: Aが確定するとBの可能性が大きく絞られるが、Bはまだ決まらない
- none: Aが確定してもBは決まらず、可能性も大きく絞られない

試行2の implies 質問:

> `pairs[n].a` の仮説が確定すると、`pairs[n].b` の仮説も決まるか。`context` の明示された前提と確認済みの条件を使い、AからBへの向きを判定する。他の条件が確認済みで残る条件がAだけなら、Aの確定でBも決まる。未確認の条件が別に残る必要条件だけなら、Bは絞られるだけ。同じ課題に属するだけでは依存関係とはしない。数値の計算や一致は判定しない。

criteria:

- determines: Aが確定するとBの成立・不成立も決まる。直接の含意、またはcontextで他の条件が確認済みでAが唯一残る条件となる依存関係
- narrows: Aが確定するとBの可能性が大きく絞られるが、未確認の条件が別に残るためBの成立・不成立はまだ決まらない
- none: Aが確定してもBは決まらず、可能性も大きく絞られない。共通の課題・目的があるだけの独立した仮説を含む

## 閾値の識別

両試行とも tune の採用する辺は0.50〜0.65で同一であり、**この範囲では閾値を識別できない**。さらに tune の none は全組が none と判定されたため、誤った辺の率という選択基準だけでは0.50〜0.95のどの閾値も区別できない。0.5は計画の最小値を選ぶ規則の帰結であり、閾値の最適性を示す結果ではない。合成fixture各12組での受け入れ結果を記録し、CLIの `IMPLIES_THRESHOLD` と spec §5 を0.5に合わせた。

## 実装と計画サンプルの適合

- Task 5: pair に出てくる全仮説を items に含めた。計画のテストサンプルでは hyp-2 の本文が無く、指定された本文検索ができないため、完全な入力にした。鍵なし・応答の欠けや型違い・確率範囲・通信失敗も差し替えテストで検証した。
- Task 6: `artifacts get` は既存コマンドが常に JSON を返すため、サンプルの `--format json` をテストから外した。仮説と未確定事項は既存の採番・永続IDを維持する保存手順に合わせた。
- Task 6: `fermi calc` はモデル全体を model_dump で保存しており、既存コードのまま unit が残る。異なる単位を持つ複数モデルの保存結果を回帰テストで確認し、保存処理は変更しなかった。
- Task 6: `ArtifactStore.save` の保存時検査が ValueError を送出するため、CLIの例外処理内で保存する形に移し、保存拒否も非ゼロ終了と `error:` にした。
- Task 6: 既存 freshness と citation checker を再利用し、stale のIDに加えて状態と理由も出力した。rank の入力用 switch / reach / swing_ratio と、設計の pivot / keystone をともに返す。Jev への state には本文・課題ID・検証方法を渡し、計算値・感度・切り替え点を含めない。
- Task 6最終自己レビュー: unit 不一致でも各策の感度は計算し、切り替え点だけを core に拒否させた。感度まで止める実装を回帰テストで修正した。
- Task 7: 組ごとの context を保持し、ラベル非送信と tune のみの閾値選択をテストした。評価セットの最低件数・各ラベルの件数も実行前に検査する。評価の各試行を再現できるよう raw 判定と出力の記録を追加した。

Codex単体プロファイルでTDD・自己レビューを実施した。計画が参照する superpowers の実行スキルはこの環境には未配置のため、計画に記載された手順を直接実行した。skills と core には変更を加えていない。コミットとgit操作は行っていない。

## タスク終端の検証

`UV_CACHE_DIR=/tmp/medo-uv-cache UV_NO_SYNC=1` を指定し、既存 .venv を使用した。既定の uv キャッシュはサンドボックス内で書き込めないため /tmp に置いた。

| Task | pytest | ruff |
|---|---|---|
| 5 | 740 passed in 28.13s | All checks passed! |
| 6 | 774 passed in 30.81s | All checks passed! |
| 7(最終) | 785 passed in 30.15s | All checks passed!(指摘0件) |

## Claudeによる独立な再検証(2026-10-05)

試行1で validate の結果を見てから質問文を調整したため、**validate はもう独立した検証ではない**(計画が「満たさなければ質問文を最大3回調整してよい」としていたことによる。計画の誤り)。

そこで、質問文を見ていない別の Claude に新しい組を12組(determines / narrows / none 各4、業界を散らし、紛らわしい組を含む)作らせ、`scripts/eval/implies_holdout.json` に置いた。今の質問文と閾値 0.5 のまま**1回だけ**評価した。

| ラベル | 結果 |
|---|---|
| determines 4組 | 4組とも determines(確信度 0.94〜0.99) |
| narrows 4組 | 4組とも narrows(0.77〜0.95) |
| none 4組 | 4組とも none(1.00) |

`false_edge_rate=0.00`、`determines_recall=1.00`。受け入れ条件を満たす。

注意: holdout も LLM が書いた組で、実案件の仮説より整っている可能性がある。実案件の仮説で判定が外れたら、その組を holdout に足して評価し直す。**今後は holdout を調整に使わない**(結果を見て質問文を直したら、また新しい holdout が要る)。

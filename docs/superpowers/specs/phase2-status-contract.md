# フェーズ2 status契約

`medo status` が返す診断の構造。索引: [medo-phase2-design.md](medo-phase2-design.md)

**診断は報告であって強制ではない**(不変条件6)。未接続・未確認・未解決を検出しても保存を拒否しない。

---

## 1. 4階層の構造

当初案はトップレベルに9ブロックを並べており、同じ事実を複数の視点で返す重複があった(件数を `structure` と `loop` の両方で返す、確認状態を生データと診断の両方で返す等)。**元データと診断を同じ枝に置く4階層**に再編する。

```
status
├─ model        案件内容の充足(ドメインモデル由来)
│  ├─ structure   セクションごとの件数と確度
│  ├─ links       リンクの接続状況
│  └─ coverage    個々の対象が処理されているか
├─ workflow     進行の記録(ワークフローモデル由来)
│  ├─ checks      発見プロセスの実施状況 + 不整合
│  ├─ review      AsIsレビューの状況
│  ├─ responses   ステークホルダーの反応(畳み込み済み)
│  └─ loop        往復の現在地 + チェックポイント
├─ readiness    収束判定
│  ├─ state
│  └─ failed_conditions
└─ actions      推奨する次の行動
```

各ステージは対応する枝だけを読めば進められる:

| Stage | 読む枝 |
|---|---|
| 1. Investigate & Draft | `model` |
| 2. Internal Review | `model.links` / `workflow.review` |
| 3. Client Dialogue | `workflow.responses` |
| 4. Adapt & Decide | `readiness` / `actions` |

---

## 2. 診断の対象範囲

**既定では `scope: "core"` の項目のみを診断対象とする**(`ScopedNode` を継承する型に限る)。往復のたびに課題とGAPが蓄積するが、すべてを今回解くわけではない。スコープを絞らないと、重要度の低い項目にまで一律にアラートが出て実務が埋没する。

`--include-scope secondary,out` で範囲を広げられる。

### 段階的に開示する

初回ヒアリング直後に全診断を出すと、「未検証」「未突合」「GAP」「not_ready」が一斉に並び、**全部埋めないと動かない**という印象を与える。探索の初期段階では収束に関する警告を出さない。

| `diagnostic_phase` | 判定 | 出す診断 |
|---|---|---|
| `discovery`(`to_be` が0件) | 探索中 | `model` と `actions`。`readiness` は `not_evaluable` |
| `convergence`(`to_be` が1件以上) | 収束に向かっている | 全診断 |

これは発散から収束へ段階的に進むダブルダイヤモンドの考え方に沿う([Design Council](https://www.designcouncil.org.uk/our-resources/the-double-diamond/))。

---

## 3. JSON契約

```json
{
  "project": "medo-ops",
  "diagnostic_phase": "convergence",
  "model": {
    "structure": {
      "as_is":        {"count": 3, "confirmed": 2, "public": 1, "internal": 2},
      "to_be":        {"count": 2, "confirmed": 0, "assumed": 2, "open": 0},
      "kpis":         {"count": 0, "confirmed": 0},
      "stakeholders": {"count": 2, "confirmed": 2},
      "gaps":         {"count": 1, "perception": 1, "internal_conflict": 0, "goal": 0},
      "bottlenecks":  {"count": 0, "confirmed": 0},
      "constraints":  {"count": 1, "confirmed": 1},
      "attempts":     {"count": 1, "confirmed": 0},
      "challenges":   {"count": 5, "confirmed": 4}
    },
    "links": {
      "challenges_without_cause": ["ch-2"],
      "gaps_without_bottleneck": [],
      "to_be_without_kpi": ["tb-1"],
      "hypotheses_unvalidated": ["hyp-1", "hyp-3"]
    },
    "coverage": {
      "public_as_is_without_verification": ["as-1"],
      "challenges_without_attempt": ["ch-1", "ch-4"],
      "artifacts_without_challenge_coverage": []
    }
  },
  "workflow": {
    "checks": {
      "states": {
        "reality_gap": "unverified",
        "past_attempts": "identified",
        "hidden_stakeholders": "confirmed_none",
        "decision_maker": "unverified"
      },
      "inconsistent": []
    },
    "review": {
      "current_target": "as-is-report-v2",
      "open_findings": ["gap-1"]
    },
    "responses": {
      "effective": [
        {"stakeholder_id": "sh-1", "purpose": "as_is_alignment", "reaction": "empathized"},
        {"stakeholder_id": "sh-2", "purpose": "as_is_alignment", "reaction": "objected"}
      ],
      "open_objections": ["ev-7"],
      "go_ahead": {"decision_maker": "sh-1", "agreed": false},
      "subsumed": []
    },
    "loop": {
      "round_count": 2,
      "focus_hypothesis": "hyp-1",
      "reality_evidence": {"internal_as_is": 2, "constraints": 1, "resistant_stakeholders": 0},
      "checkpoint": {"state": "pending", "since_version": 2},
      "divergence_warning": false
    }
  },
  "readiness": {
    "state": "not_ready",
    "failed_conditions": [
      {"code": "as_is_report_missing", "refs": []},
      {"code": "unsupported_confirmed_to_be", "refs": []},
      {"code": "discovery_check_missing", "refs": ["reality_gap", "decision_maker"]},
      {"code": "review_findings_open", "refs": ["gap-1"]},
      {"code": "to_be_go_ahead_missing", "refs": ["sh-1"]},
      {"code": "high_influence_objection_open", "refs": ["ev-7"]}
    ]
  },
  "actions": [
    {"code": "answer_tobe_checkpoint", "reason": "節目で未回答"},
    {"code": "resolve_objection", "refs": ["ev-7"]}
  ]
}
```

### 診断キーの判定式

各キーの入力と判定を明示する。

**scope による絞り込みは `ScopedNode` を継承する型にのみ作用する**([ドメインモデル](phase2-domain-model.md) §3)。`Kpi` / `Stakeholder` / `Hypothesis` / `Attempt` は scope を持たないため常に全件が対象になる。`--include-scope` はこれらに影響しない。

| キー | 判定式 |
|---|---|
| `links.challenges_without_cause` | `bottleneck_ids` と `cause_hypothesis_ids` の**両方が空**の課題 |
| `links.gaps_without_bottleneck` | `kind="goal"` の gap のうち、どの `Bottleneck.gap_ids` からも参照されないもの |
| `links.to_be_without_kpi` | どの `Kpi.to_be_ids` からも参照されない `to_be` |
| `links.hypotheses_unvalidated` | `status` が `unvalidated` または `validating` の仮説 |
| `coverage.public_as_is_without_verification` | `visibility="public"` かつ `reality_checked=False` かつ、その ID を `from_as_is` に含む有効な `perception` Gap が存在しないもの |
| `coverage.challenges_without_attempt` | どの `Attempt.challenge_ids` からも参照されない課題(`outcome="not_attempted"` の記録があれば確認済みとして除外) |
| `coverage.artifacts_without_challenge_coverage` | カバレッジ適用型の生成物のうち、最新の core 課題集合に未対応のものがあるもの |

### actions の優先順位

`actions` は下表の順に評価し、該当するものを順に並べる。**`actions[0]` が旧 `next_step` に相当する**。

| 順 | code | 条件 |
|---|---|---|
| 1 | `answer_tobe_checkpoint` | 未回答の `MilestoneDetected` がある |
| 2 | `resolve_objection` | 有効値としての `objected` がある |
| 3 | `address_review_findings` | 未解決の `changes_requested` がある |
| 4 | `draft_strawman_to_be` | `to_be` が0件で、`internal` AsIs が1件以上ある |
| 5 | `generate_as_is_report` | 最新要件版から生成された `as-is-report` が無い |
| 6 | `run_check` | `unverified` の check がある(段階に応じた項目のみ) |
| 6b | `explore_undeterminable` | `undeterminable` の check がある。**判断できなかったこと自体を掘る** |
| 6c | `consider_promotion` | 未昇格の `internal_conflict` または `undeterminable` がある。**課題として扱うか判断する** |
| 7 | `regenerate_stale_artifacts` | stale な生成物がある(**往復進行中は順位を下げる**。下記) |
| 8 | `proceed_to_propose_options` | `readiness.state == "ready"` |
| 9 | `continue_hearing` | 上記のいずれにも該当しない |

**Discovery段階でも `actions` は必ず何かを返す**(agy指摘)。`readiness` を出さない段階でも、順位4・5・6が「次に何をすべきか」を示す。当初案は Discovery で `readiness` を非表示にする一方で `actions` の生成規則が無く、初日の利用者が立ち往生する状態だった。

### 理由をコードで返す

`failed_conditions` は自然文ではなく**理由コード + 参照ID**で返す。自然文だとSkillの契約が文言に依存し、テストが不安定になる。コードは[ワークフローモデル](phase2-workflow-model.md) §7 の肯定条件表と1対1で対応する。

**ただしこれは「失敗条件」ではなく「次の一手の候補」である**。当初案は診断の語彙がほぼすべて「足りない・間違っている」の枠組みで、監査人の視点になっていた。不変条件6「診断は報告であって強制ではない」と書きながら、`not_ready` をゲートに読める位置に置いていた。

`readiness` は求められたときに答える位置に下げ、**`actions`(次にできること)を主役にする**。同じデータを返すが、Skillが最初に読むものを変える。

### stale と「今すぐ再生成すべき」は別

**stale が1件でもあれば再生成を最優先する、という挙動を採らない**。早期に生成物を作った後、往復のたびにToBeの確度や本文が変わって生成物がstaleになり、周回ごとに再生成へ誘導されてしまう。

`actions` は複数を返し、**往復が進行中**(`checkpoint.state == "pending"` または `to_be.confirmed == 0`)のあいだは stale生成物の再生成を最優先にしない。「この版で提案を更新する」とユーザーが決めるまでは往復の継続を優先候補として提示する。

---

## 4. projection

**単一コマンドを維持し、返す範囲を絞る**。診断ごとに別コマンドへ分割すると、ホストLLMのシェル呼び出し回数が増え、異なる時点の状態を組み合わせるリスクも生じる。一方でSkillは開始・終了ごとに `status` を呼ぶため、毎回全量をコンテキストへ入れると累積コストになる。

```
medo status --project <id>                      # 既定 = --view summary
medo status --project <id> --view full          # 全診断
medo status --project <id> --view model         # 枝だけ(model|workflow|readiness|actions)
medo status --project <id> --include-scope secondary
medo status --project <id> --format json|digest
```

- `--view summary`(既定): **`actions` を先頭に置く**。続いて `diagnostic_phase` / `workflow.loop.round_delta` / `workflow.loop.checkpoint` / `workflow.responses.open_objections` / `workflow.review.open_findings`。`readiness` は `state` のみを返し、`failed_conditions` は `--view readiness` で取る
- `--view full`: 全4階層
- `--view <枝名>`: その枝のみ

`--view` は単一の値を取り、`summary` / `full` / 枝名のいずれか。**枝名と `full` を同時に指定できない**(排他)。

通常のSkillは `summary` を使い、原因を掘るときだけ `full` または枝名を使う契約とする([Skill構成と移植性](phase2-skill-portability.md))。

---

## 5. 後方互換

フェーズ1の `medo status` はフラットなJSON(`requirements` / `facts` / `artifacts` / `next_step`)を返している。

- `next_step` は `actions[0].code` として返し続ける
- フェーズ1の `artifacts` 配列は `model` 直下に残す(生成物の一覧と stale フラグ)
- **`--view summary` に後方互換フィールドを含める**: `requirements`(最新版・confidence件数)・`facts`(件数・stale件数)・`artifacts`(型ごと最新版とstaleフラグ)・`next_step`。フェーズ1のSkillはこれらだけで動く
- `medo-hearing` は `medo-investigate` に統合するが、**フェーズ2の移行期間中は同名のSkillを残す**(本文は `medo-investigate` を呼ぶよう案内するだけの薄いwrapper)。統合完了後に削除する

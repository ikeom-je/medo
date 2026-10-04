# knowledge-digest とナレッジ来歴(フェーズ2・後続)

ステータス: 未承認(実装着手前)

案件を跨いで蓄積したナレッジの**重複を統合し、置き換えの来歴を残す**設計。統合の判断はJev(TypeSafe System One)に段階ごとに分類させて絞り込み、確定は人の承認とCLIの決定論に残す。

親: [medo-phase2-design.md](medo-phase2-design.md)(「後続」の ナレッジ来歴 / `knowledge-digest`)。関連: [ナリッジとメモリの階層](phase2-knowledge-memory.md) / [出典検証の強化](phase2-source-verification.md) / [生成物のライフサイクル](phase2-artifact-lifecycle.md)

---

## 1. なぜ要るか

案件横断のナレッジ(`knowledge/{kind}/`)は追記のみで、重複を扱う仕組みが無い。フェーズ1の統合スモークでは、同じ論文(arXiv:2311.17311)由来の内容をClaudeとGeminiが独立に保存した(`docs/setup.md`)。重複が残ると:

- 検索結果が同じ事実で埋まり、文字数予算(#138)を食う
- 同じ指標の新旧の値が並び、どちらを引用すべきか分からない
- 値の食い違い(転記ミスか出典の違い)が埋もれる

また、エントリを置き換えたという**来歴を表す手段が無い**。生成物は `cited_knowledge` でIDを引用するが、引用先が別のエントリに取って代わられても検出できない。

### 範囲

v1 は**案件横断のナレッジ**(`KnowledgeStore`)に限る。生成物が `cited_knowledge` で引用するのはこちらだけだからである。案件固有ナレッジ(`knowledge/projects/`)とファクトの重複は後続に回す。

重複の統合と来歴を主目的とし、**鮮度の見直し**(stale エントリの再取得)と**要約・圧縮**は含めない(§7)。

---

## 2. 方式の選択

| 案 | 内容 | 判断 |
|---|---|---|
| **A(採用)** | 決定論で候補の組を作り、Jevが関係を分類して残す側を選び、人の承認後にCLIが確定する。新しい文は生成しない | 言い換え型の重複を拾え、数値の通り道にLLMを挟まない。確定は人とCLIに残る |
| B | Gemini Flash のAPIで構造化・統合する(tech.md の当初案) | 外部APIへの常設依存が入り、差別化軸「クラウド非依存」とぶつかる。件数が3桁未満の今は割に合わない |
| C | 決定論だけ(同じ出典URLかつ同じ数値なら重複) | 言い換えや、同じ論文を別URL(abs と pdf)から引いた重複を拾えない。実際に起きた重複はこの型 |

---

## 3. 重複統合のパイプライン

| 段 | 担い手 | 内容 |
|---|---|---|
| ① 候補の組を作る | CLI(決定論) | 同じ kind の中で、次のいずれかを満たす組だけを候補にする: 出典URLのホストとパスが同じ(クエリと拡張子の差、arXiv の `abs`/`pdf` の差は同一視)/ `value` と `unit`(注記を除く)が同じ / `statement` の語の重なり(Jaccard)が閾値以上。全組み合わせをJevに投げないための前処理 |
| ② 関係を分類する | **Jev** | 全組の質問を1リクエストに並べて並列に判定する(下表の `relation` / `same_scope` / `primary_source`) |
| ③ 残す側を選ぶ | **Jev** | `duplicate` / `updates` の組について `keep` を判定する |
| ④ 統合案を組み立てる | CLI(決定論) | ②③の結果と確信度から、`proposals` / `conflicts` / `held` に振り分ける(§3.2)。**新しい文は生成しない**。既存エントリのどちらかを残す |
| ⑤ 確定する | 人の承認 → CLI | 承認された組だけ `supersede` で確定する(§5) |

### 3.1 Jevに聞く質問(1組あたり)

| ID | 型 | 内容 |
|---|---|---|
| `relation` | choice | `duplicate`(同じ事実)/ `updates`(同じ指標の新しい値)/ `complementary`(同じ対象の別の側面)/ `conflicting`(同じ指標なのに値が食い違う)/ `unrelated` |
| `same_scope` | noul | 2つのエントリの年・地域・対象が一致しているか(`duplicate` と `updates` を分ける根拠) |
| `primary_source` | noul ×2 | 各エントリの出典が一次資料か |
| `keep` | choice | `duplicate` / `updates` のとき、どちらを残すべきか。基準は一次資料か・具体的か・新しいか |

**決定論に残す部分**: どちらが新しいかは `retrieved` の日付でCLIが決める。数値が一致するかはCLIが判定し、Jevには判定させない(原則1)。

`state` には各エントリの `statement` / `value` / `unit` / `source` / `retrieved` / `note` を渡す。Jevに数値を書かせることはなく、Jevの出力は分類と選択だけである。

### 3.2 確信度による振り分け

`relation` の確信度(choice の `confidence`)で段階を分ける。

| 条件 | 扱い |
|---|---|
| `conflicting` | **確信度に関係なく `conflicts` に入れる**。値の食い違いは事実の誤りに直結するので、見落とすほうが害が大きい。統合はしない |
| `complementary` / `unrelated` で確信度 0.8 以上 | 偽の重複として除く |
| `duplicate` / `updates` で確信度 0.8 以上 | `proposals` に入れる(確定には人の承認が要る) |
| 確信度 0.5〜0.8 | 各エントリの出典本文の抜粋を足して**1回だけ**聞き直す(§3.3)。0.8 以上になれば上の行に従い、ならなければ `held` |
| 確信度 0.5 未満 | `held` |

**同じ質問をそのまま聞き直さない**。Jevは同じ入力にほぼ同じ確率を返す(triage の評価セットを2回流したとき、premise の変動は ±0.06 程度だった)。確信度を上げるのは聞き直しではなく入力の追加である(triage は根拠のコード片を渡しただけで識別不能から 8/8 に改善した, #160)。

**閾値の 0.8 は出発点であり、評価セットで決める**(§8)。誤って統合する害は、統合し損ねる害より大きい(引用の連鎖で誤りが広がる)ため、「評価セットで誤った統合案が0件になる最も低い値」を採る。最後は人が承認するので、閾値が主に決めるのは人に見せる候補の量と雑音である。

### 3.3 聞き直しの根拠

出典検証で作った取得の仕組み(`cli/src/medo_cli/fetch.py`)で各エントリの `source` を取得し、`statement` の数値の周辺(出典検証の「近い箇所」と同じ抽出)を `evidence` として `state` に足す。取得に失敗したエントリは evidence 無しのまま聞き直す。聞き直しは1組につき1回までとする。

---

## 4. 来歴のスキーマ

`KnowledgeEntry` に次のフィールドを足し、OKF の frontmatter に保存する。

```python
superseded_by: str = ""                                    # 後継エントリのID(同じkind)
supersede_reason: Literal["", "duplicate", "updates"] = ""
superseded_on: str = ""                                    # 置き換えた日 YYYY-MM-DD
```

- **来歴は旧エントリの側だけが持つ**。後継側に `supersedes` の一覧は持たせず、必要なときは全件を走査して逆引きする。両側に持たせると片方だけ更新されて食い違うおそれがある
- 既存データはフィールドを持たないので空として読み込む。移行は不要

### 4.1 置き換えの検査(CLIが拒否する)

- 後継が存在し、同じ kind である
- 後継自身が置き換え済みでない
- 旧エントリが置き換え済みでない(同じエントリを2度置き換えない)
- 旧と後継が同じIDでない(循環は上の2条件で起こり得ない)

### 4.2 検索と索引

- `knowledge search` / `knowledge index` は置き換え済みのエントリを既定で除く。`--include-superseded` で含める。`index.md` の件数も置き換え済みを除いて数える
- `knowledge get`(IDでの直接読み出し)は従来どおり返し、`superseded_by` を表示する。古い引用を人が追えるようにするため

---

## 5. 旧エントリを引用している生成物

- 生成物は版ごとに固定した記録なので、**引用IDを自動で書き換えない**。書き換えると、その版が実際には参照していなかった内容を引用したことになる
- 引用先が置き換え済みなら、その生成物を **stale** と判定する。`make_citation_checker`(`core/src/medo_core/context.py`)の判定に「引用先が置き換えられた」を足す。理由には後継のIDを添え、作り直す版が何を引用すべきかを示す
- status の `regenerate_stale_artifacts` にそのまま載るので、Skillは既存の手順で作り直せる
- `duplicate` も `updates` も扱いは同じ stale とする。数値が変わり得るので、作り直さずに済ませる経路は作らない

### 5.1 取り消し

案件横断のナレッジはもともと別の git リポジトリで管理している(tech.md)。誤った置き換えは git の履歴から戻せるので、専用の取り消しコマンドは作らない。

---

## 6. コマンドと Skill

### 6.1 CLI

| コマンド | 内容 |
|---|---|
| `medo knowledge dedupe --kind <k> [--format json\|digest]` | §3 の①〜④を実行し、`proposals` / `conflicts` / `held` を出力する。**書き込みはしない** |
| `medo knowledge supersede --kind <k> --old <id> --by <id> --reason duplicate\|updates` | 承認された1組を確定する。§4.1 の検査を通し、索引を作り直す。旧エントリを引用している生成物を**全案件から探して一覧表示**する |

`proposals` の各要素は `old`(置き換えられる側)/ `by`(残す側)/ `reason` / `relation` / `confidence` / `same_scope` / `primary_source` / `requeried`(聞き直したか)を持つ。`conflicts` と `held` は組と分類・確信度を持つ。

### 6.2 Jevが使えないとき

既存の `research triage` と同じ扱いにそろえる。`TYPESAFE_API_KEY` が無いか呼び出しに失敗したら、①の候補の組だけを `judge: unavailable` 付きで返し、統合案は出さない。

決定論だけで統合案を作る代わりの経路は設けない。誤った統合は引用の連鎖を通じて広がるので、推測で補わずそのまま人に見せる(原則5)。

### 6.3 Skill `medo-knowledge-digest`(新規)

標準周回の段階には属さない、ナレッジの保守作業として独立させる。description が既存の6本と重ならないので、選択がぶれる心配はない([Skill構成と移植性](phase2-skill-portability.md) の条件を満たす)。

手順:

1. `medo knowledge index` で全体を見る
2. kind ごとに `medo knowledge dedupe --kind <k>` を実行する
3. `proposals` / `conflicts` / `held` を、根拠(分類・確信度・出典)と一緒にユーザーに見せる。`conflicts` は統合せず、出典を開いて確認するよう案内する
4. **ユーザーが承認した組だけ** `medo knowledge supersede` で確定する
5. 作り直しが要る生成物(`supersede` の出力)を報告する

`judge: unavailable` のときは、候補の組を見せて判定できなかったことを報告し、統合はしない。

---

## 7. 配置

| 層 | 内容 |
|---|---|
| core `knowledge.py` | 来歴フィールド、§4.1 の検査を含む `supersede`、検索と索引からの除外、逆引き |
| core `knowledge_dedupe.py`(新規) | 候補の組の生成(純関数)、確信度による振り分け(純関数)、引用している生成物の全案件からの逆引き |
| core `context.py` | 「引用先が置き換えられた」による stale |
| cli `jev.py` | 組ごとの4問の判定(`judge_pairs`)。聞き直しの evidence を含む |
| cli `main.py` | `knowledge dedupe` / `knowledge supersede` |
| skills | `medo-knowledge-digest` |

coreはJevを呼ばない(LLM・外部API呼び出しはcliのアダプタ側。structure.md の依存方向)。振り分けの関数はJevの判定結果を受け取る純関数とする。

---

## 8. テストと評価

- 候補の組の生成、§4.1 の検査、検索からの除外、stale の判定は決定論のユニットテストにする
- Jevは既存のテストと同じく `urlopen` を差し替える。`TYPESAFE_API_KEY` 無し・失敗で `judge: unavailable` になること、聞き直しが1回で止まること
- **正解付きの評価セット**(`scripts/eval/` に triage と同じ形式で置く)。次の5種類を含め、Jevの分類が正解と合うかを実装の受け入れ条件にする。閾値(§3.2)はこの評価で、誤った統合案が0件になる最も低い値に決める
  - 同じ論文を abs と pdf から引いた重複(`duplicate`)
  - 同じ指標の新旧の値(`updates`)
  - 同じ指標で値が食い違う(`conflicting`)
  - 同じ対象の別の側面(`complementary`)
  - 無関係な組(`unrelated`)

---

## 9. 実装の分割

| # | 内容 | 担当 |
|---|---|---|
| A | core: 来歴スキーマ、§4.1 の検査、検索と索引からの除外、「置き換え」による stale、候補の組の生成、振り分け、逆引き | Codex が実装、Claude がレビュー |
| B | cli と jev: `dedupe` / `supersede`、Jevの4問と聞き直し、評価セットと閾値の決定 | Codex が実装、Claude がレビュー |
| C | Skill `medo-knowledge-digest` と設計書・tech.md の同期(digest のLLM方針を Gemini Flash から本設計へ改める) | Claude が書き、Codex と agy がレビュー |

Aから順に。B と C は CLI の契約(新しいコマンド)と Skill を変えるので人間レビューの対象。**Bの `knowledge search` / `index` の出力から置き換え済みが消えるのもSkill契約に影響する**。

---

## 10. やらないこと

- **統合文の生成**: どちらかを残せば足りる。新しい文を生成すると数値の通り道が増える
- **鮮度の見直し**(stale エントリの再取得・廃止の提案): 主目的から外した。来歴(`supersede_reason: updates`)はその受け皿として使える
- **要約・圧縮**: 件数が少ない今は効果が出にくい
- **案件固有ナレッジとファクトの重複**: 生成物から `cited_knowledge` で引用されないため後続に回す
- **ベクトル検索・埋め込み**: 候補の組は決定論で作る([ナリッジとメモリの階層](phase2-knowledge-memory.md) §8 と同じ判断)
- **Gemini Flash などの外部APIによる構造化**: 案B を採らない(§2)

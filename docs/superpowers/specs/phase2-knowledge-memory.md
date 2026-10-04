# ナリッジとメモリの階層(フェーズ2)

ステータス: 未承認(実装着手前)

周回のたびに得た要点を、次の周回と次の案件が使える形で残すための設計。保存の形式は [OKF(Open Knowledge Format)](https://github.com/google/open-knowledge-format) v0.2 に寄せ、階層の切り方と取り出し方は [TencentDB-Agent-Memory](https://github.com/TencentCloud/TencentDB-Agent-Memory) を参考にする。

親: [medo-phase2-design.md](medo-phase2-design.md)。関連: [Skill構成と移植性](phase2-skill-portability.md) / [ワークフローモデル](phase2-workflow-model.md)

---

## 1. なぜ要るか

product.md は「案件を跨いで育つ技術ナリッジ」を差別化軸に置いている。実装は `knowledge/{kind}/`(案件横断)と `knowledge/projects/{id}/`(案件固有)を持ち、CLIの保存・検索も通る。**足りないのは書き手と読み方である**。

実測(2026-09-23 時点、`skills/src/*/SKILL.md` を全走査):

| 確認したこと | 結果 |
|---|---|
| `knowledge save` を指示しているSkill | `medo-investigate` / `medo-propose-options` / `medo-grow-prfaq` の3本 |
| そのうち案件横断(`--kind`)で保存するもの | **0本**。すべて `--project` 付きの案件固有 |
| `medo-review` / `medo-dialogue` / `medo-decide` のナリッジ保存 | **無し** |
| 保存されるfrontmatter | `kind` / `statement` / `value` / `unit` / `source` / `retrieved` / `note`。**OKFの必須フィールド `type` が無い** |
| 概要から辿る仕組み | **無し**。`KnowledgeStore.search()` は全 `.md` のfrontmatterを読んでから絞り込む |
| 打ち切りの予算 | 件数(`limit`、既定10)のみ。**文字数予算が無い** |

つまり**レビューと対話で得た要点はどこにも残らず**、蓄積したナリッジは**全部読まないと使えない**。前者は原則3(課題も要件も最初から確定しない)の裏返しである「周回で分かったことを次に渡す」が効かないことを意味し、後者は蓄積が増えるほどコンテキストを食う。

---

## 2. 層の切り方

ユーザーの指定により**セッション層(1 issue / 1コンポーネント単位のメモリ)は置かない**。2層で始める。

| 層 | 置き場所 | 寿命 | 誰が書くか |
|---|---|---|---|
| **永続ナリッジ** | `knowledge/{kind}/`(案件横断)/ `knowledge/projects/{id}/`(案件固有) | 無期限。鮮度契約(原則4)で古さを表す | Skillの手順がCLI経由で書く |
| **一時中間メモリ** | ホストの作業ファイル(`/tmp/*.yaml` 等) | その周回の中だけ | ホストLLMが直接書く |

**一時中間メモリをCLIに持たせない**。移植性の条件1は「状態はすべてCLIに置く」だが、一時中間メモリは状態ではなく**作業の足場**である。CLIに置くと寿命と掃除の責任がCLI側に生まれ、`medo status` が「消し忘れた中間ファイル」を診断対象に抱え込む。要件の雛形(`/tmp/req.yaml`)が今もこの扱いで、それで足りている。

セッション層を置かない理由は、置くと**同じ事実が3か所に増える**ため。永続に上げるか捨てるかの二択にすれば、判断が1回で済む。必要になったら足す。

---

## 3. TencentDB-Agent-Memory から何を採るか

| 向こうの層・仕組み | medoでどうするか | 理由 |
|---|---|---|
| L0 Conversation(会話ログ) | **採らない** | 進行記録の正本は events(`WorkflowRecorder`)で既にある。会話そのものを残すと出典のない文が混ざり、原則1と衝突する |
| L1 Atom(原子的な事実) | **採用済み** | `KnowledgeEntry` / `ProjectKnowledgeEntry` が1エントリ=1文でこれに当たる |
| L2 Scenario(場面でまとめた要約) | **新規に採る** | `index.md` として実装する(§4) |
| L3 Persona(相手の人格モデル) | **採らない** | 個人利用で認証・マルチテナントを持たない(不変条件5)。相手の人格を推定して保持する必要が無く、推定は原則5(推測で補完しない)に反する |
| 検索は L2/L3 で bootstrap し、足りなければ L1/L0 に降りる | **採る。ただし bootstrap を絞り込みには使わない** | 要約で絞ると要約から漏れた語で取りこぼす(§5)。`index.md` は「読むべきか」を決める材料であって、検索のフィルタではない |
| 結果を件数・文字数・タイムアウトで打ち切る | **件数と文字数を採る。タイムアウトは採らない** | 読み先はローカルファイルで、時間ではなく量が効く |

---

## 4. OKF に寄せる

OKF v0.2 の必須フィールドは `type` だけで、残りは任意。**全部を一度に入れず、判断に効くものから入れる**。

### 4.1 エントリのfrontmatter

```yaml
---
type: knowledge            # OKF必須。medoでは knowledge 固定
kind: tech                 # 既存5種 + practice(§4.3)
statement: Cloud Run のリクエストタイムアウト上限は60分
sources:                   # 既存の source を OKF の複数形に寄せる(単数も受ける)
  - https://cloud.google.com/run/docs/configuring/request-timeout
generated: "2026-09-20"    # 既存の retrieved に対応
stale_after: "2026-10-20"  # 鮮度契約(tech 30日 / 他 180日)から導出。コードが書く
status: unverified         # unverified | machine-confirmed | human-reviewed
actor: claude-opus-5       # 書いた主体。人間なら human:<id>
---

本文は任意。出典からの引用は引用の範囲に留め、URLと資料名を併記する。
```

**`stale_after` はコードが導出して書く**。LLMに計算させない(原則1)。`retrieved` と `source` は後方互換のため読み続ける。

**`status` の初期値は `unverified`**。`human-reviewed` に上げられるのは人間の操作だけで、Skillの手順からは上げない。上げる経路は本設計では作らず、必要になってから足す。

### 4.2 `index.md`(progressive disclosure)

`knowledge/{kind}/index.md` と `knowledge/projects/{id}/index.md` を置く。**これが TencentDB でいう L2 Scenario に当たる**。

```yaml
---
type: index
kind: tech
entry_count: 42
generated: "2026-09-23"
---

## このkindに何があるか

- Cloud Run / Cloud Functions の制限と料金(12件)
- BigQuery の取り込み経路(8件)
- ...
```

**`index.md` はCLIが生成する**。エントリを保存・削除したときに作り直す。見出しの文章はLLMが書いてよいが、件数と生成日は**コードが数える**(原則1)。

**stale件数はファイルに書かない**。鮮度は時間の経過だけで変わるため、保存時に焼き込むと次の保存まで実態とずれ続ける。読み出すときにコードが `stale_after` と今日を比べて数える。

`index.md` を読めば「このkindに使える情報があるか」が本体を開かずに分かる。

### 4.3 `practice` kind を足す

既存の5種のうち `tech` / `market` / `policy` / `trend` は **URLを必須**にしており(`_URL_KINDS`)、残る `company` は個社ファクトを指す。**レビューや対話で得た「進め方のノウハウ」を入れる先が無い**。

`practice` を足す。

| | |
|---|---|
| 意味 | 案件を跨いで使える進め方の知見(レビューで繰り返し出る指摘の型、効いた問い方) |
| `sources` | **必須。ただしURLでなくてよい**(例: `medo-review 2026-09-23対話`)。案件固有ナレッジ(`ProjectKnowledgeEntry`)と同じ扱い |
| 鮮度 | 180日(既定) |

出典必須を緩めない(原則5)。緩めるのは**出典の形式**であって、出典の有無ではない。

---

## 5. 取り出し方

**`index.md` を検索の絞り込みに使わない**。索引は要約であり、要約に載らなかった語で引くと、実体があるのに「無い」と返る。取りこぼしは黙って起きるので、呼び出し側からは検出できない(原則5に反する)。

役割を2つのコマンドに分ける。

| コマンド | 何を返すか | いつ使うか |
|---|---|---|
| `medo knowledge index [--kind <k>]` | 各kindの `index.md`(件数・stale件数・見出し) | **本体を開く前**に「使えるものがありそうか」を判断する |
| `medo knowledge search <query>` | エントリの実体。**索引を経由せず全エントリを走査する** | 実際に引く |

これが TencentDB の「L2 で bootstrap し、足りなければ L1 に降りる」に当たる。**降りる経路を索引に依存させない**点だけが違う。

`search` には予算を2つ入れる。

| 予算 | 既定 | 理由 |
|---|---|---|
| 件数 | 10(既存の `limit`) | 既存の挙動を変えない |
| 文字数 | 4000 | エントリが長文化しても呼び出し側のコンテキストが破裂しない |

**打ち切ったことは返り値に出す**。`truncated: true` と「何件中何件を返したか」を添える。黙って切ると、呼び出し側が「これで全部」と誤認する(原則5)。

---

## 6. 誰がいつ書くか

| Skill | 書くもの | 層 |
|---|---|---|
| `medo-investigate` | 調査で分かった業界・現場のノウハウ | 案件固有(既存) |
| `medo-review` | **レビューで繰り返し出た指摘の型**(例: 「討議用スライドで断定調にすると反発が出る」) | **案件横断(新規)** |
| `medo-dialogue` | **対話で効いた問い方・効かなかった問い方** | **案件横断(新規)** |
| `medo-decide` | **判断が割れた論点と、決め手になった材料** | 案件固有(新規) |
| `medo-propose-options` | 打ち手の比較で効いた技術情報 | 案件固有(既存)+ 案件横断(新規) |
| `medo-grow-prfaq` | PRFAQ育成で使った技術的背景 | 案件固有(既存)+ 案件横断(新規) |

**案件横断に上げる条件を、判定できる形で手順に書く**。「他の案件でも起きそうなら」では抽象的すぎて、案件固有の事情が混入する。

> **固有名詞を消しても文が成り立つなら案件横断(`--kind`)、成り立たないなら案件固有(`--project`)。**

「A社の受注センターは紙を嫌う」は固有名詞を消すと何も残らないので案件固有。「現場の作業者が関わる変更は、決裁者の合意より先に現場の反応を取ったほうが早い」は残るので案件横断。

判断はホストLLMがするが、**出典必須の検証はCLIが落とす**(`tech` / `market` / `policy` / `trend` はURL必須、`practice` と `company` は自由記述だが空は拒否)。

レビューの指摘そのもの(`AsIsReportReviewed.slide_findings`)は events に残り続ける。**ナリッジに上げるのは個別の指摘ではなく、そこから一般化した型**である。この区別を手順に明記しないと、案件固有の指摘が案件横断ナリッジを汚す。

---

## 7. 実装の分割

| # | 内容 | 影響範囲 |
|---|---|---|
| A | エントリのOKF化(`type` / `sources` / `stale_after` / `status` / `actor`)と後方互換の読み取り、`practice` kind の追加 | core(`knowledge.py`)・CLI |
| B | `index.md` の生成と `medo knowledge index` の追加、`search` の文字数予算と `truncated` | core・CLI。**`medo knowledge search` の出力が変わる = Skill契約に影響** |
| C | 各Skillの手順にナリッジ保存を足す(案件横断の判断基準つき) | skills。**80行上限との調整が要る** |

Aから順に。BはAの `stale_after` を使い、CはBの検索形を前提にする。

---

## 8. やらないこと

- **自動要約・自動統合**(knowledge-digest)は本設計に含めない。`index.md` の見出しは人が読める粒度で十分で、重複統合はフェーズ2の別タスク
- **ベクトル検索・埋め込み**は入れない。件数が3桁になるまで文字列一致で足り、埋め込みはクラウド依存を呼び込む(差別化軸)
- **セッション層**は置かない(§2)
- **`status` の昇格経路**(`unverified` → `human-reviewed`)は作らない(§4.1)

# フェーズ2 Skill構成と移植性

索引: [medo-phase2-design.md](medo-phase2-design.md)

**どのAgentでもmedoを動かせる状態**を担保するための設計。オーケストレータおよび実行主体のAgent(Claude Code / Codex / agy)とモデルは変わりうる前提で組む。

---

## 1. サブエージェント化は採らない

コンポーネントをサブエージェントに分割する案は**採用しない**。

| 理由 | 内容 |
|---|---|
| **移植性を壊す** | Claude Codeの `Task` / subagent に相当する機構が Codex・agy には同じ形で存在しない。サブエージェント前提にすると、その機構を持たないホストでmedoが動かなくなる |
| **差別化軸に反する** | product.md は「自律的なmulti-agent(非決定性が増える)」をやらない、「会話Agent(1体)+決定論的ツール群」をやる、と定めている |
| **不要である** | 後述のとおり Skill + CLI だけで「モデルを変えて実行する」は実現できる |

これは `multi-agent-portability-design.md` の「対象外(やらない)」に既に明記されている方針(「Claude Code以外のホストへの `Task` 的なサブエージェント機構の移植」)の踏襲である。

**Skill化は採る**。3ホストとも同一の `<name>/SKILL.md` 形式(YAML frontmatter + 本文)をネイティブサポートしており、これが唯一の移植可能な単位である。Agent Skills はオープン仕様として公開され、多数のツールが同一のディレクトリ構造を読む([agentskills.io](https://agentskills.io/specification))。

---

## 2. どのAgentでも動かすための4条件

Skillの分割方法よりも、**次の4条件**が移植性を決める。

### 条件1: 状態はすべてCLIに置く

案件の内容も進行記録も `MEDO_HOME` 配下のストアにある。ホストのコンテキストやメモリには何も残さない。

**帰結**: ステージごとに違うホストで実行してよい。調査はagy(検索が強い)、AsIs整理はClaude、レビューはCodex、という使い分けが成立する。途中でモデルが変わっても続行できる。

### 条件2: どのSkillも `medo status` から現在地を読んで単独で開始できる

前のSkillの実行を前提にしない。開始時に `status` を読み、そこから何をすべきかを決める。

**帰結**: 実行順序の記憶がホスト側に不要になる。セッションが切れても、別のホストに移っても、`status` を読めば再開できる。

### 条件3: Skill間の受け渡しはCLI経由のみ

Skill Aの出力をSkill Bがコンテキスト越しに受け取る、という設計にしない。すべて `artifacts save` / `requirements save` / イベント記録を経由する。

**帰結**: Skillの実行が独立し、順序の入れ替えや再実行が安全になる。

### 条件4: Skill本文を薄く保ち、判断材料はCLIが返す

**これが最も重要である**。設計の詳細ルールをSkill本文に書き込むと、Skillが肥大化して**モデルが変わったときの遵守率が落ちる**(4項目以上の行動規範は遵守率が落ちるとの報告がある)。

したがって:

- Skillには**手順**だけを書く(何を、どの順で、どのCLIで)
- **何が足りないか・次に何をすべきか**は `medo status` が返す(`readiness.failed_conditions` の理由コード、`actions`)
- 判定ロジック・検証・整合性チェックはすべてCLI側に置く

**帰結**: Skill本文が短く保たれ、モデルの能力差に左右されにくくなる。同時に、設計原則「数値・事実の通り道にLLMを挟まない」とも一致する。

---

## 3. Skill構成

標準周回の4ステージに対応させる。

| Skill | ステージ | 主に呼ぶCLI |
|---|---|---|
| `medo-investigate` | 1. 調べる・仕立てる | `facts save` / `requirements save` / `artifacts save --type research,as-is-report` |
| `medo-review` | 2. 内部検証 | `medo review add` |
| `medo-dialogue` | 3. ぶつける・反応を得る | `artifacts save --type slides` / `medo respond add` |
| `medo-decide` | 4. 振り返る・次へ進む | `requirements save` / `medo checkpoint answer` / `status` |

合意形成後の工程は既存Skillを維持する:

| Skill | 用途 |
|---|---|
| `medo-propose-options` | 打ち手候補のミニPRFAQ候補セット化 |
| `medo-grow-prfaq` | 合意案を完全版PRFAQへ育成 |

計6本。フェーズ1の `medo-hearing` は `medo-investigate` に統合する(ヒアリングは調べる・仕立てるステージの一部)。

**Skillを増やしすぎない理由**: Skillの選択は `description` frontmatter のマッチングで行われる。似た説明のSkillが並ぶと、モデルによって選択がブレる。ステージ単位が識別しやすい粒度である。

---

## 4. 各Skillの共通契約

全Skillが守る契約。**3項目に絞る**(4項目以上は遵守率が落ちる)。

1. **開始時と終了時に `medo status --view summary` を実行し、現在地と次の行動をユーザーに報告する**
2. **CLIが失敗したら推測で補完せず、エラー内容をそのまま報告する**
3. **stale・未確認・仮説の項目を引用するときは、その旨を明記する**

数値・出典・鮮度に関する詳細ルールはCLIが検証・返却するため、Skill本文には書かない。

---

## 5. レビューはサブエージェントなしで実現する

ステージ2の内部レビューは、**「別のホストで同じSkillを実行してもよい」という運用**にする。

- ユーザーがagyで調査し、Claudeで整理し、Codexでレビューする、という使い分けが可能
- サブエージェント機構は一切不要。状態がCLIにあるため、どのホストからでも同じ対象をレビューできる
- 誰が実行したかは生成物の `generated_by` と、レビューイベントの記録で追跡できる

**これは制約ではなく強みになる**。同じ状態に対してモデルを変えて実行し、結果を比較できる(フェーズ1の `generated_by` 比較の延長)。

---

## 6. 配布

3ホスト共通のSKILL.md形式をビルドし、各ホストの配置先へコピーする。

```bash
python skills/build.py
mkdir -p ~/.claude/skills ~/.codex/skills .agents/skills
cp -r skills/dist/* ~/.claude/skills/   # Claude Code(ユーザーレベル)
cp -r skills/dist/* ~/.codex/skills/    # Codex CLI(ユーザーレベル)
cp -r skills/dist/* .agents/skills/     # agy(プロジェクトレベル・自動検出)
```

**ホスト固有の機能に依存しない**。Skill本文で使ってよいのは、3ホストすべてが持つ能力(ファイル読み書き・シェル実行・Web検索)に限る。バンドルした参照ファイルの読み込み挙動はホストごとに差がありうるため、**Skillは単一の `SKILL.md` で自己完結させる**(詳細はCLIが返す。条件4)。

---

## 7. 最小構成で使い始められること

**全部を揃えないと動かない設計にしない**。

初めて使う場合、`medo-investigate` だけで開始できる:

1. `facts save` で調べたことを出典付きで保存する
2. `requirements save` で現状(`as_is`)と生の声を記録する
3. `medo status` が次に何を確認すべきかを返す

レビュー・反応記録・チェックポイントは、往復が始まってから必要になる。探索の初期段階では収束に関する診断を出さない([status契約](phase2-status-contract.md) の段階的開示)。

# マルチエージェント移植性 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Claude Code・Codex・agyのいずれか単体でもIssue→PR→マージのサイクルを一人称で回せるよう`workflow.md`に「エージェント可用性プロファイル」を追加し、Skill配布を3ホスト共通の単一`SKILL.md`形式に統一する。

**Architecture:** `workflow.md`の既存担当表(全員揃う場合)はそのまま維持し、その直後に利用可能エージェント別のプロファイル表を追加する。Skillは`skills/src/`を「1フォルダ=1 Skill(`<name>/SKILL.md`)」に再構成し、`build.py`はホスト別変換をやめて単純コピー+frontmatter検証のみを行う。

**Tech Stack:** Python 3.12 / pytest / 既存の`skills/build.py`(argparse・re・pathlib のみ、追加依存なし)

## Global Constraints

- ドキュメントのみの変更(Task1・2・5)はコード変更を伴わないため`uv run pytest`は既存分がパスすることのみ確認する
- コード変更(Task3・4)は `uv run pytest skills/tests/test_build.py -v` → 全体 `uv run pytest` → `uv run ruff check .` の順で確認する
- 正本 `docs/superpowers/specs/multi-agent-portability-design.md` の記述と矛盾する実装をしない
- コミットメッセージは日本語Conventional Commits(`.claude/steering/git.md`)

---

### Task 1: workflow.mdにエージェント可用性プロファイルを追加

**Files:**
- Modify: `.claude/steering/workflow.md`(Section 3内、担当表と「変更できない不変条件」の間、および不変条件本文)

**Interfaces:** なし(ドキュメントのみ)

- [ ] **Step 1: 担当表の直後にプロファイル表を挿入**

`.claude/steering/workflow.md` で以下の行:

```
| スライド・図表などの資料生成 | **agy(antigravity)** | Gemini系が得意な傾向のある資料生成(Google Slides・図表等)。Skillの「Geminiホスト」としての実行・eval(`generated_by`比較)を含む |

**変更できない不変条件**(担当表の編集では変えられない):
```

を、次のように置き換える(表の下に新セクションを挿入し、不変条件の前置きを一部修正):

```
| スライド・図表などの資料生成 | **agy(antigravity)** | Gemini系が得意な傾向のある資料生成(Google Slides・図表等)。Skillの「Geminiホスト」としての実行・eval(`generated_by`比較)を含む |

### エージェント可用性プロファイル

上記の担当表は「Claude Code・Codex・agyが全員揃っている」場合の分担である。実際にはClaude Codeが使えずCodex単体・agy単体で作業する環境もあるため、利用可能なエージェントの組み合わせ別に、統制者(オーケストレーター)・実装・レビューの担い方を以下に定める。

| プロファイル | オーケストレータ | 実装・テスト | レビュー | 備考 |
|---|---|---|---|---|
| 全員揃う(既定) | Claude | Codex(+agyは調査/資料) | Claude作→Codex+agy / Codex,agy作→Claude(相互レビュー) | 上記の担当表通り |
| Codex単体 | Codex | Codex | Codex自己レビュー | `git.md` Section1の手順をCodexが単独で実行する |
| agy単体 | agy | agy | agy自己レビュー | 同上 |
| Claude単体 | Claude | Claude | Claude自己レビュー | 同上 |

**単体プロファイルでの相互レビュー原則の扱い**: 「作ったモデル≠レビューするモデル」は物理的に満たせないため、単体環境では自己レビューに緩和する。コミット本文の `review:` 行は `review: self 1R`(または相当)の形式で、単体実行であった旨を記録する。

**変わらないもの**: `git.md` Section1 step7の重要度判定(スキーマ/契約変更・GCP課金変更・重大指摘未解決の場合は人間レビューを依頼する基準)は、どのプロファイルでも同一に適用する。プロファイルが変わるのは「誰が計画・実装・レビューを担うか」であり、「人間レビューが必要かどうかの判定基準」ではない。

**プロファイルの決定方法**: 各セッション開始時、当該ツール(Claude Code / Codex CLI / agy)は自分がどのプロファイルに該当するかを、利用可能な他ツールの有無(MCP接続・CLI呼び出し可否)から自己判断する。判断に迷う場合はユーザーに確認する。

**変更できない不変条件**(担当表の編集では変えられない):
```

- [ ] **Step 2: 不変条件1の文言をプロファイル前提に修正**

同ファイルの以下の行:

```
1. 最終判断・検証・マージ・コミットの統制は常にClaude(オーケストレーター)— このため担当表の「計画・設計・判断」行はClaude以外に変更できない
```

を次に置き換える:

```
1. 「全員揃う」プロファイルでの最終判断・検証・マージ・コミットの統制は常にClaude(オーケストレーター)— このため担当表の「計画・設計・判断」行はClaude以外に変更できない。単体プロファイルでは、当該プロファイルのオーケストレータ(上表参照)が同じ責務を担う
```

- [ ] **Step 3: 変更内容を目視確認**

Run: `grep -n "エージェント可用性プロファイル\|単体プロファイル" .claude/steering/workflow.md`
Expected: 追加した見出し・文言がヒットする(3箇所以上)

- [ ] **Step 4: コミット**

```bash
git add .claude/steering/workflow.md
git commit -m "docs(steering): エージェント可用性プロファイルを追加

Claude Codeが使えない環境でもCodex/agy単体でIssue→PR→マージの
サイクルを回せるようにする設計(multi-agent-portability-design.md)を
反映した。既存の「全員揃う」場合の担当表は変更していない。"
```

---

### Task 2: CLAUDE.md/AGENTS.mdの同期

**Files:**
- Modify: `CLAUDE.md`(絶対に守ることSection、項目5)
- Modify: `AGENTS.md`(冒頭説明文・絶対に守ることSection項目1/5・Medo Skillsセクション)

**Interfaces:** なし(ドキュメントのみ)

- [ ] **Step 1: CLAUDE.mdの項目5をプロファイル前提の文言に修正**

`CLAUDE.md`の以下の行:

```
5. 実行主体はClaudeが統制する: **担当は workflow.md Section 3 の担当表(唯一の定義箇所)に従う**(担当表の更新で変更可能。最終判断・検証・コミットが常にClaudeであることは不変)。中間生成物は相互レビュー(作成モデル≠レビューモデル、上限2ラウンド)を通す
```

を次に置き換える:

```
5. 実行主体は workflow.md Section 3 の担当表・エージェント可用性プロファイル(唯一の定義箇所)に従う(担当表の更新で変更可能。「全員揃う」プロファイルでは最終判断・検証・コミットは常にClaude、単体プロファイルではそのプロファイルのオーケストレータが担う)。中間生成物は相互レビュー(作成モデル≠レビューモデル、上限2ラウンド。単体プロファイルでは自己レビューに緩和)を通す
```

- [ ] **Step 2: AGENTS.mdの冒頭説明文をクラウド非依存表記に更新**

`AGENTS.md`の以下の行:

```
アイデアから「目処が立つ」までを最速にする、Google Cloud上流工程Agentケイパビリティ(Agent + Skill + CLI)。発想は自由に、事実は縛る。
```

を次に置き換える:

```
アイデアから「目処が立つ」までを最速にする、クラウド非依存の上流工程Agentケイパビリティ(Agent + Skill + CLI)。発想は自由に、事実は縛る。実装手段としてGCPを選ぶ案件が多い想定。
```

- [ ] **Step 3: AGENTS.mdのMedo Skillsセクションを単一形式の案内に統一**

`AGENTS.md`の以下のブロック:

```
## Medo Skills(フェーズ1 Task 9 のビルド後に有効)

- 課題・方針の構造化: `skills/dist/agy/medo-hearing.md` の手順に従う
- 打ち手候補の提案: `skills/dist/agy/medo-propose-options.md` の手順に従う
- PRFAQ育成: `skills/dist/agy/medo-grow-prfaq.md` の手順に従う
```

を次に置き換える:

```
## Medo Skills(フェーズ1 Task 9 のビルド後に有効)

`python skills/build.py` を実行後、自ホストの配置先にコピーすると利用可能になる(`tech.md` セクション6のコマンド例参照)。agyはプロジェクトルート直下の `.agents/skills/` を自動検出するため、`cp -r skills/dist/* .agents/skills/` を実行すればよい。

- 課題・方針の構造化: `medo-hearing` Skillの手順に従う
- 打ち手候補の提案: `medo-propose-options` Skillの手順に従う
- PRFAQ育成: `medo-grow-prfaq` Skillの手順に従う
```

- [ ] **Step 4: AGENTS.mdの絶対に守ること項目1・5を更新**

`AGENTS.md`の以下の行:

```
1. 数値・launch_stage・鮮度の通り道にLLMを挟まない(事実はカタログ値・CLI出力のみ)
```

を次に置き換える:

```
1. 数値・鮮度・技術ナレッジの通り道にLLMを挟まない(事実はfacts/knowledge・CLI出力のみ)
```

続けて以下の行:

```
5. 実行主体はClaudeが統制する: **担当は workflow.md Section 3 の担当表(唯一の定義箇所)に従う**(担当表の更新で変更可能。最終判断・検証・コミットが常にClaudeであることは不変)。中間生成物は相互レビュー(作成モデル≠レビューモデル、上限2ラウンド)を通す
```

を、Task2 Step1でCLAUDE.mdに書いたのと同じ文言に置き換える:

```
5. 実行主体は workflow.md Section 3 の担当表・エージェント可用性プロファイル(唯一の定義箇所)に従う(担当表の更新で変更可能。「全員揃う」プロファイルでは最終判断・検証・コミットは常にClaude、単体プロファイルではそのプロファイルのオーケストレータが担う)。中間生成物は相互レビュー(作成モデル≠レビューモデル、上限2ラウンド。単体プロファイルでは自己レビューに緩和)を通す
```

- [ ] **Step 5: 変更内容を目視確認**

Run: `grep -n "Google Cloud\|launch_stage" AGENTS.md`
Expected: 該当なし(0件)

- [ ] **Step 6: コミット**

```bash
git add CLAUDE.md AGENTS.md
git commit -m "docs: CLAUDE.md/AGENTS.mdをエージェント可用性プロファイルとクラウド非依存表記に同期

AGENTS.mdがGoogle Cloud専用・launch_stage前提の古い記述のまま
残っており、CLAUDE.mdとの内容乖離があった。あわせて実行主体の
不変条件をエージェント可用性プロファイル前提の文言に更新した。"
```

---

### Task 3: skills/src をフォルダ構成(`<name>/SKILL.md`)に再構成

**Files:**
- Move: `skills/src/hearing.md` → `skills/src/medo-hearing/SKILL.md`
- Move: `skills/src/propose-options.md` → `skills/src/medo-propose-options/SKILL.md`
- Move: `skills/src/grow-prfaq.md` → `skills/src/medo-grow-prfaq/SKILL.md`

**Interfaces:**
- Produces: `skills/src/<name>/SKILL.md`(Task4のbuild.pyが読む新しいソース構成)

- [ ] **Step 1: git mvで移動**

```bash
mkdir -p skills/src/medo-hearing skills/src/medo-propose-options skills/src/medo-grow-prfaq
git mv skills/src/hearing.md skills/src/medo-hearing/SKILL.md
git mv skills/src/propose-options.md skills/src/medo-propose-options/SKILL.md
git mv skills/src/grow-prfaq.md skills/src/medo-grow-prfaq/SKILL.md
```

- [ ] **Step 2: 中身が壊れていないことを確認**

Run: `head -5 skills/src/medo-hearing/SKILL.md`
Expected: `---` で始まるfrontmatterがそのまま表示される(内容変更なし)

- [ ] **Step 3: コミット**

```bash
git commit -m "refactor(skills): skills/srcを1フォルダ=1 Skill構成に変更

3ホスト(Claude Code/Codex/agy)が同一のSKILL.md形式(frontmatter付き
フォルダ)をネイティブサポートしていることが判明したため、変換不要な
配布に単純化する準備としてソース構成をフォルダ形式に揃えた。"
```

---

### Task 4: skills/build.pyを単一形式生成に簡素化

**Files:**
- Modify: `skills/build.py`
- Modify: `skills/tests/test_build.py`

**Interfaces:**
- Consumes: `skills/src/<name>/SKILL.md`(Task3で作成したフォルダ構成)
- Produces: `build(out: Path) -> None`(`skills/dist/<name>/SKILL.md` に検証済みコピーを出力)

- [ ] **Step 1: 新しいテストを書く(既存テストを置き換え)**

`skills/tests/test_build.py` を次の内容に全面置換する:

```python
import subprocess
import sys
from pathlib import Path

SKILLS_DIR = Path(__file__).parent.parent

SKILL_NAMES = ["medo-hearing", "medo-propose-options", "medo-grow-prfaq"]


def test_build_generates_skill_md_per_name(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SKILLS_DIR / "build.py"), "--out", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    for name in SKILL_NAMES:
        skill_md = tmp_path / name / "SKILL.md"
        assert skill_md.exists(), name
        text = skill_md.read_text(encoding="utf-8")
        assert text.startswith("---")
        assert f"name: {name}" in text
        assert "description:" in text

    hearing = (tmp_path / "medo-hearing" / "SKILL.md").read_text(encoding="utf-8")
    assert "medo requirements save" in hearing


def test_build_rejects_missing_frontmatter(tmp_path):
    src = tmp_path / "src"
    (src / "broken").mkdir(parents=True)
    (src / "broken" / "SKILL.md").write_text("no frontmatter here", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SKILLS_DIR / "build.py"), "--src", str(src), "--out", str(tmp_path / "out")],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "frontmatter" in (result.stdout + result.stderr)
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run pytest skills/tests/test_build.py -v`
Expected: FAIL(現行の`build.py`は`--src`引数を受け付けず、`dist/<name>/SKILL.md`ではなく`dist/claude/<name>/SKILL.md`に出力するため、両テストとも失敗する)

- [ ] **Step 3: build.pyを簡素化して実装**

`skills/build.py` を次の内容に全面置換する:

```python
"""Skill共通md(1フォルダ=1 Skill)をdist/へ検証付きでコピーする。"""

import argparse
import re
from pathlib import Path
from shutil import copyfile

SRC = Path(__file__).parent / "src"


def validate(src_text: str, name: str) -> None:
    """frontmatterの必須項目(name/description)を検証する。"""
    m = re.match(r"^---\n(.*?)\n---\n", src_text, re.DOTALL)
    if not m:
        raise ValueError(f"{name}: frontmatter(---区切り)がありません")
    fm = m.group(1)
    if not re.search(r"^name:\s*\S+", fm, re.MULTILINE):
        raise ValueError(f"{name}: frontmatterにnameがありません")
    if not re.search(r"^description:", fm, re.MULTILINE):
        raise ValueError(f"{name}: frontmatterにdescriptionがありません")


def build(src: Path, out: Path) -> None:
    for skill_dir in sorted(p for p in src.iterdir() if p.is_dir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        text = skill_md.read_text(encoding="utf-8")
        validate(text, skill_dir.name)

        dest_dir = out / skill_dir.name
        dest_dir.mkdir(parents=True, exist_ok=True)
        copyfile(skill_md, dest_dir / "SKILL.md")
    print(f"built skills into {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", type=Path, default=SRC)
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "dist")
    args = parser.parse_args()
    build(args.src, args.out)
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run pytest skills/tests/test_build.py -v`
Expected: PASS(2 passed)

- [ ] **Step 5: distを生成して目視確認**

Run: `python skills/build.py && find skills/dist -type f`
Expected: `skills/dist/medo-hearing/SKILL.md`・`skills/dist/medo-propose-options/SKILL.md`・`skills/dist/medo-grow-prfaq/SKILL.md` の3ファイルのみ

- [ ] **Step 6: 全体テストとリントを確認**

Run: `uv run pytest -q && uv run ruff check .`
Expected: 全パッケージPASS、リント違反なし

- [ ] **Step 7: コミット**

```bash
git add skills/build.py skills/tests/test_build.py
git commit -m "refactor(skills): build.pyをホスト別変換なしの単一形式生成に簡素化

Claude Code/Codex/agyが同一のSKILL.md形式をネイティブサポートする
ため、agy向けのfrontmatter除去・ホスト別ディレクトリ分岐が不要に
なった。frontmatter必須項目(name/description)の検証は維持する。"
```

---

### Task 5: 配布コマンド例・ディレクトリ構成説明・.gitignoreの同期

**Files:**
- Modify: `.claude/steering/tech.md`(Skillビルドと配布のコマンド例)
- Modify: `.claude/steering/structure.md`(Section 4 `skills/`ディレクトリ構成図)
- Modify: `.gitignore`

**Interfaces:** なし(ドキュメント・設定のみ)

- [ ] **Step 1: tech.mdのコマンド例を3ホスト分に更新**

`.claude/steering/tech.md` の以下の行:

```
# Skillビルドと配布
python skills/build.py
cp -r skills/dist/claude/* ~/.claude/skills/     # Claude Code
# agy: skills/dist/agy/*.md をAGENTS.mdから参照
```

を次に置き換える:

```
# Skillビルドと配布(3ホスト共通のSKILL.md形式)
python skills/build.py
cp -r skills/dist/* ~/.claude/skills/   # Claude Code(ユーザーレベル)
cp -r skills/dist/* ~/.codex/skills/    # Codex CLI(ユーザーレベル)
cp -r skills/dist/* .agents/skills/     # agy(プロジェクトレベル。リポジトリ直下から自動検出)
```

- [ ] **Step 2: structure.mdのskills/ディレクトリ構成図を更新**

`.claude/steering/structure.md` の以下のブロック:

```
skills/
├── src/                 # 共通md(frontmatter付き)。1ファイル=1 Skill
│   ├── hearing.md            # 業界・ビジネス状況・課題・経営思想/方針の構造化
│   ├── propose-options.md    # 市場ファクト+フェルミ+技術ナリッジ根拠→打ち手候補のミニPRFAQ候補セット化
│   └── grow-prfaq.md         # 合意案を完全版PRFAQへ育成(技術ナリッジ根拠)
├── build.py             # dist/claude/<name>/SKILL.md と dist/agy/<name>.md を生成
├── tests/
└── dist/                # ビルド出力(.gitignored)
```

を次に置き換える:

```
skills/
├── src/                       # 共通Skill(frontmatter付き)。1フォルダ=1 Skill
│   ├── medo-hearing/SKILL.md            # 業界・ビジネス状況・課題・経営思想/方針の構造化
│   ├── medo-propose-options/SKILL.md    # 市場ファクト+フェルミ+技術ナリッジ根拠→打ち手候補のミニPRFAQ候補セット化
│   └── medo-grow-prfaq/SKILL.md         # 合意案を完全版PRFAQへ育成(技術ナリッジ根拠)
├── build.py             # dist/<name>/SKILL.md を生成(3ホスト共通形式・変換なし)
├── tests/
└── dist/                # ビルド出力(.gitignored)
```

続けて同ファイルの以下の行:

```
- Skill本文は `src/` の1箇所で管理し、ホスト形式へは `build.py` の薄い変換のみ
- Claude Code へは `~/.claude/skills/` にコピー、agy へは `dist/agy/*.md` をAGENTS.mdから参照
```

を次に置き換える:

```
- Skill本文は `src/<name>/SKILL.md` の1箇所で管理し、`build.py` はfrontmatter検証付きコピーのみ行う(ホスト別変換は不要。3ホストとも同一のSKILL.md形式をネイティブサポートするため)
- 配布先: Claude Codeは `~/.claude/skills/`、Codexは `~/.codex/skills/`(いずれもユーザーレベル、コピーが必要)。agyはプロジェクトルート直下の `.agents/skills/` を自動検出する(プロジェクトレベル)
```

- [ ] **Step 3: .gitignoreに.agents/skills/を追加**

`.gitignore` の `skills/dist/` の行の直後に以下を追加する:

```
.agents/skills/
```

- [ ] **Step 4: 変更内容を確認**

Run: `grep -n "cp -r skills/dist" .claude/steering/tech.md && grep -n "medo-hearing/SKILL.md" .claude/steering/structure.md && grep -n ".agents/skills" .gitignore`
Expected: いずれもヒットする

- [ ] **Step 5: コミット**

```bash
git add .claude/steering/tech.md .claude/steering/structure.md .gitignore
git commit -m "docs(steering): Skill配布コマンド・ディレクトリ構成をSKILL.md統一形式に同期

build.pyの出力形式変更(Task4)に合わせ、配布コマンド例と
skills/ディレクトリ構成の説明を実装と一致させた。"
```

---

## Self-Review Notes

- **Spec coverage**: design doc(`multi-agent-portability-design.md`)のスコープ1-4を Task1(プロファイル表)・Task2(AGENTS.md同期)・Task3+4(Skill配布形式統一)・Task5(配置先コマンド・structure.md・.gitignore)で網羅。design doc「影響範囲」節の4項目(skills/srcリネーム・.gitignore・medo-phase1.md追記・structure.md同期)のうちTask1-5で3つを実施。`medo-phase1.md`への軽微な追記は本計画のスコープ外(design doc影響範囲に「軽微」と明記されており、別途Issueなしの臨時ドキュメント修正として扱ってよい)
- **型整合**: Task4で定義した`build(src: Path, out: Path) -> None`のシグネチャは他Taskから参照されない(build.py内で完結)
- **依存順序**: Task3(ファイル移動)がTask4(build.py実装)より先。Task1・2・5は独立で並び替え可能だが、レビューのしやすさのため設計doc記載順とした

# Medo(目処) — Agent向けエントリポイント

アイデアから「目処が立つ」までを最速にする、クラウド非依存の上流工程Agentケイパビリティ(Agent + Skill + CLI)。発想は自由に、事実は縛る。

## まず読む

**`docs/agent-guide.md` を開くこと。** ホスト共通のAgent向けガイドで、現在地・参照先・絶対に守ることはすべてそこにある。本ファイルは各ホストが自動で読む場所であり、内容を持たない。

最低限、着手前に次を読む:

- `docs/agent-guide.md` — 入口(可用性プロファイルの判断を含む)
- `.claude/steering/product.md` / `tech.md` / `structure.md` — 常時参照する規約
- `.claude/steering/workflow.md` — タスク着手前。**担当分担の唯一の定義箇所**

`.claude/` というディレクトリ名だが、中身はホスト非依存の規約である。Claude Code 以外のホスト(Codex / agy 等)もこのパスを読む。

規約を足すときは `docs/agent-guide.md` だけを直す。本ファイルに書き写さない(CLAUDE.md とずれる)。

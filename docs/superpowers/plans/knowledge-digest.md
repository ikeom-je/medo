# knowledge-digest とナレッジ来歴 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 案件横断ナレッジの重複を、Jevの段階的な分類で絞り込み、人の承認後に `supersede` で置き換えて来歴を残す。置き換えられた引用先を持つ生成物は stale にして終端の後継を案内する。

**Architecture:** core は決定論だけを持つ(来歴スキーマ・検査・候補の組の生成・振り分け・影響の列挙)。Jev の呼び出しと出典の取得は cli のアダプタに置き、core の振り分け関数は Jev の判定結果を受け取る純関数とする。Skill `medo-knowledge-digest` が dedupe → 人の承認 → supersede の手順を持つ。

**Tech Stack:** Python 3.12 / pydantic 2 / typer / pytest / ruff / TypeSafe System One(Jev)/ 既存の `cli/src/medo_cli/fetch.py` と `core/src/medo_core/source_check.py`

**Spec:** `docs/superpowers/specs/phase2-knowledge-digest.md`(承認済み)

## Global Constraints

- 新しい文は生成しない。統合は既存エントリのどちらかを残す(spec §3)
- 数値の一致はCLIが判定し、Jevには判定させない。`retrieved` は新旧の判断に使わない(spec §3.1)
- 閾値 T の出発点は 0.8。聞き直しは relation の確信度 ≥ 0.5 のときに1組1回まで。根拠の取得に失敗した組は聞き直さず held(spec §3.2・§3.3)
- `conflicting` は確信度に関係なく conflicts。同じ塊に conflicts がある proposals はすべて held(spec §3.2・§3.4)
- 来歴は旧エントリの `superseded_by` / `supersede_reason` / `superseded_on` のみ。3フィールドはすべて空かすべて埋まる(spec §4)
- 通常の `KnowledgeStore.save` は既存IDの上書きを拒否する。来歴を変えられるのは `supersede` だけ(spec §4.1)
- 生成物の引用IDは書き換えない。置き換え済みの引用先は stale(理由に終端の後継)(spec §5)
- Jev: `TYPESAFE_API_KEY` 無し → `judge: unavailable`(終了0)、鍵ありで失敗 → 非ゼロ終了(spec §6.2)
- core は Jev・ネットワークを呼ばない(structure.md の依存方向)
- コードコメントは Why not のみ。CLI失敗は非ゼロ終了+`error: <理由>`
- Codex への委譲は `codex exec -m gpt-6.1-sol -c model_reasoning_effort=high ... </dev/null`(workflow.md)。テストと ruff の最終確認は Claude の環境で行う

## Review Focus

1. **置き換え済みエントリの再保存**: `knowledge save` に既存IDを渡す経路(現在のCLIは entry_id を受けないが、core の save は受ける)で来歴が消えないこと → Task 2 のテスト `test_save_refuses_existing_id`
2. **置き換えの連鎖の途中を引用している生成物**: A→B→C で A を引用している生成物の理由に、B ではなく C が出ること → Task 3 のテスト `test_citation_reason_names_terminal_successor`
3. **壊れた来歴を持つファイル**(手編集で `superseded_by` だけ書かれた等): 読み込みは止めず、`knowledge index` が警告を返すこと → Task 2 のテスト `test_index_warns_on_broken_provenance`
4. **値を持たないエントリ同士の重複**(定性ファクト): 数値の一致検査を飛ばして proposals に進めること、片方だけ値を持つ組は proposals にしないこと → Task 4 のテスト `test_route_duplicate_without_values` / `test_route_rejects_duplicate_with_one_sided_value`
5. **案件が1つも無い MEDO_HOME で supersede**: 影響する生成物の列挙が空で正常終了すること → Task 6 のテスト `test_supersede_with_no_projects`

---

## File Structure

| ファイル | 責務 |
|---|---|
| `core/src/medo_core/storage.py`(変更) | `list_children` を Protocol と2実装に足す |
| `core/src/medo_core/knowledge.py`(変更) | 来歴フィールド、読み込み時の検査、save の上書き拒否、`supersede`、終端の解決、検索・索引からの除外 |
| `core/src/medo_core/context.py`(変更) | `CitationIssue`、引用の判定に「置き換え」を足す |
| `core/src/medo_core/artifacts.py`(変更) | freshness の理由文を `CitationIssue` の表示に合わせる(文字列の引用IDも引き続き受ける) |
| `core/src/medo_core/knowledge_dedupe.py`(新規) | 候補の組の生成、振り分け、案どうしの検査、影響する生成物の列挙(すべて純関数か Storage 読み取りのみ) |
| `cli/src/medo_cli/jev.py`(変更) | `judge_pairs` |
| `cli/src/medo_cli/main.py`(変更) | `knowledge dedupe` / `knowledge supersede` / `--include-superseded` |
| `scripts/eval/dedupe_cases.json` / `run_dedupe_eval.py`(新規) | 評価セット(調整用・検証用)と評価 |
| `skills/src/medo-knowledge-digest/SKILL.md`(新規) | 手順 |
| `skills/tests/test_build.py`(変更) | 新Skillを一覧に足す |
| `.claude/steering/tech.md` / `structure.md`(変更) | digest のLLM方針と配置の同期 |

---

## Part A: core

### Task 1: Storage.list_children

**Files:**
- Modify: `core/src/medo_core/storage.py`
- Test: `core/tests/test_storage.py`

**Interfaces:**
- Produces: `Storage.list_children(prefix: str) -> list[str]` — 直下の子の名前(パスではなく名前)を昇順で返す。子がJSONファイルでもディレクトリでもよい

- [ ] **Step 1: Write the failing test**

```python
def test_list_children_returns_project_dirs_without_json(tmp_path):
    storage = LocalJsonStorage(tmp_path)
    storage.put("projects/p1/facts/fact-1", {"x": 1})
    storage.put("projects/p2/requirements/v1", {"x": 1})

    assert storage.list("projects") == []          # 既存の list は直下のJSONだけ
    assert storage.list_children("projects") == ["p1", "p2"]


def test_list_children_of_missing_prefix_is_empty(tmp_path):
    assert LocalJsonStorage(tmp_path).list_children("projects") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest core/tests/test_storage.py -k list_children -v`
Expected: FAIL with `AttributeError: 'LocalJsonStorage' object has no attribute 'list_children'`

- [ ] **Step 3: Write minimal implementation**

```python
class Storage(Protocol):
    def get(self, path: str) -> dict | None: ...
    def put(self, path: str, doc: dict) -> None: ...
    def list(self, prefix: str) -> list[str]: ...
    def list_children(self, prefix: str) -> list[str]: ...

# LocalJsonStorage
    def list_children(self, prefix: str) -> list[str]:
        d = self._root / prefix
        if not d.is_dir():
            return []
        names = {p.stem if p.suffix == ".json" else p.name for p in d.iterdir()}
        return sorted(names)

# FirestoreStorage
    def list_children(self, prefix: str) -> list[str]:
        # list_documents は実体の無い親ドキュメント(サブコレクションだけを持つ)も返す
        return sorted(ref.id for ref in self._client.collection(prefix).list_documents())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest core/tests/test_storage.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/src/medo_core/storage.py core/tests/test_storage.py
git commit -m "feat(core): 案件を列挙できる Storage.list_children"
```

### Task 2: 来歴スキーマ・save の上書き拒否・supersede・検索と索引からの除外

**Files:**
- Modify: `core/src/medo_core/knowledge.py`
- Test: `core/tests/test_knowledge.py`

**Interfaces:**
- Consumes: なし
- Produces:
  - `KnowledgeEntry.superseded_by: str = ""` / `supersede_reason: Literal["", "duplicate", "updates"] = ""` / `superseded_on: str = ""`
  - `KnowledgeEntry.is_superseded -> bool`(property)
  - `KnowledgeStore.save(entry) -> str` — `entry.entry_id` が既存なら `ValueError("既存のエントリは上書きできません: <id>")`
  - `KnowledgeStore.supersede(kind: str, old_id: str, by_id: str, reason: Literal["duplicate","updates"], today: date | None = None) -> KnowledgeEntry`(更新後の旧エントリを返す)
  - `KnowledgeStore.terminal(kind: str, entry_id: str) -> str` — 連鎖の終端のID。循環・欠落は `ValueError`
  - `KnowledgeStore.search(..., include_superseded: bool = False)` / `index(kind, today=None, include_superseded=False)`
  - `KnowledgeStore.provenance_warnings(kind: str) -> list[str]`
  - `KnowledgeIndex.warnings: list[str] = []`

- [ ] **Step 1: Write the failing tests**

```python
def _entry(**kw):
    base = dict(kind="tech", statement="s", source="https://example.com/a", retrieved="2026-09-01")
    return KnowledgeEntry(**{**base, **kw})


def test_save_refuses_existing_id(tmp_path):
    store = KnowledgeStore(tmp_path)
    entry_id = store.save(_entry())
    with pytest.raises(ValueError, match="上書き"):
        store.save(_entry(entry_id=entry_id, statement="別の文"))


def test_supersede_records_provenance_and_hides_from_search(tmp_path):
    store = KnowledgeStore(tmp_path)
    old = store.save(_entry(statement="旧"))
    new = store.save(_entry(statement="新"))

    updated = store.supersede("tech", old, new, "duplicate", today=date(2026, 10, 4))

    assert (updated.superseded_by, updated.supersede_reason, updated.superseded_on) == (
        new, "duplicate", "2026-10-04")
    assert [e.entry_id for e in store.search("", kind="tech").entries] == [new]
    assert {e.entry_id for e in store.search("", kind="tech", include_superseded=True).entries} == {old, new}
    assert store.index("tech").entry_count == 1
    assert store.get("tech", old).superseded_by == new


@pytest.mark.parametrize("case", ["same", "missing", "kind", "old_done", "new_done"])
def test_supersede_rejects_invalid(tmp_path, case):
    store = KnowledgeStore(tmp_path)
    a = store.save(_entry())
    b = store.save(_entry())
    c = store.save(_entry())
    m = store.save(_entry(kind="market", source="https://example.com/m"))
    if case == "old_done":
        store.supersede("tech", a, b, "duplicate")
    if case == "new_done":
        store.supersede("tech", b, c, "duplicate")
    args = {"same": (a, a), "missing": (a, "tech-99"), "kind": (a, m),
            "old_done": (a, c), "new_done": (a, b)}[case]
    with pytest.raises(ValueError):
        store.supersede("tech", *args, "duplicate")


def test_terminal_follows_chain(tmp_path):
    store = KnowledgeStore(tmp_path)
    a, b, c = (store.save(_entry()) for _ in range(3))
    store.supersede("tech", a, b, "updates")
    store.supersede("tech", b, c, "updates")
    assert store.terminal("tech", a) == c
    assert store.terminal("tech", c) == c


def test_index_warns_on_broken_provenance(tmp_path):
    store = KnowledgeStore(tmp_path)
    a = store.save(_entry())
    path = tmp_path / "tech" / f"{a}.md"
    path.write_text(path.read_text(encoding="utf-8").replace(
        "---\n", "---\nsuperseded_by: tech-99\n", 1), encoding="utf-8")

    index = store.index("tech")
    assert index is not None
    assert any("tech-99" in w for w in index.warnings)


def test_provenance_fields_are_all_or_nothing():
    with pytest.raises(ValueError):
        _entry(superseded_by="tech-2")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest core/tests/test_knowledge.py -k "supersede or terminal or existing_id or provenance" -v`
Expected: FAIL(`superseded_by` 未定義、save が上書きする)

- [ ] **Step 3: Write minimal implementation**

`KnowledgeEntry` に追加:

```python
    superseded_by: str = ""
    supersede_reason: Literal["", "duplicate", "updates"] = ""
    superseded_on: str = ""

    @property
    def is_superseded(self) -> bool:
        return bool(self.superseded_by)
```

`_validate` の末尾に追加:

```python
        provenance = (self.superseded_by, self.supersede_reason, self.superseded_on)
        if any(provenance) and not all(provenance):
            raise ValueError("superseded_by / supersede_reason / superseded_on はすべて指定するか、すべて空にする")
        if self.superseded_on:
            date.fromisoformat(self.superseded_on)
```

読み込み時に来歴が壊れたファイルでも止めないよう、`_entries` / `get` は `_load(path, kind)` を経由し、来歴の3フィールドの検証で失敗したら来歴を空にして読み、警告用に記録する:

```python
    def _load(self, path: Path, kind: str) -> tuple[KnowledgeEntry, str | None]:
        meta = {**_from_okf(_read_frontmatter(path)), "entry_id": path.stem, "kind": kind}
        try:
            return KnowledgeEntry.model_validate(meta), None
        except ValueError as e:
            # 手編集で来歴が壊れても蓄積全体を読めなくしない(索引の _index_meta と同じ判断)
            for key in ("superseded_by", "supersede_reason", "superseded_on"):
                meta.pop(key, None)
            return KnowledgeEntry.model_validate(meta), f"{path.stem}: 来歴が不正です({e})"
```

`save` の先頭(採番の後)に:

```python
        path = self._dir(entry.kind) / f"{entry.entry_id}.md"
        if path.exists():
            raise ValueError(f"既存のエントリは上書きできません: {entry.entry_id}")
```

原子的書き込み(`_write_frontmatter` を置き換え):

```python
def _write_frontmatter(path: Path, meta: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    front = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False)
    tmp = path.with_suffix(".md.tmp")
    tmp.write_text(f"---\n{front}---\n", encoding="utf-8")
    tmp.replace(path)
```

`supersede` / `terminal` / `provenance_warnings`:

```python
    def supersede(self, kind, old_id, by_id, reason, today=None) -> KnowledgeEntry:
        def check() -> KnowledgeEntry:
            if old_id == by_id:
                raise ValueError("旧エントリと後継が同じです")
            old, new = self.get(kind, old_id), self.get(kind, by_id)
            if old is None or new is None:
                raise ValueError(f"エントリが見つかりません: {old_id if old is None else by_id}")
            if old.is_superseded:
                raise ValueError(f"{old_id} は置き換え済みです(→ {old.superseded_by})")
            if new.is_superseded:
                raise ValueError(f"後継 {by_id} 自身が置き換え済みです(→ {new.superseded_by})")
            return old

        check()
        old = check()  # 書き込み直前にやり直す。ロックは入れない(個人利用、spec §4.1)
        updated = old.model_copy(update={
            "superseded_by": by_id, "supersede_reason": reason,
            "superseded_on": (today or date.today()).isoformat(),
        })
        _write_frontmatter(self._dir(kind) / f"{old_id}.md", updated.to_okf())
        self.rebuild_index(kind)
        return updated

    def terminal(self, kind: str, entry_id: str) -> str:
        seen: set[str] = set()
        current = entry_id
        while True:
            if current in seen:
                raise ValueError(f"置き換えが循環しています: {entry_id}")
            seen.add(current)
            entry = self.get(kind, current)
            if entry is None:
                raise ValueError(f"置き換え先が見つかりません: {current}")
            if not entry.is_superseded:
                return current
            current = entry.superseded_by

    def provenance_warnings(self, kind: str) -> list[str]:
        warnings = [w for _, w in self._loaded(kind) if w]
        for entry, _ in self._loaded(kind):
            if entry.is_superseded:
                try:
                    self.terminal(kind, entry.entry_id)
                except ValueError as e:
                    warnings.append(f"{entry.entry_id}: {e}")
        return warnings
```

(`to_okf` は `entry_id` 以外のフィールドをそのまま書くので、来歴の3フィールドは空でも出力される。空のときは `to_okf` で落とす: `meta = {k: v for k, v in meta.items() if not (k in ("superseded_by","supersede_reason","superseded_on") and not v)}`)

`_entries(kind)` は `[e for e, _ in self._loaded(kind)]`、`_loaded(kind)` は各パスに `_load` をかけた一覧。`search` と `index` と `rebuild_index` は `include_superseded=False` のとき `e.is_superseded` を除く。`index` は `warnings=self.provenance_warnings(kind)` を返す。`KnowledgeIndex` に `warnings: list[str] = Field(default_factory=list)` を足す。

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest core/tests/test_knowledge.py -v && uv run pytest -q`
Expected: PASS(既存テストも含めて)

- [ ] **Step 5: Commit**

```bash
git add core/src/medo_core/knowledge.py core/tests/test_knowledge.py
git commit -m "feat(core): ナレッジの置き換えと来歴を記録し、置き換え済みを検索から除く"
```

### Task 3: 引用の判定に「置き換え」を足す

**Files:**
- Modify: `core/src/medo_core/context.py`, `core/src/medo_core/artifacts.py`
- Test: `core/tests/test_context.py`, `core/tests/test_artifacts.py`

**Interfaces:**
- Consumes: `KnowledgeStore.get` / `KnowledgeStore.terminal`(Task 2)
- Produces:
  - `CitationIssue(BaseModel)`: `id: str`, `reason: Literal["missing","stale","superseded"]`, `successor: str = ""`。`__str__` は `missing` / `stale` なら `id`、`superseded` なら `f"{id}(置き換え済み → {successor})"`
  - `make_citation_checker(...)` が返す関数は `list[CitationIssue]` を返す
  - `ArtifactStore.freshness` は `is_citation_stale` の戻り値の各要素を `str()` して理由文に連結する(既存テストの `lambda a, today: list(a.cited_facts)` も動く)

- [ ] **Step 1: Write the failing test**

```python
def test_citation_reason_names_terminal_successor(tmp_path):
    knowledge = KnowledgeStore(tmp_path / "knowledge")
    a, b, c = (knowledge.save(KnowledgeEntry(kind="tech", statement=f"s{i}",
               source="https://example.com", retrieved=date.today().isoformat())) for i in range(3))
    knowledge.supersede("tech", a, b, "updates")
    knowledge.supersede("tech", b, c, "updates")
    storage = LocalJsonStorage(tmp_path / "data")
    checker = make_citation_checker(storage, "p1", knowledge_root=tmp_path / "knowledge")

    issues = checker(_artifact(cited_knowledge=[a]), None)

    assert [(i.id, i.reason, i.successor) for i in issues] == [(a, "superseded", c)]
    assert str(issues[0]) == f"{a}(置き換え済み → {c})"


def test_citation_checker_keeps_missing_and_stale(tmp_path):
    storage = LocalJsonStorage(tmp_path / "data")
    checker = make_citation_checker(storage, "p1", knowledge_root=tmp_path / "knowledge")
    issues = checker(_artifact(cited_facts=["fact-9"], cited_knowledge=["tech-9"]), None)
    assert {(i.id, i.reason) for i in issues} == {("fact-9", "missing"), ("tech-9", "missing")}
```

(`_artifact` は `core/tests/test_context.py` に既存のヘルパーがあればそれを使い、無ければ `Artifact(project="p1", type="research", requirements_version=1, content="x", **kw)` を返すヘルパーを足す)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest core/tests/test_context.py -k citation -v`
Expected: FAIL(戻り値が str の配列)

- [ ] **Step 3: Write minimal implementation**

```python
class CitationIssue(BaseModel):
    id: str
    reason: Literal["missing", "stale", "superseded"]
    successor: str = ""

    def __str__(self) -> str:
        if self.reason == "superseded":
            return f"{self.id}(置き換え済み → {self.successor})"
        return self.id


    def citation_checker(artifact: Artifact, today: date | None) -> list[CitationIssue]:
        issues: list[CitationIssue] = []
        for fact_id in artifact.cited_facts:
            fact = facts.get(project_id, fact_id)
            if fact is None:
                issues.append(CitationIssue(id=fact_id, reason="missing"))
            elif fact.is_stale(today=today):
                issues.append(CitationIssue(id=fact_id, reason="stale"))
        for entry_id in artifact.cited_knowledge:
            if "-" not in entry_id:
                issues.append(CitationIssue(id=entry_id, reason="missing"))
                continue
            kind, _ = entry_id.rsplit("-", 1)
            entry = knowledge.get(kind, entry_id)
            if entry is None:
                issues.append(CitationIssue(id=entry_id, reason="missing"))
            elif entry.is_superseded:
                try:
                    successor = knowledge.terminal(kind, entry_id)
                except ValueError:
                    successor = entry.superseded_by
                issues.append(CitationIssue(id=entry_id, reason="superseded", successor=successor))
            elif entry.is_stale(today=today):
                issues.append(CitationIssue(id=entry_id, reason="stale"))
        return issues
```

`artifacts.py` の `freshness`:

```python
                reasons.append(f"引用が古くなっています: {', '.join(str(c) for c in stale_citations)}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest core/tests -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/src/medo_core/context.py core/src/medo_core/artifacts.py core/tests/test_context.py
git commit -m "feat(core): 置き換えられた引用先を持つ生成物を stale にし、終端の後継を示す"
```

### Task 4: 候補の組・振り分け・案どうしの検査・影響の列挙

**Files:**
- Create: `core/src/medo_core/knowledge_dedupe.py`
- Test: `core/tests/test_knowledge_dedupe.py`

**Interfaces:**
- Consumes: `KnowledgeEntry`(Task 2)、`source_check._without_annotation`(既存)、`Storage.list_children`(Task 1)、`ArtifactStore.freshness` / `make_citation_checker`(既存・Task 3)
- Produces:
  - `candidate_pairs(entries: list[KnowledgeEntry], overlap_threshold: float = 0.35) -> list[tuple[str, str]]`(ID の組、`a < b` の番号順、置き換え済みは除く)
  - `PairJudgment(BaseModel)`: `relation: str`, `relation_confidence: float`, `same_scope: float`, `newer: str`, `newer_confidence: float`, `keep: str`, `keep_confidence: float`
  - `route(a: KnowledgeEntry, b: KnowledgeEntry, j: PairJudgment, threshold: float = 0.8) -> Routing`。`Routing(BaseModel)`: `bucket: Literal["proposal","conflict","excluded","requery","held"]`, `old: str = ""`, `by: str = ""`, `reason: Literal["", "duplicate","updates"] = ""`
  - `check_components(proposals: list[Routing], conflicts: list[tuple[str, str]]) -> tuple[list[Routing], list[Routing]]`(残す proposals、held に落とす proposals)
  - `affected_artifacts(storage: Storage, knowledge_root: Path, kind: str, entry_id: str) -> list[dict]`(`{"project", "artifact", "via"}`、`via` は `"cited"` か親の artifact ID)

- [ ] **Step 1: Write the failing tests**

```python
def _e(i, **kw):
    base = dict(entry_id=f"tech-{i}", kind="tech", statement="s", source=f"https://e.com/{i}",
                retrieved="2026-09-01")
    return KnowledgeEntry(**{**base, **kw})


def _j(relation, rc=0.9, scope=0.9, newer="same", nc=0.9, keep="a", kc=0.9):
    return PairJudgment(relation=relation, relation_confidence=rc, same_scope=scope,
                        newer=newer, newer_confidence=nc, keep=keep, keep_confidence=kc)


def test_candidate_pairs_by_same_url_ignoring_arxiv_abs_pdf():
    a = _e(1, source="https://arxiv.org/abs/2311.17311", statement="USC は精度を上げる")
    b = _e(2, source="https://arxiv.org/pdf/2311.17311", statement="全く別の言い回し")
    c = _e(3, source="https://other.example/x", statement="無関係な話題")
    assert candidate_pairs([a, b, c]) == [("tech-1", "tech-2")]


def test_candidate_pairs_by_char_bigram_overlap():
    a = _e(1, statement="市場規模は2024年に3.2兆円")
    b = _e(2, statement="2024年の市場規模は3.2兆円だった", source="https://x.example/y")
    assert ("tech-1", "tech-2") in candidate_pairs([a, b])


def test_route_conflicting_always_conflict():
    assert route(_e(1), _e(2), _j("conflicting", rc=0.3)).bucket == "conflict"


def test_route_duplicate_with_mismatched_value_is_conflict():
    a, b = _e(1, value=3.2, unit="兆円"), _e(2, value=3.3, unit="兆円")
    assert route(a, b, _j("duplicate")).bucket == "conflict"


def test_route_duplicate_without_values():
    r = route(_e(1), _e(2), _j("duplicate", keep="b"))
    assert (r.bucket, r.old, r.by, r.reason) == ("proposal", "tech-1", "tech-2", "duplicate")


def test_route_rejects_duplicate_with_one_sided_value():
    assert route(_e(1, value=3.2, unit="兆円"), _e(2), _j("duplicate")).bucket in ("requery", "held")


def test_route_updates_uses_newer_not_retrieved():
    a = _e(1, retrieved="2026-09-30")   # 後から取得したが古い時点の記述
    b = _e(2, retrieved="2026-01-01")
    r = route(a, b, _j("updates", newer="b"))
    assert (r.old, r.by) == ("tech-1", "tech-2")


def test_route_low_confidence_requeries_then_holds():
    assert route(_e(1), _e(2), _j("duplicate", scope=0.6)).bucket == "requery"
    assert route(_e(1), _e(2), _j("duplicate", rc=0.4)).bucket == "held"


def test_check_components_holds_whole_component_with_conflict():
    p1 = Routing(bucket="proposal", old="tech-1", by="tech-3", reason="duplicate")
    p2 = Routing(bucket="proposal", old="tech-2", by="tech-3", reason="duplicate")
    keep, held = check_components([p1, p2], conflicts=[("tech-1", "tech-2")])
    assert keep == [] and held == [p1, p2]


def test_check_components_holds_branch_and_chain():
    branch = [Routing(bucket="proposal", old="tech-1", by="tech-2", reason="duplicate"),
              Routing(bucket="proposal", old="tech-1", by="tech-3", reason="duplicate")]
    chain = [Routing(bucket="proposal", old="tech-4", by="tech-5", reason="updates"),
             Routing(bucket="proposal", old="tech-5", by="tech-6", reason="updates")]
    keep, held = check_components(branch + chain, conflicts=[])
    assert keep == [] and len(held) == 4
```

```python
def test_affected_artifacts_includes_descendants(tmp_path):
    storage = LocalJsonStorage(tmp_path / "data")
    store = ArtifactStore(storage)
    store.save("p1", Artifact(project="p1", type="research", requirements_version=1,
                              content="調査", cited_knowledge=["tech-1"]))
    store.save("p1", Artifact(project="p1", type="as-is-report", requirements_version=1,
                              content="報告", derived_from=["research-v1"]))
    rows = affected_artifacts(storage, tmp_path / "knowledge", "tech", "tech-1")
    assert {(r["project"], r["artifact"], r["via"]) for r in rows} == {
        ("p1", "research-v1", "cited"), ("p1", "as-is-report-v1", "research-v1")}
```

(`as-is-report` の保存に要件が要る場合は、`RequirementsStore(storage).save` で最小の要件を先に保存する。既存の `core/tests/test_artifacts.py` のヘルパー `_artifact` があれば流用する)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest core/tests/test_knowledge_dedupe.py -v`
Expected: FAIL with `ModuleNotFoundError: medo_core.knowledge_dedupe`

- [ ] **Step 3: Write minimal implementation**

```python
"""ナレッジの重複統合の決定論部分。Jevの判定は呼び出し側から受け取る。"""

from __future__ import annotations

import re
import unicodedata
from itertools import combinations
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel

from medo_core.knowledge import KnowledgeEntry
from medo_core.source_check import _without_annotation
from medo_core.storage import Storage


def _url_key(source: str) -> str:
    u = urlparse(source)
    path = re.sub(r"\.(pdf|html?)$", "", u.path.rstrip("/"))
    path = re.sub(r"^/(abs|pdf)/", "/paper/", path) if "arxiv.org" in u.netloc else path
    return f"{u.netloc.lower()}{path}"


def _bigrams(text: str) -> set[str]:
    t = "".join(unicodedata.normalize("NFKC", text).split())
    return {t[i:i + 2] for i in range(len(t) - 1)}


def _overlap(a: str, b: str) -> float:
    x, y = _bigrams(a), _bigrams(b)
    return len(x & y) / len(x | y) if x | y else 0.0


def candidate_pairs(entries, overlap_threshold=0.35):
    live = [e for e in entries if not e.is_superseded]
    pairs = []
    for a, b in combinations(live, 2):
        same_url = _url_key(a.source) == _url_key(b.source)
        same_unit = bool(a.unit) and _without_annotation(a.unit) == _without_annotation(b.unit)
        if same_url or same_unit or _overlap(a.statement, b.statement) >= overlap_threshold:
            pairs.append((a.entry_id, b.entry_id))
    return pairs


class PairJudgment(BaseModel):
    relation: str
    relation_confidence: float
    same_scope: float
    newer: str
    newer_confidence: float
    keep: str
    keep_confidence: float


class Routing(BaseModel):
    bucket: Literal["proposal", "conflict", "excluded", "requery", "held"]
    old: str = ""
    by: str = ""
    reason: Literal["", "duplicate", "updates"] = ""


def _pick(a, b, side):
    return (b.entry_id, a.entry_id) if side == "a" else (a.entry_id, b.entry_id)


def route(a, b, j, threshold=0.8):
    t = threshold
    units_match = _without_annotation(a.unit) == _without_annotation(b.unit)
    if j.relation == "conflicting":
        return Routing(bucket="conflict")
    if (j.relation == "duplicate" and j.relation_confidence >= t and j.same_scope >= t
            and units_match and a.value is not None and b.value is not None
            and a.value != b.value):
        return Routing(bucket="conflict")
    if j.relation in ("complementary", "unrelated") and j.relation_confidence >= t:
        return Routing(bucket="excluded")
    one_sided = (a.value is None) != (b.value is None)
    if (j.relation == "duplicate" and j.relation_confidence >= t and j.same_scope >= t
            and j.newer == "same" and j.newer_confidence >= t and j.keep_confidence >= t
            and units_match and not one_sided):
        old, by = _pick(a, b, j.keep)
        return Routing(bucket="proposal", old=old, by=by, reason="duplicate")
    if (j.relation == "updates" and j.relation_confidence >= t and j.same_scope >= t
            and j.newer in ("a", "b") and j.newer_confidence >= t):
        old, by = _pick(a, b, j.newer)
        return Routing(bucket="proposal", old=old, by=by, reason="updates")
    if j.relation_confidence >= 0.5 and j.relation in ("duplicate", "updates"):
        return Routing(bucket="requery")
    return Routing(bucket="held")
```

(`_pick` は「残す側」を受け取り `(old, by)` を返す。`side == "a"` なら a を残すので old は b)

`check_components`: proposals の old/by を頂点とする無向グラフの連結成分ごとに、(i) 成分内の2頂点が `conflicts` に含まれる、(ii) 同じ `old` が2回以上、(iii) ある `by` が別の案の `old` に現れる、のいずれかなら成分の案をすべて held に、それ以外は keep に入れる。順序は入力順を保つ。

`affected_artifacts`: `storage.list_children("projects")` の各案件で `ArtifactStore(storage)._load_all(project)` を読み、`cited_knowledge` に `entry_id` を含む生成物を `via="cited"` で、さらに `freshness` の再帰で親がそれらの生成物である子孫を `via=<親ID>` で返す。子孫の判定は `Artifact` の親参照(`derived_from` / `grown_from` の既存フィールド)を辿る。

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest core/tests/test_knowledge_dedupe.py -v && uv run ruff check core`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core/src/medo_core/knowledge_dedupe.py core/tests/test_knowledge_dedupe.py
git commit -m "feat(core): ナレッジの重複候補と振り分けの決定論部分"
```

**Part A の終わり**: PR を作る(Closes 実装Issue A)。`knowledge search` / `index` の出力から置き換え済みが消えるので人間レビュー対象(spec §9)。

---

## Part B: cli と Jev

### Task 5: jev.judge_pairs

**Files:**
- Modify: `cli/src/medo_cli/jev.py`
- Test: `cli/tests/test_cli.py`(既存のJevテストの並び)

**Interfaces:**
- Consumes: `PairJudgment`(Task 4)
- Produces: `judge_pairs(pairs: list[tuple[KnowledgeEntry, KnowledgeEntry]], evidence: dict[str, str] | None = None, timeout: int = 60) -> list[PairJudgment]` — 1リクエストで全組を判定。鍵が無ければ `JevUnavailable`(新設、RuntimeError のサブクラス)、呼び出し・解析の失敗は `RuntimeError`

- [ ] **Step 1: Write the failing test**

```python
def test_judge_pairs_sends_four_questions_per_pair_without_numbers_to_judge(monkeypatch):
    import medo_cli.jev as jev
    sent = {}

    def fake(request, timeout):
        sent.update(json.loads(request.data))
        answers = {}
        for n in range(2):
            answers[f"p{n}_relation"] = {"choice": "duplicate", "confidence": 0.9}
            answers[f"p{n}_same_scope"] = {"noul": 0.85}
            answers[f"p{n}_newer"] = {"choice": "same", "confidence": 0.8}
            answers[f"p{n}_keep"] = {"choice": "a", "confidence": 0.7}
        return _FakeResponse({"answers": answers})

    monkeypatch.setenv("TYPESAFE_API_KEY", "dummy")
    monkeypatch.setattr(jev, "urlopen", fake)
    e = lambda i: KnowledgeEntry(entry_id=f"tech-{i}", kind="tech", statement="s",
                                 source="https://e.com", retrieved="2026-09-01")
    result = jev.judge_pairs([(e(1), e(2)), (e(3), e(4))])

    assert len(sent["questions"]) == 8
    assert result[0].relation == "duplicate" and result[0].keep_confidence == 0.7


def test_judge_pairs_without_key_raises_unavailable(monkeypatch):
    import medo_cli.jev as jev
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(jev.JevUnavailable):
        jev.judge_pairs([])
```

(`_FakeResponse` は既存テストのヘルパーを使う。無ければ `__enter__`/`__exit__` と `read()` を持つ最小のクラスを足す)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest cli/tests/test_cli.py -k judge_pairs -v`
Expected: FAIL(`judge_pairs` 未定義)

- [ ] **Step 3: Write minimal implementation**

```python
class JevUnavailable(RuntimeError):
    """鍵が無い。呼び出しの失敗(RuntimeError)と区別する(spec §6.2)。"""


def judge_pairs(pairs, evidence=None, timeout=60):
    api_key = os.environ.get("TYPESAFE_API_KEY")
    if not api_key:
        raise JevUnavailable("TYPESAFE_API_KEY が設定されていません")
    questions = {}
    for n, _ in enumerate(pairs):
        a, b = f"`pairs[{n}].a`", f"`pairs[{n}].b`"
        questions[f"p{n}_relation"] = {"type": "choice",
            "instructions": f"{a} と {b} の関係を分類する。数値が同じかどうかは判断しない。",
            "criteria": {
                "duplicate": "同じ範囲・同じ時点の同じ事実を述べている",
                "updates": "同じ範囲・同じ指標について、異なる時点の値を述べている",
                "complementary": "同じ対象の別の側面を述べている",
                "conflicting": "同じ範囲・同じ時点・同じ指標なのに述べている値や結論が食い違う",
                "unrelated": "関係が無い"}}
        questions[f"p{n}_same_scope"] = {"type": "noul",
            "instructions": f"{a} と {b} の地域・対象・指標が一致しているか。時点は問わない。"}
        questions[f"p{n}_newer"] = {"type": "choice",
            "instructions": f"{a} と {b} が述べている時点(調査年・発表年・版)の関係。取得日(retrieved)では判断しない。",
            "criteria": {"a": "a のほうが後の時点", "b": "b のほうが後の時点",
                         "same": "同じ時点", "unknown": "時点が読み取れない"}}
        questions[f"p{n}_keep"] = {"type": "choice",
            "instructions": f"{a} と {b} が同じ事実を述べているとき、残すべきほうを選ぶ。基準は出典が一次資料か、記述が具体的か。新しさは基準にしない。",
            "criteria": {"a": "a を残す", "b": "b を残す"}}
    state = {"pairs": [
        {"a": _entry_state(a, evidence), "b": _entry_state(b, evidence)} for a, b in pairs]}
    answers = _post({"state": state, "model": "jev-latest", "questions": questions},
                    api_key, timeout)
    try:
        return [PairJudgment(
            relation=answers[f"p{n}_relation"]["choice"],
            relation_confidence=answers[f"p{n}_relation"]["confidence"],
            same_scope=answers[f"p{n}_same_scope"]["noul"],
            newer=answers[f"p{n}_newer"]["choice"],
            newer_confidence=answers[f"p{n}_newer"]["confidence"],
            keep=answers[f"p{n}_keep"]["choice"],
            keep_confidence=answers[f"p{n}_keep"]["confidence"],
        ) for n, _ in enumerate(pairs)]
    except (KeyError, TypeError, ValueError) as e:
        raise RuntimeError(f"Jevの応答が不正です: {e}") from e


def _entry_state(entry, evidence):
    state = entry.model_dump(mode="json", include={"entry_id", "statement", "value", "unit",
                                                   "source", "retrieved", "note"})
    if evidence and entry.entry_id in evidence:
        state["evidence"] = evidence[entry.entry_id]
    return state
```

`_post(payload, api_key, timeout) -> dict` は既存の `judge_candidates` / `judge_support` の送信部分を共通化した関数(HTTPError は本文付きで RuntimeError、その他の通信・JSON失敗も RuntimeError、戻り値は `answers`)。既存2関数もこれを使うよう置き換え、既存テストがそのまま通ることを確かめる。

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest cli/tests -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cli/src/medo_cli/jev.py cli/tests/test_cli.py
git commit -m "feat(cli): ナレッジの組の関係をJevに4問で判定させる"
```

### Task 6: knowledge dedupe / knowledge supersede / --include-superseded

**Files:**
- Modify: `cli/src/medo_cli/main.py`
- Test: `cli/tests/test_cli.py`

**Interfaces:**
- Consumes: `candidate_pairs` / `route` / `check_components` / `affected_artifacts`(Task 4)、`judge_pairs` / `JevUnavailable`(Task 5)、`KnowledgeStore.supersede`(Task 2)、`fetch_body`(既存)、`source_check.nearby_excerpt`(既存)
- Produces:
  - `medo knowledge dedupe --kind <k> [--format json|digest] [--threshold 0.8]`。json 出力: `{"kind", "judge": "ok"|"unavailable", "candidates": [[a,b],...], "proposals": [...], "conflicts": [...], "held": [...]}`。proposals の要素は spec §6.1 のキー
  - `medo knowledge supersede --kind <k> --old <id> --by <id> --reason duplicate|updates`。出力: `superseded: <old> -> <by>` と、影響する生成物を1行ずつ `affected: <project>/<artifact> (<via>)`、無ければ `affected: (なし)`
  - `knowledge search` / `knowledge index` に `--include-superseded`

- [ ] **Step 1: Write the failing tests**

```python
from medo_core.knowledge_dedupe import PairJudgment


def _save_k(kind, statement, source="https://e.com/a"):
    r = runner.invoke(app, ["knowledge", "save", "--kind", kind, "--statement", statement,
                            "--source", source])
    assert r.exit_code == 0, r.output


def _pj(relation="duplicate", scope=0.9, newer="same", keep="a"):
    return PairJudgment(relation=relation, relation_confidence=0.9, same_scope=scope,
                        newer=newer, newer_confidence=0.9, keep=keep, keep_confidence=0.9)


def test_dedupe_without_key_returns_candidates_only(medo_home, monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    _save_k("market", "市場規模は2024年に3.2兆円")
    _save_k("market", "2024年の市場規模は3.2兆円")
    r = runner.invoke(app, ["knowledge", "dedupe", "--kind", "market", "--format", "json"])
    out = json.loads(r.stdout)
    assert r.exit_code == 0 and out["judge"] == "unavailable"
    assert out["candidates"] == [["market-1", "market-2"]] and out["proposals"] == []


def test_dedupe_jev_failure_exits_nonzero(medo_home, monkeypatch):
    from medo_cli import main
    _save_k("market", "市場規模は2024年に3.2兆円")
    _save_k("market", "2024年の市場規模は3.2兆円")

    def boom(*_a, **_k):
        raise RuntimeError("HTTP 500")

    monkeypatch.setattr(main, "judge_pairs", boom)
    r = runner.invoke(app, ["knowledge", "dedupe", "--kind", "market"])
    assert r.exit_code != 0 and "error:" in r.output


def test_dedupe_requeries_once_with_evidence_then_holds(medo_home, monkeypatch):
    from medo_cli import main
    from medo_cli.fetch import FetchResult
    _save_k("market", "市場規模は2024年に3.2兆円")
    _save_k("market", "2024年の市場規模は3.2兆円")
    calls = []

    def judge(pairs, evidence=None, timeout=60):
        calls.append(evidence)
        return [_pj(scope=0.6) for _ in pairs]

    monkeypatch.setattr(main, "judge_pairs", judge)
    monkeypatch.setattr(main, "fetch_body", lambda *_: FetchResult(body="市場規模は2024年に3.2兆円"))
    out = json.loads(runner.invoke(
        app, ["knowledge", "dedupe", "--kind", "market", "--format", "json"]).stdout)
    assert len(calls) == 2 and calls[0] is None and calls[1]
    assert out["held"] == [["market-1", "market-2"]] and out["proposals"] == []


def test_dedupe_fetch_failure_holds_without_requery(medo_home, monkeypatch):
    from medo_cli import main
    from medo_cli.fetch import FetchResult
    _save_k("market", "市場規模は2024年に3.2兆円")
    _save_k("market", "2024年の市場規模は3.2兆円")
    calls = []
    monkeypatch.setattr(main, "judge_pairs",
                        lambda pairs, evidence=None, timeout=60: calls.append(1) or
                        [_pj(scope=0.6) for _ in pairs])
    monkeypatch.setattr(main, "fetch_body", lambda *_: FetchResult(reason="HTTP 403"))
    out = json.loads(runner.invoke(
        app, ["knowledge", "dedupe", "--kind", "market", "--format", "json"]).stdout)
    assert len(calls) == 1 and out["held"] == [["market-1", "market-2"]]


def test_dedupe_proposes_duplicate(medo_home, monkeypatch):
    from medo_cli import main
    _save_k("market", "市場規模は2024年に3.2兆円")
    _save_k("market", "2024年の市場規模は3.2兆円")
    monkeypatch.setattr(main, "judge_pairs",
                        lambda pairs, evidence=None, timeout=60: [_pj(keep="b") for _ in pairs])
    out = json.loads(runner.invoke(
        app, ["knowledge", "dedupe", "--kind", "market", "--format", "json"]).stdout)
    assert [(p["old"], p["by"], p["reason"]) for p in out["proposals"]] == [
        ("market-1", "market-2", "duplicate")]


def test_supersede_with_no_projects(medo_home):
    _save_k("practice", "a", source="medo-test")
    _save_k("practice", "b", source="medo-test")
    r = runner.invoke(app, ["knowledge", "supersede", "--kind", "practice", "--old", "practice-1",
                            "--by", "practice-2", "--reason", "duplicate"])
    assert r.exit_code == 0
    assert "superseded: practice-1 -> practice-2" in r.stdout and "affected: (なし)" in r.stdout


def test_supersede_lists_citing_artifacts(medo_home, tmp_path):
    _save_k("practice", "a", source="medo-test")
    _save_k("practice", "b", source="medo-test")
    content = tmp_path / "research.md"
    content.write_text("調査", encoding="utf-8")
    r = runner.invoke(app, ["artifacts", "save", "--project", "p1", "--type", "research",
                            "--cites", "practice-1", "--file", str(content),
                            "--generated-by", "claude"])
    assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["knowledge", "supersede", "--kind", "practice", "--old", "practice-1",
                            "--by", "practice-2", "--reason", "duplicate"])
    assert "affected: p1/research-v1 (cited)" in r.stdout


def test_supersede_rejects_invalid_pair(medo_home):
    _save_k("practice", "a", source="medo-test")
    r = runner.invoke(app, ["knowledge", "supersede", "--kind", "practice", "--old", "practice-1",
                            "--by", "practice-1", "--reason", "duplicate"])
    assert r.exit_code != 0 and "error:" in r.output


def test_search_hides_superseded_unless_flag(medo_home):
    _save_k("practice", "重複A", source="medo-test")
    _save_k("practice", "重複B", source="medo-test")
    runner.invoke(app, ["knowledge", "supersede", "--kind", "practice", "--old", "practice-1",
                        "--by", "practice-2", "--reason", "duplicate"])
    hidden = runner.invoke(app, ["knowledge", "search", "重複", "--kind", "practice"]).stdout
    shown = runner.invoke(app, ["knowledge", "search", "重複", "--kind", "practice",
                                "--include-superseded"]).stdout
    assert "practice-1" not in hidden and "practice-1" in shown
```

(`artifacts save` の research 型が要件の保存を要求する場合は、既存の `_save_requirements(tmp_path)` を先に呼ぶ。research は要件に依存しない型なので通常は不要)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest cli/tests/test_cli.py -k "dedupe or supersede or include_superseded" -v`
Expected: FAIL(コマンド未定義)

- [ ] **Step 3: Write minimal implementation**

dedupe の流れ(`main.py` に追加):

```python
@knowledge_app.command("dedupe")
def knowledge_dedupe(
    kind: str = typer.Option(...),
    format: Literal["json", "digest"] = typer.Option("digest"),
    threshold: float = typer.Option(0.8),
):
    store = KnowledgeStore(get_knowledge_root())
    entries = {e.entry_id: e for e in store.search("", kind=kind, limit=10**6,
                                                   char_budget=10**9).entries}
    pairs = candidate_pairs(list(entries.values()))
    result = {"kind": kind, "judge": "ok", "candidates": [list(p) for p in pairs],
              "proposals": [], "conflicts": [], "held": []}
    if pairs:
        try:
            first = judge_pairs([(entries[a], entries[b]) for a, b in pairs])
        except JevUnavailable:
            result["judge"] = "unavailable"
            _echo_dedupe(result, format)
            return
        except RuntimeError as e:
            _fail(f"Jevの判定に失敗: {e}")
        routed = {p: route(entries[p[0]], entries[p[1]], j, threshold) for p, j in zip(pairs, first)}
        requery = [p for p, r in routed.items() if r.bucket == "requery"]
        evidence, unfetched = _evidence_for(requery, entries)
        for p in requery:
            if p[0] in unfetched or p[1] in unfetched:
                routed[p] = Routing(bucket="held")
        retry = [p for p in requery if routed[p].bucket == "requery"]
        if retry:
            try:
                second = judge_pairs([(entries[a], entries[b]) for a, b in retry], evidence=evidence)
            except RuntimeError as e:
                _fail(f"Jevの判定に失敗: {e}")
            for p, j in zip(retry, second):
                r = route(entries[p[0]], entries[p[1]], j, threshold)
                routed[p] = Routing(bucket="held") if r.bucket == "requery" else r
        conflicts = [p for p, r in routed.items() if r.bucket == "conflict"]
        keep, held_by_component = check_components(
            [r for r in routed.values() if r.bucket == "proposal"], conflicts)
        result["proposals"] = [_proposal_payload(r, routed, pairs, first, retry) for r in keep]
        result["conflicts"] = [list(p) for p in conflicts]
        result["held"] = [list(p) for p, r in routed.items() if r.bucket == "held"] + [
            [r.old, r.by] for r in held_by_component]
    _echo_dedupe(result, format)
```

`_evidence_for(pairs, entries) -> tuple[dict[str, str], set[str]]`: 組に出てくる各エントリの `source` を `fetch_body` で1回ずつ取得し、取れたら `nearby_excerpt(entry.statement, body, entry.value, entry.unit) or body[:400]` を evidence に、取れなければ ID を unfetched に入れる。`_proposal_payload` は spec §6.1 のキー(old / by / reason / relation と確信度 / same_scope / newer または keep と確信度 / requeried)を、その組の最後の判定から作る。`_echo_dedupe` は json ならそのまま、digest なら `proposals` / `conflicts` / `held` の見出しごとに1行ずつ、`judge: unavailable` のときはその行と候補の組を出す。

supersede:

```python
@knowledge_app.command("supersede")
def knowledge_supersede(
    kind: str = typer.Option(...),
    old: str = typer.Option(...),
    by: str = typer.Option(...),
    reason: Literal["duplicate", "updates"] = typer.Option(...),
):
    root = get_knowledge_root()
    try:
        KnowledgeStore(root).supersede(kind, old, by, reason)
    except ValueError as e:
        _fail(str(e))
    typer.echo(f"superseded: {old} -> {by}")
    rows = affected_artifacts(get_storage(), root, kind, old)
    if not rows:
        typer.echo("affected: (なし)")
    for row in rows:
        typer.echo(f"affected: {row['project']}/{row['artifact']} ({row['via']})")
```

`knowledge search` / `knowledge index` に `include_superseded: bool = typer.Option(False, "--include-superseded")` を足して store に渡す。`knowledge index` の digest 出力は、`warnings` があれば `warning: ...` を1行ずつ足す。`_knowledge_entry_payload` に来歴の3フィールドを含める。

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -q && uv run ruff check .`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cli/src/medo_cli/main.py cli/tests/test_cli.py
git commit -m "feat(cli): knowledge dedupe と supersede"
```

### Task 7: 評価セットと閾値の決定

実装時の評価補足: Step 2のサンプルはすべての組をJevに渡しているが、実際のCLIと同じく候補生成を通った組だけを渡し、候補に入らない組はheldとして数える。文字2-gramの閾値はspec §8に従ってtune組のみで選び、CLIにも反映する。残す側に加えて置き換え理由の誤りも誤統合に数える。評価後のCLI既定値は文字2-gramが0.20、判定Tが0.50。Step 3に従い、聞き直しのテストは明示の `--threshold 0.8` で初期のテスト条件を保つ。

**Files:**
- Create: `scripts/eval/dedupe_cases.json`, `scripts/eval/run_dedupe_eval.py`

**Interfaces:**
- Consumes: `judge_pairs`(Task 5)、`route` / `check_components`(Task 4)
- Produces: 評価の出力(調整用の組で選んだ T、検証用の組での誤統合数・conflicts の取りこぼし数・統合の検出率)

- [ ] **Step 1: 評価セットを作る**

`dedupe_cases.json` は `[{"split": "tune"|"validate", "a": {KnowledgeEntry の dict}, "b": {...}, "label": "duplicate"|"updates"|"conflicting"|"complementary"|"unrelated", "keep": "a"|"b"|null}]`。各 split に5種類を最低2組ずつ。必須の組:
- arXiv の abs と pdf から同じ論文の同じ主張(duplicate)
- 同じ指標の2023年値と2025年値で、2023年値の `retrieved` のほうが新しい(updates、取得日と記述の時点が逆)
- 同じ指標・同じ年で値が違い、言い回しも出典ドメインも違う(conflicting)
- 同じ製品の料金と対応地域(complementary)
- 無関係(unrelated)

ラベルはJevに渡さない(`run_triage_eval.py` と同じく a / b だけを渡す)。

- [ ] **Step 2: 評価スクリプトを書く**

```python
"""正解付きの組で dedupe の振り分けを評価し、閾値を決める。"""

import json
import sys
from pathlib import Path

from medo_cli.jev import judge_pairs
from medo_core.knowledge import KnowledgeEntry
from medo_core.knowledge_dedupe import candidate_pairs, check_components, route

CASES = Path(__file__).with_name("dedupe_cases.json")
MERGE = {"duplicate", "updates"}


def _wrong(case, r):
    if r.bucket != "proposal":
        return False
    if case["label"] not in MERGE:
        return True
    kept = case["a"]["entry_id"] if case["keep"] == "a" else case["b"]["entry_id"]
    return r.by != kept


def main() -> int:
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    pairs = {c["split"]: [] for c in cases}
    for c in cases:
        pairs[c["split"]].append((KnowledgeEntry(**c["a"]), KnowledgeEntry(**c["b"])))
    tune = [c for c in cases if c["split"] == "tune"]
    judged = judge_pairs(pairs["tune"])  # T を変えても判定は同じなので1回だけ呼ぶ
    chosen = None
    for t in [x / 100 for x in range(50, 100, 5)]:
        if not any(_wrong(c, route(a, b, j, t)) for c, (a, b), j in zip(tune, pairs["tune"], judged)):
            chosen = t
            break
    if chosen is None:
        print("error: 調整用の組で誤統合0件になる閾値がありません", file=sys.stderr)
        return 1
    val = [c for c in cases if c["split"] == "validate"]
    vj = judge_pairs(pairs["validate"])
    routed = [route(a, b, j, chosen) for (a, b), j in zip(pairs["validate"], vj)]
    conflicts = [(a.entry_id, b.entry_id) for (a, b), r in zip(pairs["validate"], routed)
                 if r.bucket == "conflict"]
    keep, _ = check_components([r for r in routed if r.bucket == "proposal"], conflicts)
    wrong = sum(_wrong(c, r) for c, r in zip(val, routed) if r in keep)
    missed_conflicts = sum(
        1 for c, (a, b), r in zip(val, pairs["validate"], routed)
        if c["label"] == "conflicting" and (
            r.bucket != "conflict" or (a.entry_id, b.entry_id) not in candidate_pairs([a, b])))
    merge_cases = [r for c, r in zip(val, routed) if c["label"] in MERGE]
    rate = sum(r in keep for r in merge_cases) / len(merge_cases) if merge_cases else 0.0
    print(f"threshold={chosen} wrong={wrong} missed_conflicts={missed_conflicts} proposal_rate={rate:.2f}")
    ok = wrong == 0 and missed_conflicts == 0 and rate >= 0.8
    print("accept" if ok else "reject")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
```


- [ ] **Step 3: 実行する**

Run: `python3 scripts/eval/run_dedupe_eval.py`
Expected: 選んだ T と検証の3指標が表示され、受け入れ条件を満たす。満たさなければ Jev の instructions / criteria を調整する(最大3回。評価セットは変えない)。T が 0.8 から変わったら `main.py` の `--threshold` の既定値と spec §3.2 の「出発点」の記述を合わせる

- [ ] **Step 4: Commit**

```bash
git add scripts/eval/dedupe_cases.json scripts/eval/run_dedupe_eval.py
git commit -m "test(scripts): dedupe の評価セットと閾値の決定"
```

**Part B の終わり**: PR(Closes 実装Issue B)。CLIの新コマンド=契約変更で人間レビュー対象。

---

## Part C: Skill と同期

### Task 8: Skill medo-knowledge-digest と steering の同期

**Files:**
- Create: `skills/src/medo-knowledge-digest/SKILL.md`
- Modify: `skills/tests/test_build.py`, `.claude/steering/tech.md`, `.claude/steering/structure.md`, `docs/usage.md`

**Interfaces:**
- Consumes: Part B の CLI

- [ ] **Step 1: Write the failing test**

```python
MAINTENANCE_SKILLS = ["medo-knowledge-digest"]


def test_knowledge_digest_skill_confirms_each_proposal_before_superseding(tmp_path):
    text = _built(tmp_path, "medo-knowledge-digest")
    assert "medo knowledge dedupe" in text and "medo knowledge supersede" in text
    assert "1組ずつ" in text and "judge: unavailable" in text
    body = text.partition("## 契約")[2]
    assert len([l for l in body.splitlines() if l.startswith("- ")]) == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest skills/tests -k knowledge_digest -v`
Expected: FAIL(Skill が無い)

- [ ] **Step 3: Write the Skill**

```markdown
---
name: medo-knowledge-digest
description: 案件を跨いで蓄積したナレッジの重複を洗い出し、ユーザーが承認した組だけを置き換えて来歴を残す。値の食い違いは統合せずに見せる。標準周回とは別の保守作業。
---

# medo-knowledge-digest: ナレッジの重複を統合する

## 手順

1. 全体を見る:

       medo knowledge index

   `warning:` があれば(来歴の破損)そのまま報告する。

2. kind ごとに統合案を作る(書き込みはしない):

       medo knowledge dedupe --kind <tech|market|policy|trend|company|practice>

   `judge: unavailable` なら、候補の組を見せて「判定できなかった」と報告し、統合はしない。

3. 結果をユーザーに見せる。`proposals`(統合案)は、残す側・置き換える側・理由・確信度・出典を並べる。`conflicts`(値の食い違い)は統合せず、**ユーザーが出典を開いて確認するよう案内する。自分で出典を読んで解決しに行かない**。`held`(判定保留)は見せるだけでよい。

4. `proposals` を**1組ずつ**ユーザーに承認を尋ね、返答を待ってから確定する:

       medo knowledge supersede --kind <k> --old <置き換える側> --by <残す側> --reason <duplicate|updates>

   承認されなかった組は確定しない。`held` の組は、ユーザーが根拠を見て統合したいと明言したときに限り、残す側と理由をユーザーに確かめてから確定してよい。

5. `supersede` の出力の `affected:` を集め、作り直しが要る生成物として案件ごとに報告する(各案件の `medo status` の `regenerate_stale_artifacts` にも載る)。

## 契約(必ず守る)

- 確定は `medo knowledge supersede` だけで行い、エントリのファイルを直接書き換えない
- ユーザーの承認なしに置き換えない。`conflicts` を統合しない
- CLIが失敗したら推測で補完せず、エラー内容をそのまま報告する
```

`test_build.py` の `SKILL_NAMES` には足さない(案件の status を読まない保守作業のため、`--view summary` を要求するテストの対象外)。上の `MAINTENANCE_SKILLS` を定義する。

- [ ] **Step 4: 同期**

- `tech.md` §1 の洗練フローと §4 の knowledge-digest 行: 「Gemini Flash等で構造化・圧縮」→「決定論の候補抽出+Jev(TypeSafe System One)の段階的な分類+人の承認(新しい文は生成しない)。詳細: phase2-knowledge-digest.md」。§3 の Gemini API 行と §5 の `GEMINI_API_KEY` 行は「knowledge-digest で使う場合のみ」を削除し、§5 に `TYPESAFE_API_KEY`(Jev。research triage・出典の補助判定・knowledge-digest)を足す。§7 のテスト方針の knowledge-digest 行を「Jevは urlopen を差し替え、正解付き評価セットで閾値を決める」に改める
- `structure.md` §2 に `knowledge_dedupe.py` を1行、§4 に `medo-knowledge-digest` を1行
- `docs/usage.md` の knowledge の節に dedupe / supersede の例を1つずつ

- [ ] **Step 5: Run and commit**

Run: `uv run pytest -q && python3 skills/build.py`
Expected: PASS

```bash
git add skills/src/medo-knowledge-digest skills/tests/test_build.py .claude/steering/tech.md .claude/steering/structure.md docs/usage.md
git commit -m "feat(skills): ナレッジの重複を統合する medo-knowledge-digest"
```

**Part C の終わり**: PR(Closes 実装Issue C)。Skill 契約の新設で人間レビュー対象。
